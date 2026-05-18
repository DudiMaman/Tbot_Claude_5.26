"""
Event-driven BacktestEngine — replays historical bars through the full pipeline.
Same code path as live trading; only broker and clock differ.
Enforces bar-shift rule: signal on bar N → fill at bar N+1 open.
"""
from __future__ import annotations

import asyncio
import structlog
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

import pandas as pd

from bot.core.clock import SimulatedClock
from bot.core.config import BrokerConfig, RiskConfig, StrategyConfig
from bot.core.events import FillEvent, MarketEvent, OHLCVBar, OrderEvent, Signal
from bot.core.modes import ExecutionMode, RiskMode
from bot.data.normalizer import bars_to_dataframe
from bot.data.timeframe_manager import TimeframeManager
from bot.execution.fee_model import FeeModel
from bot.execution.paper import PaperBroker
from bot.portfolio.manager import PortfolioManager
from bot.reporting.equity_curve import EquityCurve, compute_metrics, save_summary, save_trade_log
from bot.risk.manager import RiskManager
from bot.brain.engine import BrainEngine
from bot.strategies.base import BaseStrategy, StrategyContext
from bot.utils.idempotency import make_key

logger = structlog.get_logger(__name__)


class BacktestEngine:
    def __init__(
        self,
        risk_config: RiskConfig,
        broker_config: BrokerConfig,
        strategies: list[BaseStrategy],
        output_dir: str = "reports",
        enable_brain: bool = True,
        brain_interval_bars: int = 50,
    ) -> None:
        self._rcfg = risk_config
        self._bcfg = broker_config
        self._strategies = strategies
        self._output_dir = Path(output_dir)

        self._portfolio = PortfolioManager(
            initial_cash=risk_config.capital_usd,
            asset_class_map={},
        )
        self._broker = PaperBroker(broker_config, initial_cash=risk_config.capital_usd)
        self._risk_mgr = RiskManager(risk_config, broker_config, self._portfolio)
        self._fee_model = FeeModel(broker_config)
        self._equity_curve = EquityCurve()

        # Pending signals from bar N, to be filled at bar N+1
        self._pending_signals: list[tuple[Signal, float]] = []  # (signal, qty)

        self._broker.register_fill_callback(self._on_fill)

        for strategy in self._strategies:
            strategy.initialize(self._portfolio)

        self._brain: Optional[BrainEngine] = (
            BrainEngine(
                strategies=strategies,
                portfolio=self._portfolio,
                risk_manager=self._risk_mgr,
                assessment_interval_bars=brain_interval_bars,
                state_path=self._output_dir / "brain_state.json",
            )
            if enable_brain
            else None
        )

    async def run(
        self,
        bars_by_tf: dict[str, pd.DataFrame],  # {"1h": df, "1D": df, ...}
        primary_tf: str = "1h",
        step_size: float = 0.0001,
    ) -> dict:
        """
        Run backtest over provided DataFrames.
        bars_by_tf: dict mapping timeframe string to OHLCV DataFrame (timestamp index).
        Returns metrics dict.
        """
        primary_df = bars_by_tf.get(primary_tf)
        if primary_df is None or primary_df.empty:
            raise ValueError(f"No data for primary timeframe {primary_tf}")

        tf_mgr = TimeframeManager(list(bars_by_tf.keys()))

        # Pre-warm all timeframe buffers with first 50 bars
        for tf, df in bars_by_tf.items():
            warm_bars = _df_to_bars(df.iloc[:50], "BT", tf)
            tf_mgr.pre_warm("BT", tf, warm_bars)

        clock = SimulatedClock(primary_df.index[0].to_pydatetime())

        total_bars = len(primary_df)
        for i, (ts, row) in enumerate(primary_df.iterrows()):
            ts_dt = ts.to_pydatetime() if hasattr(ts, "to_pydatetime") else ts
            clock.advance(ts_dt)

            # Simulate fills from previous bar's signals
            if self._pending_signals:
                for strategy in self._strategies:
                    for sym in strategy.config.symbols:
                        bar_for_fill = _row_to_bar(ts_dt, row, sym, primary_tf)
                        fills = await self._broker.on_bar(bar_for_fill)
                        for fill in fills:
                            await self._process_fill(fill, sym)

            # Let the Brain assess and adapt before dispatching strategies
            primary_slice = bars_by_tf[primary_tf].iloc[: i + 1]
            if self._brain is not None:
                self._brain.on_bar(primary_slice)

            # Build context for each symbol and strategy
            for strategy in self._strategies:
                # Brain may have disabled this strategy
                if self._brain is not None and not self._brain.is_strategy_enabled(strategy.strategy_id):
                    continue
                for sym in strategy.config.symbols:
                    curr_bar = _row_to_bar(ts_dt, row, sym, primary_tf)
                    tf_mgr.update(curr_bar)

                    context_bars: dict[str, pd.DataFrame] = {}
                    for tf, df in bars_by_tf.items():
                        context_bars[tf] = df.iloc[: i + 1].copy()

                    context = StrategyContext(
                        symbol=sym,
                        bars=context_bars,
                        current_bar=curr_bar,
                        portfolio=self._portfolio,
                        timestamp=ts_dt,
                    )
                    signal = strategy.on_bar(context)

                    if signal is not None:
                        await self._handle_signal(signal, step_size)

            # Check SL/TP on existing positions
            await self._check_stop_take(row, primary_tf, ts_dt)

            # Record equity
            self._equity_curve.record(ts_dt, self._portfolio.equity())

            if i % 500 == 0:
                logger.debug("backtest_progress", bar=i, total=total_bars)

        return self._generate_report()

    async def _handle_signal(self, signal: Signal, step_size: float) -> None:
        qty, rejection = self._risk_mgr.validate(
            signal, self._portfolio.cash + sum(
                p.entry_price * p.qty_filled for p in self._portfolio.open_positions.values()
            ),
            step_size=step_size,
        )
        if rejection:
            return

        idem_key = make_key(signal.strategy_id, signal.symbol, signal.direction, signal.timestamp)
        if self._portfolio.is_duplicate(idem_key):
            return

        side: str = "buy" if signal.direction == "long" else "sell"
        order_event = OrderEvent(
            symbol=signal.symbol,
            side=side,
            qty=qty,
            order_type="market",
            price=0.0,
            strategy_id=signal.strategy_id,
            idempotency_key=idem_key,
            timestamp=signal.timestamp,
        )
        # Attach signal to pending so we can open position on fill
        self._pending_signals.append((signal, qty))
        await self._broker.place_order(order_event)

    async def _on_fill(self, fill: FillEvent) -> None:
        # Find matching pending signal (works for both long and short opens)
        matched_signal = None
        for sig, qty in self._pending_signals:
            if sig.symbol == fill.symbol and sig.strategy_id == fill.strategy_id:
                matched_signal = sig
                break
        if matched_signal:
            _adjust_signal_for_gap(matched_signal, fill.avg_price)
            self._portfolio.open_position(fill, matched_signal)
            self._pending_signals = [
                (s, q) for s, q in self._pending_signals
                if not (s.symbol == fill.symbol and s.strategy_id == fill.strategy_id)
            ]
        else:
            self._portfolio.close_position(fill)

    async def _process_fill(self, fill: FillEvent, symbol: str) -> None:
        pass  # handled via callback

    async def _check_stop_take(self, row: pd.Series, tf: str, ts: datetime) -> None:
        """Check if any open positions hit SL or TP on this bar.

        When both SL and TP are touched on the same bar we use the bar direction
        (close vs open) as a heuristic: a bullish bar (close > open) means price
        rose first → TP wins for longs, SL wins for shorts; a bearish bar means
        the opposite.  This avoids the systematic pessimism of always preferring SL.
        """
        for sym, pos in list(self._portfolio.open_positions.items()):
            bar_open = float(row.get("open", row.get("close", 0)))
            bar_high = float(row.get("high", row.get("close", 0)))
            bar_low = float(row.get("low", row.get("close", 0)))
            bar_close = float(row.get("close", 0))

            hit_sl = hit_tp = False
            if pos.side == "long":
                hit_sl = bar_low <= pos.stop_loss
                hit_tp = bar_high >= pos.take_profit
            else:
                hit_sl = bar_high >= pos.stop_loss
                hit_tp = bar_low <= pos.take_profit

            if not (hit_sl or hit_tp):
                continue

            # Determine exit price using bar-direction heuristic for ambiguous bars
            if hit_sl and hit_tp:
                bullish_bar = bar_close >= bar_open
                if pos.side == "long":
                    exit_price = pos.take_profit if bullish_bar else pos.stop_loss
                else:
                    exit_price = pos.take_profit if not bullish_bar else pos.stop_loss
            elif hit_tp:
                exit_price = pos.take_profit
            else:
                exit_price = pos.stop_loss

            fee = exit_price * pos.qty_filled * self._bcfg.fee_schedule.taker
            fill = FillEvent(
                order_id=f"exit_{sym}_{ts.timestamp():.0f}",
                symbol=sym,
                side="sell" if pos.side == "long" else "buy",
                qty_filled=pos.qty_filled,
                avg_price=exit_price,
                fee_paid=fee,
                timestamp=ts,
                strategy_id=pos.strategy_id,
            )
            self._portfolio.close_position(fill)

    def _generate_report(self) -> dict:
        trades = self._portfolio.tracker.closed_trades
        equity_values = [eq for _, eq in self._equity_curve._snapshots]
        metrics = compute_metrics(trades, self._rcfg.capital_usd, equity_values)

        self._output_dir.mkdir(parents=True, exist_ok=True)
        save_trade_log(trades, self._output_dir / "trade_log.csv")
        self._equity_curve.to_csv(self._output_dir / "equity_curve.csv")
        save_summary(metrics, self._output_dir / "summary.json")

        logger.info("backtest_complete", **{k: v for k, v in metrics.items() if isinstance(v, (int, float, str))})

        if self._brain is not None:
            brain_summary = self._brain.get_summary()
            save_summary(brain_summary, self._output_dir / "brain_summary.json")
            logger.info("brain_session_summary", **{
                "regime": brain_summary["regime"],
                "total_decisions": brain_summary["decisions"]["total_decisions"],
                "action_counts": brain_summary["decisions"]["action_counts"],
            })

        return metrics


