"""
TradingEngine — owns the main event loop, wires all components together.
Mode-switches between BACKTEST, PAPER, and LIVE via injected broker/clock.
"""
from __future__ import annotations

import asyncio
import os
import sys
import structlog
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

from bot.core.clock import Clock, WallClock
from bot.core.config import BrokerConfig, RiskConfig
from bot.core.events import FillEvent, MarketEvent, OHLCVBar, OrderEvent, RejectionEvent, Signal
from bot.core.modes import ExecutionMode, RiskMode
from bot.data.base import AbstractDataFeed
from bot.data.feed_crypto import CryptoFeed
from bot.data.timeframe_manager import TimeframeManager
from bot.execution.base import AbstractBroker
from bot.execution.fee_model import FeeModel
from bot.execution.paper import PaperBroker
from bot.portfolio.manager import PortfolioManager
from bot.reporting.alerts import send_circuit_breaker_alert, send_daily_summary, send_fill_alert
from bot.reporting.equity_curve import EquityCurve
from bot.reporting.prometheus import TradingMetrics
from bot.risk.circuit_breaker import KillSwitch
from bot.risk.manager import RiskManager
from bot.brain.engine import BrainEngine
from bot.strategies.base import BaseStrategy, StrategyContext
from bot.utils.idempotency import make_key

logger = structlog.get_logger(__name__)


