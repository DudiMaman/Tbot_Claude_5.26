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
from bot.data.feed_crypto import CryptoFeed
from bot.data.timeframe_manager import TimeframeManager
from bot.execution.base import AbstractBroker
from bot.execution.fee_model import FeeModel
from bot.execution.paper import PaperBroker
from bot.portfolio.manager import PortfolioManager
from bot.reporting.alerts import send_circuit_breaker_alert, send_fill_alert
from bot.reporting.equity_curve import EquityCurve
from bot.reporting.prometheus import TradingMetrics
from bot.risk.circuit_breaker import KillSwitch
from bot.risk.manager import RiskManager
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
        self._running = False
        self._stale_check_interval = risk_config.stale_order_timeout_minutes * 60

        if isinstance(broker, PaperBroker):
            broker.register_fill_callback(self._on_fill)

        for strategy in self._strategies:
            strategy.initialize(self._portfolio)

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

        asyncio.create_task(self._stale_order_monitor())
        asyncio.create_task(self._daily_reset_loop())

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
            await self._broker.stop()
            logger.info("engine_stopped")

    async def _consume_feed(self, symbol: str, timeframe: str) -> None:
        feed = CryptoFeed(testnet=os.environ.get("BINANCE_TESTNET", "true").lower() == "true")
        async for bar in feed.stream_bars(symbol, timeframe):
            await self._on_bar(bar)

    async def _on_bar(self, bar: OHLCVBar) -> None:
        if KillSwitch.is_active():
            logger.critical("kill_switch_active_emergency_close")
            await self._emergency_close_all()
            sys.exit(1)

        self._tf_manager.update(bar)
        self._equity_curve.record(self._clock.now(), self._portfolio.equity())

        # Update trailing stops
        self._portfolio.update_on_bar(bar)

        # Process pending fills from paper broker
        if isinstance(self._broker, PaperBroker):
            await self._broker.on_bar(bar)

        # Update metrics
        if self._metrics:
            equity = self._portfolio.equity()
            self._metrics.equity.labels(mode=self._mode.value).set(equity)
            self._metrics.daily_pnl.set(self._portfolio.daily_net_pnl())

        # Dispatch to all strategies
        for strategy in self._strategies:
            if bar.symbol not in strategy.config.symbols:
                continue
            signal_tf = strategy.config.timeframes.get("signal", "1h")
            if bar.timeframe != signal_tf:
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

        if fill.side == "buy" and pending:
            signal, _ = pending
            self._portfolio.open_position(fill, signal)
            del self._pending_signals[idem_key]
        elif fill.side == "sell":
            self._portfolio.close_position(fill)

        # Notify strategy
        for strategy in self._strategies:
            if fill.strategy_id == strategy.strategy_id:
                strategy.on_fill(fill)

        if self._metrics:
            self._metrics.fills_total.labels(side=fill.side).inc()

        if self._mode == ExecutionMode.LIVE:
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
        """Reset daily P&L and circuit breakers at UTC midnight."""
        import time as _time
        while self._running:
            now = datetime.now(timezone.utc)
            # Sleep until next UTC midnight
            midnight_secs = (24 - now.hour) * 3600 - now.minute * 60 - now.second
            await asyncio.sleep(midnight_secs)
            self._portfolio.reset_daily_pnl()
            self._risk_mgr.reset_daily()
            logger.info("daily_reset_complete")

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

    def stop(self) -> None:
        self._running = False