def _row_to_bar(ts: datetime, row: pd.Series, symbol: str, tf: str, source: str = "backtest") -> OHLCVBar:
    return OHLCVBar(
        symbol=symbol,
        timeframe=tf,
        timestamp=ts if ts.tzinfo else ts.replace(tzinfo=timezone.utc),
        open=float(row.get("open", row.iloc[0])),
        high=float(row.get("high", row.iloc[0])),
        low=float(row.get("low", row.iloc[0])),
        close=float(row.get("close", row.iloc[3])),
        volume=float(row.get("volume", 0)),
        source=source,
    )


def _adjust_signal_for_gap(signal: "Signal", fill_price: float) -> None:
    """Shift SL/TP so they stay on the correct side of the actual fill price."""
    if signal.entry_price <= 0:
        return
    gap = fill_price - signal.entry_price
    signal.stop_loss += gap
    signal.take_profit += gap
    signal.entry_price = fill_price


def _df_to_bars(df: pd.DataFrame, symbol: str, tf: str) -> list[OHLCVBar]:
    bars = []
    for ts, row in df.iterrows():
        ts_dt = ts.to_pydatetime() if hasattr(ts, "to_pydatetime") else ts
        bars.append(_row_to_bar(ts_dt, row, symbol, tf))
    return bars
