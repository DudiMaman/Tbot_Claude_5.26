"""
Mean Reversion Strategy — Phase 4
Entry: RSI oversold + price at lower Bollinger Band (long)
       RSI overbought + price at upper Bollinger Band (short)
"""
from __future__ import annotations

from typing import Optional

import pandas as pd

from bot.core.events import Signal
from bot.core.config import StrategyConfig
from bot.strategies.base import BaseStrategy, StrategyContext
from bot.utils.indicators import atr as calc_atr, bollinger_bands, ema as calc_ema, rsi as calc_rsi


class MeanReversionStrategy(BaseStrategy):
    def __init__(self, config: StrategyConfig) -> None:
        super().__init__(config)
        self._rsi_period: int = int(config.model_extra.get("rsi_period", 14))
        self._rsi_oversold: float = float(config.model_extra.get("rsi_oversold", 30))
        self._rsi_overbought: float = float(config.model_extra.get("rsi_overbought", 70))
        self._bb_period: int = int(config.model_extra.get("bb_period", 20))
        self._bb_std: float = float(config.model_extra.get("bb_std", 2.0))
        self._atr_multiplier: float = float(config.model_extra.get("atr_multiplier", 2.0))

    def on_bar(self, context: StrategyContext) -> Optional[Signal]:
        symbol = context.symbol
        self._increment_bar_count(symbol)

        if not self.is_warmed_up(symbol):
            return None

        if context.portfolio.has_position(symbol):
            return None

        signal_tf = self.config.timeframes.get("signal", "1h")
        df = context.bars.get(signal_tf)
        if df is None or len(df) < max(self._rsi_period, self._bb_period) + 5:
            return None

        try:
            df = df.copy()
            df["rsi"] = calc_rsi(df["close"], self._rsi_period)
            bb = bollinger_bands(df["close"], self._bb_period, self._bb_std)
            df = pd.concat([df, bb], axis=1)
            df["atr"] = calc_atr(df["high"], df["low"], df["close"], 14)
        except Exception:
            return None

        curr = df.iloc[-1]
        if pd.isna(curr.get("rsi")) or pd.isna(curr.get("bb_lower")):
            return None

        # 1D trend filter — wait for full 50-bar warmup before trading.
        # When no trend TF is configured the filter is skipped entirely.
        trend_tf = self.config.timeframes.get("trend")
        daily_uptrend: bool | None = None
        if trend_tf is not None:
            trend_df = context.bars.get(trend_tf)
            if trend_df is None or len(trend_df) < 50:
                return None  # skip until 1D EMA50 is warmed up
            ema50 = calc_ema(trend_df["close"], 50).iloc[-1]
            daily_uptrend = float(trend_df["close"].iloc[-1]) > float(ema50)

        entry = context.current_bar.close
        atr_val = curr.get("atr", entry * 0.01)
        if pd.isna(atr_val) or atr_val <= 0:
            atr_val = entry * 0.01

        if curr["rsi"] < self._rsi_oversold and entry <= float(curr["bb_lower"]) * 1.005:
            if daily_uptrend is False:  # skip longs in confirmed downtrend
                return None
            stop_loss = entry - self._atr_multiplier * atr_val
            # TP at upper band = full band width, giving ~2-3R:R in most setups
            take_profit = float(curr["bb_upper"])
            if stop_loss <= 0 or take_profit <= entry:
                return None
            return Signal(
                strategy_id=self.strategy_id,
                symbol=symbol,
                direction="long",
                strength=(self._rsi_oversold - float(curr["rsi"])) / self._rsi_oversold,
                entry_price=entry,
                stop_loss=stop_loss,
                take_profit=take_profit,
                timeframe=signal_tf,
                timestamp=context.timestamp,
                metadata={"rsi": round(float(curr["rsi"]), 2), "bb_lower": round(float(curr["bb_lower"]), 6)},
            )

        if curr["rsi"] > self._rsi_overbought and entry >= float(curr["bb_upper"]) * 0.995:
            if daily_uptrend is True:  # skip shorts in confirmed uptrend
                return None
            stop_loss = entry + self._atr_multiplier * atr_val
            # TP at lower band = full band width for short
            take_profit = float(curr["bb_lower"])
            if take_profit <= 0 or take_profit >= entry:
                return None
            return Signal(
                strategy_id=self.strategy_id,
                symbol=symbol,
                direction="short",
                strength=(float(curr["rsi"]) - self._rsi_overbought) / (100 - self._rsi_overbought),
                entry_price=entry,
                stop_loss=stop_loss,
                take_profit=take_profit,
                timeframe=signal_tf,
                timestamp=context.timestamp,
                metadata={"rsi": round(float(curr["rsi"]), 2), "bb_upper": round(float(curr["bb_upper"]), 6)},
            )

        return None
