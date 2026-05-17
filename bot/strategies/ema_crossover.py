"""
EMA Crossover Strategy — Phase 2
Entry: EMA fast crosses above/below EMA slow with ADX > threshold (trending market).
Uses signal_tf for signal generation, trend_tf for higher-timeframe confirmation.
"""
from __future__ import annotations

from typing import Optional

import pandas as pd

from bot.core.events import Signal
from bot.core.config import StrategyConfig
from bot.strategies.base import BaseStrategy, StrategyContext
from bot.utils.indicators import adx as calc_adx, atr as calc_atr, ema as calc_ema


class EMACrossoverStrategy(BaseStrategy):
    def __init__(self, config: StrategyConfig) -> None:
        super().__init__(config)
        self._ema_fast: int = int(config.model_extra.get("ema_fast", 9))
        self._ema_slow: int = int(config.model_extra.get("ema_slow", 21))
        self._adx_period: int = int(config.model_extra.get("adx_period", 14))
        self._adx_threshold: float = float(config.model_extra.get("adx_threshold", 25.0))

    def _init_symbol_state(self):
        return {"bar_count": 0}

    def on_bar(self, context: StrategyContext) -> Optional[Signal]:
        symbol = context.symbol
        self._increment_bar_count(symbol)

        if not self.is_warmed_up(symbol):
            return None

        if context.portfolio.has_position(symbol):
            return None

        signal_tf = self.config.timeframes.get("signal", "1h")
        df = context.bars.get(signal_tf)
        if df is None or len(df) < self._ema_slow + 5:
            return None

        df = self._compute_indicators(df)
        if df is None or len(df) < 2:
            return None

        curr = df.iloc[-1]
        prev = df.iloc[-2]

        if pd.isna(curr["ema_fast"]) or pd.isna(curr["ema_slow"]) or pd.isna(curr["adx"]):
            return None

        if curr["adx"] < self._adx_threshold:
            return None

        bullish_cross = prev["ema_fast"] <= prev["ema_slow"] and curr["ema_fast"] > curr["ema_slow"]
        bearish_cross = prev["ema_fast"] >= prev["ema_slow"] and curr["ema_fast"] < curr["ema_slow"]

        if not bullish_cross and not bearish_cross:
            return None

        entry = context.current_bar.close
        atr_val = curr.get("atr", entry * 0.01)
        if pd.isna(atr_val) or atr_val <= 0:
            atr_val = entry * 0.01

        if bullish_cross:
            stop_loss = entry - 1.5 * atr_val
            take_profit = entry + self.config.take_profit_r * 1.5 * atr_val
            direction = "long"
        else:
            stop_loss = entry + 1.5 * atr_val
            take_profit = entry - self.config.take_profit_r * 1.5 * atr_val
            direction = "short"

        if stop_loss <= 0 or take_profit <= 0:
            return None

        return Signal(
            strategy_id=self.strategy_id,
            symbol=symbol,
            direction=direction,
            strength=min(float(curr["adx"]) / 100.0, 1.0),
            entry_price=entry,
            stop_loss=stop_loss,
            take_profit=take_profit,
            timeframe=signal_tf,
            timestamp=context.timestamp,
            metadata={
                "ema_fast": round(float(curr["ema_fast"]), 6),
                "ema_slow": round(float(curr["ema_slow"]), 6),
                "adx": round(float(curr["adx"]), 2),
                "atr": round(float(atr_val), 6),
            },
        )

    def _compute_indicators(self, df: pd.DataFrame) -> Optional[pd.DataFrame]:
        try:
            df = df.copy()
            df["ema_fast"] = calc_ema(df["close"], self._ema_fast)
            df["ema_slow"] = calc_ema(df["close"], self._ema_slow)
            df["adx"] = calc_adx(df["high"], df["low"], df["close"], self._adx_period)
            df["atr"] = calc_atr(df["high"], df["low"], df["close"], self._adx_period)
            return df
        except Exception:
            return None
