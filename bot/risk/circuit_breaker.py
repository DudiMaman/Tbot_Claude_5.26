"""Circuit breakers: daily loss limit, losing streak guard, and kill switch."""
from __future__ import annotations

import os
import structlog
from datetime import datetime, timezone
from pathlib import Path

from bot.core.config import RiskConfig
from bot.core.events import CircuitBreakerEvent
from bot.core.modes import RiskMode

logger = structlog.get_logger(__name__)

KILL_SWITCH_FILE = Path("KILL_SWITCH")


class KillSwitch:
    @staticmethod
    def is_active() -> bool:
        if os.environ.get("KILL_SWITCH", "0") == "1":
            return True
        return KILL_SWITCH_FILE.exists()

    @staticmethod
    def activate() -> None:
        KILL_SWITCH_FILE.touch()
        logger.critical("kill_switch_activated")

    @staticmethod
    def deactivate() -> None:
        KILL_SWITCH_FILE.unlink(missing_ok=True)
        logger.info("kill_switch_deactivated")


class DailyLossBreaker:
    def __init__(self, config: RiskConfig) -> None:
        self._config = config
        self._triggered = False

    def check(self, daily_net_pnl: float, capital: float) -> CircuitBreakerEvent | None:
        if self._triggered:
            return None
        limit = -capital * self._config.max_daily_loss_pct
        if daily_net_pnl <= limit:
            self._triggered = True
            event = CircuitBreakerEvent(
                reason="daily_loss_limit",
                trigger_value=daily_net_pnl,
                threshold=limit,
                timestamp=datetime.now(timezone.utc),
            )
            logger.critical(
                "daily_loss_limit_breached",
                daily_pnl=round(daily_net_pnl, 2),
                limit=round(limit, 2),
            )
            return event
        return None

    def reset(self) -> None:
        self._triggered = False

    @property
    def is_triggered(self) -> bool:
        return self._triggered


class LosingStreakGuard:
    def __init__(self, config: RiskConfig) -> None:
        self._config = config
        self._halted = False
        self._risk_mode = RiskMode.NORMAL
        self._halt_bars_remaining: int = 0

    def update(self, consecutive_losses: int) -> RiskMode:
        # Auto-reset halt after N bars of cool-down
        if self._halted and self._config.losing_streak_halt_reset_bars > 0:
            self._halt_bars_remaining -= 1
            if self._halt_bars_remaining <= 0:
                self._halted = False
                self._risk_mode = RiskMode.DEFENSIVE
                logger.info("losing_streak_halt_reset", mode="defensive")
                return self._risk_mode

        if consecutive_losses >= self._config.losing_streak_halt:
            if not self._halted:
                self._halted = True
                self._halt_bars_remaining = self._config.losing_streak_halt_reset_bars
                logger.error(
                    "losing_streak_halt",
                    consecutive_losses=consecutive_losses,
                    threshold=self._config.losing_streak_halt,
                )
            self._risk_mode = RiskMode.DEFENSIVE
        elif consecutive_losses >= self._config.losing_streak_defensive:
            self._halted = False
            self._risk_mode = RiskMode.DEFENSIVE
            logger.warning(
                "losing_streak_defensive",
                consecutive_losses=consecutive_losses,
                threshold=self._config.losing_streak_defensive,
            )
        else:
            self._halted = False
            self._risk_mode = RiskMode.NORMAL

        return self._risk_mode

    def reset(self) -> None:
        self._halted = False
        self._halt_bars_remaining = 0
        self._risk_mode = RiskMode.NORMAL

    @property
    def is_halted(self) -> bool:
        return self._halted

    @property
    def risk_mode(self) -> RiskMode:
        return self._risk_mode
