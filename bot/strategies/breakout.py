"""
Breakout Strategy — Phase 4
Entry: Price closes above N-bar resistance (long) or below N-bar support (short)
with volume confirmation (> lookback_avg_volume * multiplier).
"""
from __future__ import annotations

from typing import Optional

import pandas as pd

from bot.core.events import Signal
from bot.core.config import StrategyConfig
from bot.strategies.base import BaseStrategy, StrategyContext
from bot.utils.indicators import atr as calc_atr


class BreakoutStrategy(BaseStrategy):
    def __init__(self, config: StrategyConfig) -> None:
        super().__init__(config)
        self._lookback: int = int(config.model_extra.get("lookback_bars", 20))
        self._confirm_bars: int = int(config.model_extra.get("confirmation_bars", 2))
        self._vol_surge: float = float(config.model_extra.get("volume_surge_multiplier", 1.5))

    def _init_symbol_state(self):
        return {"bar_count": 0, "bull_count": 0, "bear_count": 0}

    def on_bar(self, context: StrategyContext) -> Optional[Signal]:
        symbol = context.symbol
        self._increment_bar_count(symbol)

        if not self.is_warmed_up(symbol):
            return None

        if context.portfolio.has_position(symbol):
            return None

        signal_tf = self.config.timeframes.get("signal", "4h")
        df = context.bars.get(signal_tf)
        if df is None or len(df) < self._lookback + self._confirm_bars + 2:
            return None

        # Lookback excludes current bar to avoid lookahead
        lookback_window = df.iloc[-(self._lookback + 1):-1]
        resistance = float(lookback_window["high"].max())
        support = float(lookback_window["low"].min())
        avg_volume = float(lookback_window["volume"].mean())

        curr = df.iloc[-1]
        curr_close = float(curr["close"])
        curr_volume = float(curr["volume"])

        state = self._symbol_state[symbol]

        try:
            atr_series = calc_atr(df["high"], df["low"], df["close"], 14)
            atr_val = float(atr_series.iloc[-1])
            if pd.isna(atr_val) or atr_val <= 0:
                atr_val = (resistance - support) * 0.1
        except Exception:
            atr_val = (resistance - support) * 0.1

        if curr_close > resistance:
            state["bull_count"] += 1
            state["bear_count"] = 0
        elif curr_close < support:
            state["bear_count"] += 1
            state["bull_count"] = 0
        else:
            state["bull_count"] = 0
            state["bear_count"] = 0
            return None

        volume_ok = avg_volume > 0 and curr_volume >= avg_volume * self._vol_surge

        if state["bull_count"] >= self._confirm_bars and volume_ok:
            entry = curr_close
            stop_loss = resistance - atr_val * 0.5
            take_profit = entry + self.config.take_profit_r * (entry - stop_loss)
            state["bull_count"] = 0
            if stop_loss <= 0:
                return None
            return Signal(
                strategy_id=self.strategy_id,
                symbol=symbol,
                direction="long",
                strength=min(curr_volume / (avg_volume * self._vol_surge), 1.0),
                entry_price=entry,
                stop_loss=stop_loss,
                take_profit=take_profit,
                timeframe=signal_tf,
                timestamp=context.timestamp,
                metadata={"resistance": round(resistance, 6), "volume_ratio": round(curr_volume / avg_volume, 2)},
            )

        if state["bear_count"] >= self._confirm_bars and volume_ok:
            entry = curr_close
            stop_loss = support + atr_val * 0.5
            take_profit = entry - self.config.take_profit_r * (stop_loss - entry)
            state["bear_count"] = 0
            if take_profit <= 0:
                return None
            return Signal(
                strategy_id=self.strategy_id,
                symbol=symbol,
                direction="short",
                strength=min(curr_volume / (avg_volume * self._vol_surge), 1.0),
                entry_price=entry,
                stop_loss=stop_loss,
                take_profit=take_profit,
                timeframe=signal_tf,
                timestamp=context.timestamp,
                metadata={"support": round(support, 6), "volume_ratio": round(curr_volume / avg_volume, 2)},
            )

        return None
