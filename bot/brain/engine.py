"""
BrainEngine — autonomous meta-controller that sits above TradingEngine.

Responsibilities:
  • Monitor per-strategy performance in real time (rolling 20-trade window)
  • Detect current market regime from live price data
  • Every `assessment_interval` bars: evaluate each strategy and act
  • Actions: adjust risk mode, enable/disable strategy, tune parameters
  • Log every decision with full context for post-session audit

Integration:
  BrainEngine is called from BacktestEngine / TradingEngine on each bar via
  `brain.on_bar(price_df)`.  It reads closed trades from the shared
  PortfolioManager tracker and writes overrides back to live strategy
  instances and the RiskManager.
"""
from __future__ import annotations

import structlog
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

import pandas as pd

from bot.brain.allocator import StrategyAllocator
from bot.brain.monitor import PerformanceMonitor
from bot.brain.regime import MarketRegime, RegimeDetector
from bot.brain.state import BrainDecision, BrainState
from bot.core.modes import RiskMode
from bot.portfolio.manager import PortfolioManager
from bot.risk.manager import RiskManager
from bot.strategies.base import BaseStrategy

logger = structlog.get_logger(__name__)


class BrainEngine:
    """
    Autonomous meta-controller.  Drop into any engine by calling
    `brain.on_bar(price_df)` once per primary bar.
    """

    def __init__(
        self,
        strategies: list[BaseStrategy],
        portfolio: PortfolioManager,
        risk_manager: RiskManager,
        assessment_interval_bars: int = 50,
        state_path: Path = Path("reports/brain_state.json"),
        min_trades_for_assessment: int = 5,
        rolling_window: int = 20,
        regime_stability_bars: int = 3,
    ) -> None:
        self._strategies: dict[str, BaseStrategy] = {s.strategy_id: s for s in strategies}
        self._portfolio = portfolio
        self._risk_manager = risk_manager
        self._interval = assessment_interval_bars

        self._monitor = PerformanceMonitor(
            list(self._strategies.keys()), window=rolling_window
        )
        self._regime_detector = RegimeDetector()
        self._allocator = StrategyAllocator(min_trades=min_trades_for_assessment)
        self._state = BrainState(state_path)

        self._enabled: dict[str, bool] = {sid: True for sid in self._strategies}
        # `_current_regime` is the CONFIRMED regime (after hysteresis). The raw
        # classifier output is noisy and can flip every 1-2 bars — using the raw
        # value would spam logs/alerts and cause the brain to flip-flop on every
        # tick. We only update _current_regime when the same new regime has
        # been observed for `_stability_threshold` consecutive bars.
        self._current_regime: MarketRegime = MarketRegime.UNKNOWN
        self._stability_threshold = regime_stability_bars
        self._pending_regime: Optional[MarketRegime] = None
        self._pending_count: int = 0
        self._bar_count: int = 0

        # Snapshot initial config values — Brain may only widen trailing stops,
        # never narrow them below the strategy's configured floor.
        self._initial_trailing_stops: dict[str, float] = {
            sid: float(getattr(s, "_trailing_stop_pct", 0.0) or 0.0)
            for sid, s in self._strategies.items()
        }

    # ------------------------------------------------------------------
    # Public interface — called by engine on every primary bar
    # ------------------------------------------------------------------

    def on_bar(self, price_df: Optional[pd.DataFrame]) -> None:
        self._bar_count += 1

        # Ingest any newly closed trades from the shared tracker
        self._monitor.ingest_new_trades(self._portfolio.tracker.closed_trades)

        # Update regime estimate from price data (with hysteresis)
        if price_df is not None and len(price_df) >= 105:
            raw_regime = self._regime_detector.detect(price_df)
            self._maybe_confirm_regime(raw_regime)

        # Run full assessment on schedule
        if self._bar_count % self._interval == 0:
            self._assess_and_act()

    def _maybe_confirm_regime(self, raw: MarketRegime) -> None:
        """Apply hysteresis: only commit a new regime once it's been observed
        for `_stability_threshold` consecutive bars. The raw classifier is
        noisy and can flip every 1-2 bars; without this filter, the brain
        would react to noise and Telegram alerts would fire constantly.
        """
        if raw == self._current_regime:
            self._pending_regime = None
            self._pending_count = 0
            return
        if raw == self._pending_regime:
            self._pending_count += 1
        else:
            self._pending_regime = raw
            self._pending_count = 1
        if self._pending_count >= self._stability_threshold:
            previous = self._current_regime
            self._current_regime = raw
            self._pending_regime = None
            self._pending_count = 0
            self._notify_regime_change(previous, self._current_regime)

    def is_strategy_enabled(self, strategy_id: str) -> bool:
        """Called by the engine before dispatching a bar to a strategy."""
        return self._enabled.get(strategy_id, True)

    def get_summary(self) -> dict:
        return {
            "bar_count": self._bar_count,
            "regime": self._current_regime.value,
            "regime_description": self._regime_detector.describe(self._current_regime),
            "enabled_strategies": dict(self._enabled),
            "risk_modes": self._risk_manager.strategy_risk_modes(),
            "metrics": self._monitor.to_dict(),
            "decisions": self._state.to_summary(),
        }

    # ------------------------------------------------------------------
    # Regime transition notifications (Telegram + structured log)
    # ------------------------------------------------------------------

    _MOMENTUM_FAVORABLE = {
        MarketRegime.TRENDING_UP,
        MarketRegime.TRENDING_DOWN,
        MarketRegime.HIGH_VOL,
    }

    def _notify_regime_change(
        self, before: MarketRegime, after: MarketRegime
    ) -> None:
        logger.info(
            "regime_change",
            before=before.value,
            after=after.value,
            bar=self._bar_count,
            favorable_for_momentum=after in self._MOMENTUM_FAVORABLE,
        )

        if after in self._MOMENTUM_FAVORABLE:
            icon, note = "🟢", "Momentum strategies favorable"
        elif after == MarketRegime.RANGING:
            icon, note = "🟡", "Ranging market — momentum stays flat"
        else:
            icon, note = "⚪", ""

        msg_lines = [
            f"{icon} *Market regime change*",
            f"`{before.value}` → `{after.value}`",
        ]
        if note:
            msg_lines.append(f"_{note}_")
        msg = "\n".join(msg_lines)

        # Fire-and-forget Telegram alert (silently no-ops if creds unset
        # or no running event loop)
        try:
            import asyncio
            from bot.reporting.alerts import send_telegram
            loop = asyncio.get_event_loop()
            if loop.is_running():
                asyncio.create_task(send_telegram(msg))
        except Exception:
            pass

    # ------------------------------------------------------------------
    # Internal assessment loop
    # ------------------------------------------------------------------

    def _assess_and_act(self) -> None:
        metrics_snapshot = self._monitor.to_dict()
        equity = self._portfolio.equity()

        logger.info(
            "brain_assessment",
            bar=self._bar_count,
            regime=self._current_regime.value,
            equity_usd=round(equity, 2),
            metrics=metrics_snapshot,
        )

        for sid in self._strategies:
            metrics = self._monitor.get_metrics(sid)
            if metrics is None:
                continue

            decision = self._allocator.decide(
                strategy_id=sid,
                metrics=metrics,
                regime=self._current_regime,
                currently_enabled=self._enabled[sid],
            )

            self._apply_risk_mode(sid, decision.risk_mode, decision.reason, metrics_snapshot)
            self._apply_enabled(sid, decision.enabled, decision.reason, metrics_snapshot)
            self._apply_param_overrides(
                sid, decision.param_overrides, decision.reason, metrics_snapshot
            )

    # ------------------------------------------------------------------
    # Action appliers — each checks for actual change before recording
    # ------------------------------------------------------------------

    def _apply_risk_mode(
        self,
        sid: str,
        new_mode: RiskMode,
        reason: str,
        metrics_snapshot: dict,
    ) -> None:
        current = self._risk_manager.get_risk_mode(sid)
        if current == new_mode:
            return
        self._risk_manager.set_risk_mode(sid, new_mode)
        self._record(
            sid=sid,
            action="set_risk_mode",
            reason=reason,
            before={"risk_mode": current.value},
            after={"risk_mode": new_mode.value},
            metrics_snapshot=metrics_snapshot.get(sid, {}),
        )
        logger.info(
            "brain_action",
            action="set_risk_mode",
            strategy=sid,
            before=current.value,
            after=new_mode.value,
            reason=reason,
            regime=self._current_regime.value,
        )

    def _apply_enabled(
        self,
        sid: str,
        enabled: bool,
        reason: str,
        metrics_snapshot: dict,
    ) -> None:
        if self._enabled[sid] == enabled:
            return
        action = "enable_strategy" if enabled else "disable_strategy"
        self._enabled[sid] = enabled
        self._record(
            sid=sid,
            action=action,
            reason=reason,
            before={"enabled": not enabled},
            after={"enabled": enabled},
            metrics_snapshot=metrics_snapshot.get(sid, {}),
        )
        level = logger.info if enabled else logger.warning
        level(
            "brain_action",
            action=action,
            strategy=sid,
            reason=reason,
            regime=self._current_regime.value,
        )

    def _apply_param_overrides(
        self,
        sid: str,
        overrides: dict[str, float],
        reason: str,
        metrics_snapshot: dict,
    ) -> None:
        strategy = self._strategies.get(sid)
        if not strategy or not overrides:
            return

        changed: dict[str, dict] = {}
        for param, new_val in overrides.items():
            attr = f"_{param}"
            current_val = getattr(strategy, attr, None)
            if current_val is None:
                continue
            # Never narrow trailing_stop_pct below the strategy's configured floor.
            # The Brain may widen stops to ride big moves but must not tighten
            # them past the minimum the user set (e.g. 10% for momentum_sniper).
            if param == "trailing_stop_pct":
                floor = self._initial_trailing_stops.get(sid, 0.0)
                new_val = max(float(new_val), floor)
            if abs(float(current_val) - float(new_val)) < 1e-9:
                continue
            setattr(strategy, attr, type(current_val)(new_val))
            changed[param] = {"before": current_val, "after": new_val}

        if not changed:
            return

        self._record(
            sid=sid,
            action="set_param",
            reason=reason,
            before={k: v["before"] for k, v in changed.items()},
            after={k: v["after"] for k, v in changed.items()},
            metrics_snapshot=metrics_snapshot.get(sid, {}),
        )
        logger.info(
            "brain_action",
            action="set_param",
            strategy=sid,
            changes=changed,
            reason=reason,
            regime=self._current_regime.value,
        )

    def _record(
        self,
        sid: str,
        action: str,
        reason: str,
        before: dict,
        after: dict,
        metrics_snapshot: dict,
    ) -> None:
        self._state.record(
            BrainDecision(
                timestamp=datetime.now(timezone.utc).isoformat(),
                strategy_id=sid,
                action=action,
                reason=reason,
                before=before,
                after=after,
                regime=self._current_regime.value,
                metrics_snapshot=metrics_snapshot,
            )
        )