class TradingEngine:
    def __init__(
        self,
        risk_config: RiskConfig,
        broker_config: BrokerConfig,
        broker: AbstractBroker,
        strategies: list[BaseStrategy],
        execution_mode: ExecutionMode = ExecutionMode.PAPER,
        clock: Optional[Clock] = None,
        enable_prometheus: bool = True,
        prometheus_port: int = 8000,
        status_interval_seconds: int = 300,
        data_feed: Optional[AbstractDataFeed] = None,
        enable_brain: bool = True,
        brain_interval_bars: int = 50,
        brain_state_path: str = "reports/brain_state.json",
        warmup_data: Optional[dict[str, dict[str, "pd.DataFrame"]]] = None,
    ) -> None:
        self._rcfg = risk_config
        self._bcfg = broker_config
        self._broker = broker
        self._strategies = strategies
        self._mode = execution_mode
        self._clock = clock or WallClock()

        # Asset class map: symbol → "crypto" | "stocks"
        asset_map: dict[str, str] = {}
        for s in self._strategies:
            cls = broker_config.asset_class
            for sym in s.config.symbols:
                asset_map[sym] = cls

        self._portfolio = PortfolioManager(
            initial_cash=risk_config.capital_usd,
            asset_class_map=asset_map,
        )
        self._risk_mgr = RiskManager(risk_config, broker_config, self._portfolio)
        self._fee_model = FeeModel(broker_config)
        self._tf_manager = TimeframeManager(
            list({tf for s in strategies for tf in s.config.timeframes.values()})
        )
        self._equity_curve = EquityCurve()
        self._metrics: Optional[TradingMetrics] = None
        self._pending_signals: dict[str, tuple[Signal, float]] = {}  # idempotency_key → (signal, qty)
        self._alerted_circuit_breakers: set[str] = set()
        self._running = False
        self._stale_check_interval = risk_config.stale_order_timeout_minutes * 60
        self._status_interval = status_interval_seconds
        self._data_feed: Optional[AbstractDataFeed] = data_feed
        self._background_tasks: list[asyncio.Task] = []
        self._warmup_data = warmup_data  # {symbol → {tf → DataFrame}} for pre-warming indicators

        if isinstance(broker, PaperBroker):
            broker.register_fill_callback(self._on_fill)

        for strategy in self._strategies:
            strategy.initialize(self._portfolio)

        self._brain: Optional[BrainEngine] = (
            BrainEngine(
                strategies=strategies,
                portfolio=self._portfolio,
                risk_manager=self._risk_mgr,
                assessment_interval_bars=brain_interval_bars,
                state_path=Path(brain_state_path),
            )
            if enable_brain
            else None
        )
        # Accumulate bars for the Brain's regime detector
        self._brain_price_bars: list[float] = []

        if enable_prometheus:
            try:
                self._metrics = TradingMetrics()
                self._metrics.start_server(prometheus_port)
            except Exception as e:
                logger.warning("prometheus_start_failed", error=str(e))

    # ------------------------------------------------------------------
    # Main run loop
    # ------------------------------------------------------------------

    async def run(self) -> None:
        self._running = True
        await self._broker.start()

        # Sync positions on startup (handles container restart mid-trade)
        await self._sync_positions_on_startup()

        # Pre-warm indicator buffers from historical data so strategies
        # don't trade blind for the first 50+ bars after startup.
        if self._warmup_data:
            self._pre_warm_from_data(self._warmup_data)

        self._background_tasks = [
            asyncio.create_task(self._stale_order_monitor()),
            asyncio.create_task(self._daily_reset_loop()),
            asyncio.create_task(self._status_reporter()),
        ]

        logger.info(
            "engine_started",
            mode=self._mode.value,
            strategies=[s.strategy_id for s in self._strategies],
        )

        feeds = []
        for strategy in self._strategies:
            for sym in strategy.config.symbols:
                for tf in strategy.config.timeframes.values():
                    feeds.append(asyncio.create_task(self._consume_feed(sym, tf)))

        try:
            await asyncio.gather(*feeds)
        except asyncio.CancelledError:
            pass
        finally:
            for task in self._background_tasks:
                task.cancel()
            if self._background_tasks:
                await asyncio.gather(*self._background_tasks, return_exceptions=True)
            self._background_tasks.clear()
            await self._broker.stop()
            logger.info("engine_stopped")

    def _pre_warm_from_data(
        self,
        warmup_data: "dict[str, dict[str, pd.DataFrame]]",
    ) -> None:
        """Pre-fill TimeframeManager buffers from historical DataFrames.

        warmup_data: {symbol → {timeframe → DataFrame (timestamp index)}}
        Called once at startup so indicators (EMA50, ATR, etc.) are ready
        before the first live bar arrives.
        """
        import pandas as pd  # local import keeps top-level clean
        total_bars = 0
        for symbol, tf_map in warmup_data.items():
            for tf, df in tf_map.items():
                bars: list[OHLCVBar] = []
                for ts, row in df.iterrows():
                    ts_dt = ts.to_pydatetime() if hasattr(ts, "to_pydatetime") else ts
                    bars.append(OHLCVBar(
                        symbol=symbol,
                        timeframe=tf,
                        timestamp=ts_dt,
                        open=float(row["open"]),
                        high=float(row["high"]),
                        low=float(row["low"]),
                        close=float(row["close"]),
                        volume=float(row["volume"]),
                        source="warmup",
                    ))
                if bars:
                    self._tf_manager.pre_warm(symbol, tf, bars)
                    total_bars += len(bars)
        logger.info("indicator_warmup_complete", total_bars=total_bars, symbols=list(warmup_data))

    async def _consume_feed(self, symbol: str, timeframe: str) -> None:
        if self._data_feed is not None:
            feed = self._data_feed
        else:
            testnet = os.environ.get("BINANCE_TESTNET", "true").lower() == "true"
            feed = CryptoFeed(testnet=testnet)
        async for bar in feed.stream_bars(symbol, timeframe):
            await self._on_bar(bar)

    async def _on_bar(self, bar: OHLCVBar) -> None:
        if KillSwitch.is_active():
            logger.critical("kill_switch_active_emergency_close")
            await self._emergency_close_all()
            sys.exit(1)

        self._tf_manager.update(bar)

        # Trailing stop updates and paper-SL/TP checks only on the signal timeframe.
        # Trend (1D) bars must NOT update stops — they run at a different pace and
        # would create phantom price levels far from the actual execution timeframe.
        is_signal_tf = any(
            bar.timeframe == s.config.timeframes.get("signal", "1h")
            for s in self._strategies
            if bar.symbol in s.config.symbols
        )
        if is_signal_tf:
            self._equity_curve.record(self._clock.now(), self._portfolio.equity())
            self._portfolio.update_on_bar(bar)
            if isinstance(self._broker, PaperBroker):
                await self._check_paper_stops(bar)

        # Process pending order fills on signal TF bars only
        if is_signal_tf and isinstance(self._broker, PaperBroker):
            await self._broker.on_bar(bar)

        # Update metrics
        if self._metrics:
            equity = self._portfolio.equity()
            self._metrics.equity.labels(mode=self._mode.value).set(equity)
            self._metrics.daily_pnl.set(self._portfolio.daily_net_pnl())

        # Feed the Brain a price DataFrame for regime detection + assessment
        if self._brain is not None:
            price_df = self._tf_manager.get_dataframe(bar.symbol, bar.timeframe)
            self._brain.on_bar(price_df)

        # Dispatch to all strategies
        for strategy in self._strategies:
            if bar.symbol not in strategy.config.symbols:
                continue
            signal_tf = strategy.config.timeframes.get("signal", "1h")
            if bar.timeframe != signal_tf:
                continue

            # Brain may have disabled this strategy
            if self._brain is not None and not self._brain.is_strategy_enabled(strategy.strategy_id):
                continue

            bars_dict: dict[str, "pd.DataFrame"] = {}
            for tf in strategy.config.timeframes.values():
                bars_dict[tf] = self._tf_manager.get_dataframe(bar.symbol, tf)

            context = StrategyContext(
                symbol=bar.symbol,
                bars=bars_dict,
                current_bar=bar,
                portfolio=self._portfolio,
                timestamp=self._clock.now(),
            )

            signal = strategy.on_bar(context)
            if signal is not None:
                await self._handle_signal(signal, strategy)

    async def _handle_signal(self, signal: Signal, strategy: BaseStrategy) -> None:
        capital = self._portfolio.equity()
        qty, rejection = self._risk_mgr.validate(signal, capital)

        if rejection:
            strategy.on_rejected(rejection)
            if self._metrics:
                self._metrics.rejections_total.labels(
                    reason=rejection.reason.split(":")[0]
                ).inc()
            _CIRCUIT_BREAKER_REASONS = {"daily_loss_limit_breached", "losing_streak_halt", "kill_switch_active"}
            if rejection.reason in _CIRCUIT_BREAKER_REASONS and rejection.reason not in self._alerted_circuit_breakers:
                self._alerted_circuit_breakers.add(rejection.reason)
                asyncio.create_task(send_circuit_breaker_alert(rejection.reason, capital))
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

        self._pending_signals[idem_key] = (signal, qty)
        try:
            await self._broker.place_order(order_event)
        except Exception as e:
            logger.error("order_placement_failed", symbol=signal.symbol, error=str(e))
            del self._pending_signals[idem_key]
            if self._metrics:
                self._metrics.api_errors_total.labels(broker=self._bcfg.name).inc()

    async def _on_fill(self, fill: FillEvent) -> None:
        idem_key = fill.idempotency_key
        pending = self._pending_signals.get(idem_key)

        if pending:
            # Opening fill — works for both long (buy) and short (sell)
            signal, _ = pending
            _adjust_signal_for_gap(signal, fill.avg_price)
            self._portfolio.open_position(fill, signal)
            del self._pending_signals[idem_key]
        else:
            # Closing fill — stop/TP auto-close or manual close
            self._portfolio.close_position(fill)

        # Notify strategy
        for strategy in self._strategies:
            if fill.strategy_id == strategy.strategy_id:
                strategy.on_fill(fill)

        if self._metrics:
            self._metrics.fills_total.labels(side=fill.side).inc()

        asyncio.create_task(send_fill_alert(
            fill.symbol, fill.side, fill.qty_filled, fill.avg_price, fill.fee_paid
        ))

        logger.info(
            "fill_processed",
            symbol=fill.symbol,
            side=fill.side,
            qty=fill.qty_filled,
            price=fill.avg_price,
            fee=fill.fee_paid,
        )

    # ------------------------------------------------------------------
    # Background tasks
    # ------------------------------------------------------------------

    async def _stale_order_monitor(self) -> None:
        while self._running:
            await asyncio.sleep(5 * 60)   # check every 5 minutes
            now = self._clock.now()
            timeout_secs = self._stale_check_interval
            for sym in list(self._pending_signals.keys()):
                signal, _ = self._pending_signals[sym]
                age = (now - signal.timestamp).total_seconds()
                if age > timeout_secs:
                    logger.warning("stale_order_cancelled", symbol=signal.symbol, age_seconds=age)
                    open_orders = await self._broker.get_open_orders(signal.symbol)
                    for order in open_orders:
                        await self._broker.cancel_order(order.order_id, order.symbol)
                    self._pending_signals.pop(sym, None)

    async def _daily_reset_loop(self) -> None:
        """Reset daily P&L and circuit breakers at UTC midnight; send Telegram summary."""
        while self._running:
            now = datetime.now(timezone.utc)
            midnight_secs = (24 - now.hour) * 3600 - now.minute * 60 - now.second
            await asyncio.sleep(max(midnight_secs, 1))

            equity = self._portfolio.equity()
            daily_pnl = self._portfolio.daily_net_pnl()
            open_pos = self._portfolio.open_position_count()
            win_rate = self._portfolio.tracker.win_rate()

            self._portfolio.reset_daily_pnl()
            self._risk_mgr.reset_daily()
            self._alerted_circuit_breakers.clear()
            logger.info("daily_reset_complete")

            asyncio.create_task(
                send_daily_summary(equity, daily_pnl, open_pos, win_rate, self._mode.value)
            )

    async def _sync_positions_on_startup(self) -> None:
        try:
            broker_positions = await self._broker.sync_positions()
            if broker_positions:
                logger.info("positions_synced_on_startup", count=len(broker_positions))
        except Exception as e:
            logger.warning("startup_sync_failed", error=str(e))

    async def _emergency_close_all(self) -> None:
        logger.critical("emergency_close_all_positions")
        for sym, pos in list(self._portfolio.open_positions.items()):
            try:
                open_orders = await self._broker.get_open_orders(sym)
                for order in open_orders:
                    await self._broker.cancel_order(order.order_id, sym)
                order_event = OrderEvent(
                    symbol=sym,
                    side="sell" if pos.side == "long" else "buy",
                    qty=pos.qty_filled,
                    order_type="market",
                    price=0.0,
                    strategy_id=pos.strategy_id,
                    idempotency_key=f"emergency_{sym}",
                    timestamp=self._clock.now(),
                )
                await self._broker.place_order(order_event)
                logger.info("emergency_close_sent", symbol=sym)
            except Exception as e:
                logger.error("emergency_close_failed", symbol=sym, error=str(e))

    async def _check_paper_stops(self, bar: OHLCVBar) -> None:
        """Auto-close paper positions when bar crosses stop-loss or take-profit."""
        pos = self._portfolio.open_positions.get(bar.symbol)
        if pos is None:
            return

        close_side = "sell" if pos.side == "long" else "buy"
        fill_price: Optional[float] = None
        reason: Optional[str] = None

        if pos.side == "long":
            if pos.take_profit and bar.high >= pos.take_profit:
                fill_price, reason = pos.take_profit, "take_profit"
            elif bar.low <= pos.stop_loss:
                fill_price, reason = pos.stop_loss, "stop_loss"
        else:
            if pos.take_profit and bar.low <= pos.take_profit:
                fill_price, reason = pos.take_profit, "take_profit"
            elif bar.high >= pos.stop_loss:
                fill_price, reason = pos.stop_loss, "stop_loss"

        if fill_price is None:
            return

        idem_key = f"auto_{reason}_{bar.symbol}_{bar.timestamp.timestamp():.0f}"
        logger.info(
            "paper_auto_close",
            symbol=bar.symbol,
            reason=reason,
            fill_price=round(fill_price, 4),
        )
        await self._broker.simulate_stop_fill(
            symbol=bar.symbol,
            side=close_side,
            qty=pos.qty_filled,
            fill_price=fill_price,
            strategy_id=pos.strategy_id,
            idempotency_key=idem_key,
            timestamp=bar.timestamp,
        )

    async def _status_reporter(self) -> None:
        """Emit a periodic equity / position snapshot to the log."""
        while self._running:
            await asyncio.sleep(self._status_interval)
            equity = self._portfolio.equity()
            pnl = self._portfolio.daily_net_pnl()
            positions = {
                sym: {
                    "side": p.side,
                    "entry": round(p.entry_price, 4),
                    "qty": p.qty_filled,
                    "sl": round(p.stop_loss, 4),
                    "tp": round(p.take_profit, 4),
                }
                for sym, p in self._portfolio.open_positions.items()
            }
            brain_info = self._brain.get_summary() if self._brain is not None else {}
            logger.info(
                "status_snapshot",
                equity_usd=round(equity, 2),
                daily_pnl_usd=round(pnl, 2),
                open_positions=len(positions),
                positions=positions,
                brain_regime=brain_info.get("regime", "n/a"),
                brain_enabled=brain_info.get("enabled_strategies", {}),
                brain_risk_modes=brain_info.get("risk_modes", {}),
                brain_decisions=brain_info.get("decisions", {}).get("total_decisions", 0),
            )

    def stop(self) -> None:
        self._running = False


def _adjust_signal_for_gap(signal: "Signal", fill_price: float) -> None:
    """Shift SL/TP by the fill-price gap so they stay on the correct side.

    Signals set SL/TP relative to the signal bar's close.  When the fill
    price (next-bar open) differs due to a gap, SL or TP can land on the
    wrong side of the actual entry, causing an instant stop-out.  Shifting
    both levels by the same gap preserves the risk distance.
    """
    if signal.entry_price <= 0:
        return
    gap = fill_price - signal.entry_price
    signal.stop_loss += gap
    signal.take_profit += gap
    signal.entry_price = fill_price
