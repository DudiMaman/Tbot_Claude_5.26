"""BaseStrategy ABC and StrategyContext — the contract all strategies implement."""
from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Optional

import pandas as pd

from bot.core.events import FillEvent, OHLCVBar, OrderEvent, RejectionEvent, Signal
from bot.core.config import StrategyConfig
from bot.portfolio.manager import PortfolioManager


@dataclass
class StrategyContext:
    symbol: str
    bars: dict[str, pd.DataFrame]        # {"1m": df, "1h": df, "1D": df}
    current_bar: OHLCVBar
    portfolio: PortfolioManager
    timestamp: datetime


class BaseStrategy(ABC):
    def __init__(self, config: StrategyConfig) -> None:
        self.strategy_id = config.strategy_id
        self.config = config
        self._symbol_state: dict[str, dict[str, Any]] = {}
        self._initialized = False

    def initialize(self, portfolio: PortfolioManager) -> None:
        for symbol in self.config.symbols:
            self._symbol_state[symbol] = self._init_symbol_state()
        self._initialized = True

    def _init_symbol_state(self) -> dict[str, Any]:
        """Override in subclasses to set up per-symbol state."""
        return {"bar_count": 0}

    def is_warmed_up(self, symbol: str) -> bool:
        state = self._symbol_state.get(symbol, {})
        return state.get("bar_count", 0) >= self.config.warmup_bars

    @abstractmethod
    def on_bar(self, context: StrategyContext) -> Optional[Signal]:
        """Generate a signal (or None) for the given context."""
        ...

    def on_fill(self, fill: FillEvent) -> None:
        """Called when one of our orders is filled. Override if needed."""

    def on_rejected(self, rejection: RejectionEvent) -> None:
        """Called when a signal is rejected by RiskManager. Override if needed."""

    def _increment_bar_count(self, symbol: str) -> None:
        self._symbol_state.setdefault(symbol, {"bar_count": 0})
        self._symbol_state[symbol]["bar_count"] += 1
