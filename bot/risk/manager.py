"""
RiskManager — the single chokepoint all orders must pass through.
Every rule check returns a rejection reason or empty string on approval.
"""
from __future__ import annotations

import structlog
from datetime import datetime, timezone
from typing import Optional

from bot.core.config import BrokerConfig, RiskConfig
from bot.core.events import RejectionEvent, Signal
from bot.core.modes import RiskMode
from bot.execution.fee_model import FeeModel
from bot.portfolio.manager import PortfolioManager
from bot.risk.circuit_breaker import DailyLossBreaker, KillSwitch, LosingStreakGuard
from bot.risk.sizing import PositionSizer

logger = structlog.get_logger(__name__)


class RiskManager:
    def __init__(
        self,
        risk_config: RiskConfig,
        broker_config: BrokerConfig,
        portfolio: PortfolioManager,
    ) -> None:
        self._rcfg = risk_config
        self._bcfg = broker_config
        self._portfolio = portfolio
        self._fee_model = FeeModel(broker_config)
        self._sizer = PositionSizer(risk_config, broker_config)
        self._daily_breaker = DailyLossBreaker(risk_config)
        self._streak_guard = LosingStreakGuard(risk_config)
        self._risk_mode = RiskMode(risk_config.risk_mode)
        # Per-strategy overrides set by BrainEngine; fall back to global mode if absent
        self._strategy_risk_modes: dict[str, RiskMode] = {}

    # ------------------------------------------------------------------
    # Main validation entry point
    # ------------------------------------------------------------------

    def validate(
        self,
        signal: Signal,
        capital: float,
        current_prices: dict[str, float] | None = None,
        step_size: float = 0.0001,
    ) -> tuple[float, Optional[RejectionEvent]]:
        """
        Validate a signal against all risk rules.
        Returns (qty, None) on approval, or (0.0, RejectionEvent) on rejection.
        """
        now = datetime.now(timezone.utc)

        # 1. Kill switch
        if KillSwitch.is_active():
            return self._reject(signal, "kill_switch_active", now)

        # 2. Daily loss circuit breaker
        cb = self._daily_breaker.check(self._portfolio.daily_net_pnl(), capital)
        if cb:
            return self._reject(signal, "daily_loss_limit_breached", now)

        # 3. Losing streak guard
        self._risk_mode = self._streak_guard.update(self._portfolio.consecutive_losses())
        if self._streak_guard.is_halted:
            return self._reject(signal, "losing_streak_halt", now)

        # 4. Duplicate position / idempotency
        if self._portfolio.has_position(signal.symbol):
            if signal.direction not in ("close", "flat"):
                return self._reject(signal, "duplicate_position", now)

        if signal.direction in ("close", "flat"):
            return 0.0, None  # close signals bypass further checks

        # 5. Compute quantity — use per-strategy override if Brain has set one
        effective_mode = self._strategy_risk_modes.get(signal.strategy_id, self._risk_mode)
        qty, sizing_err = self._sizer.compute_qty(
            signal, capital, effective_mode, step_size,
            available_cash=self._portfolio.cash,
        )
        if sizing_err:
            return self._reject(signal, sizing_err, now)

        # 6. Fee-annotate the signal
        self._fee_model.annotate_signal(signal, qty)

        # 7. R:R gate after fees
        if signal.expected_r_after_fees < self._rcfg.min_r_after_fees:
            return self._reject(
                signal,
                f"insufficient_r_after_fees:{signal.expected_r_after_fees:.2f}<{self._rcfg.min_r_after_fees}",
                now,
            )

        # 8. Max open positions
        if self._portfolio.open_position_count() >= self._rcfg.max_open_positions:
            return self._reject(signal, "max_open_positions_reached", now)

        # 9. Per-trade risk in dollars
        risk_dollars = abs(signal.entry_price - signal.stop_loss) * qty
        max_risk = capital * self._rcfg.risk_per_trade_pct * 1.5   # 1.5× for min-notional size-up
        if risk_dollars > max_risk:
            return self._reject(signal, f"risk_exceeds_limit:{risk_dollars:.2f}>{max_risk:.2f}", now)

        # 10. Sufficient cash
        required_cash = qty * signal.entry_price
        if required_cash > self._portfolio.cash:
            return self._reject(signal, "insufficient_cash", now)

        # 11. Asset-class exposure limits
        if current_prices:
            notional = self._portfolio.notional_by_asset_class(current_prices)
            equity = self._portfolio.equity(current_prices)
            new_notional = qty * signal.entry_price
            asset_class = self._bcfg.asset_class

            if asset_class == "crypto":
                if (notional.get("crypto", 0) + new_notional) / equity > self._rcfg.max_crypto_exposure_pct:
                    return self._reject(signal, "crypto_exposure_limit", now)
            elif asset_class == "stocks":
                if (notional.get("stocks", 0) + new_notional) / equity > self._rcfg.max_stock_exposure_pct:
                    return self._reject(signal, "stock_exposure_limit", now)

        logger.debug(
            "signal_approved",
            symbol=signal.symbol,
            direction=signal.direction,
            qty=qty,
            expected_r=round(signal.expected_r_after_fees, 2),
            risk_mode=self._risk_mode.value,
        )
        return qty, None

    def _reject(
        self, signal: Signal, reason: str, now: datetime
    ) -> tuple[float, RejectionEvent]:
        logger.warning("signal_rejected", symbol=signal.symbol, reason=reason, strategy=signal.strategy_id)
        return 0.0, RejectionEvent(
            symbol=signal.symbol,
            strategy_id=signal.strategy_id,
            reason=reason,
            signal=signal,
            timestamp=now,
        )

    def reset_daily(self) -> None:
        self._daily_breaker.reset()

    def reset_streak(self) -> None:
        self._streak_guard.reset()

    # ------------------------------------------------------------------
    # Brain interface — per-strategy risk mode overrides
    # ------------------------------------------------------------------

    def set_risk_mode(self, strategy_id: str, mode: RiskMode) -> None:
        self._strategy_risk_modes[strategy_id] = mode

    def get_risk_mode(self, strategy_id: str) -> RiskMode:
        return self._strategy_risk_modes.get(strategy_id, self._risk_mode)

    def strategy_risk_modes(self) -> dict[str, str]:
        return {sid: mode.value for sid, mode in self._strategy_risk_modes.items()}

    @property
    def risk_mode(self) -> RiskMode:
        return self._risk_mode
