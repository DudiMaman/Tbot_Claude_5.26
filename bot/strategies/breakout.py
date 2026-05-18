"""
Breakout Strategy — Phase 4
Entry: Price closes above N-bar resistance (long) or below N-bar support (short).

Signal logic:
  1. Volume confirmation on the FIRST break bar (not the confirmation bar).
  2. Price must stay above resistance for `confirmation_bars` consecutive closes.
  3. 1D trend filter: only take long breakouts in daily uptrend; shorts in downtrend.
  4. ATR minimum: break must be at least 0.3× ATR above resistance (not a dust break).

Stop: resistance level ± 0.5×ATR (natural S/R stop)
TP:   entry + take_profit_r × risk_distance (3:1 default)
"""
from __future__ import annotations

from typing import Optional

import pandas as pd

from bot.core.events import Signal
from bot.core.config import StrategyConfig
from bot.strategies.base import BaseStrategy, StrategyContext
from bot.utils.indicators import atr as calc_atr, ema as calc_ema


_NO_FIXED_TP = 100.0


class BreakoutStrategy(BaseStrategy):
    def __init__(self, config: StrategyConfig) -> None:
        super().__init__(config)
        self._lookback: int = int(config.model_extra.get("lookback_bars", 20))
        self._confirm_bars: int = int(config.model_extra.get("confirmation_bars", 1))
        self._vol_surge: float = float(config.model_extra.get("volume_surge_multiplier", 1.3))
        self._atr_min_break: float = float(config.model_extra.get("atr_min_break", 0.15))
        self._atr_stop_mult: float = float(config.model_extra.get("atr_stop_multiplier", 2.0))
        self._trailing_stop_pct: Optional[float] = config.trailing_stop_pct

    def _init_symbol_state(self):
        return {
            "bar_count": 0,
            "bull_count": 0,
            "bear_count": 0,
            "volume_confirmed": False,  # volume check passed on first break bar
        }

    def on_bar(self, context: StrategyContext) -> Optional[Signal]:
        symbol = context.symbol
        self._increment_bar_count(symbol)

        if not self.is_warmed_up(symbol):
            return None

        if context.portfolio.has_position(symbol):
            return None

        signal_tf = self.config.timeframes.get("signal", "4h")
        df = context.bars.get(signal_tf)
        if df is None or len(df) < self._lookback + self._confirm_bars + 5:
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

        # 1D trend filter: only trade in direction of daily trend
        trend_tf = self.config.timeframes.get("trend", "1D")
        trend_df = context.bars.get(trend_tf)
        daily_uptrend: bool | None = None
        if trend_df is not None and len(trend_df) >= 50:
            ema50 = calc_ema(trend_df["close"], 50).iloc[-1]
            daily_uptrend = float(trend_df["close"].iloc[-1]) > float(ema50)

        # Minimum break distance: price must be meaningfully above resistance
        bull_break = curr_close > resistance and (curr_close - resistance) >= self._atr_min_break * atr_val
        bear_break = curr_close < support and (support - curr_close) >= self._atr_min_break * atr_val

        if bull_break:
            if state["bull_count"] == 0:
                # First break bar: check volume HERE (most important signal)
                state["volume_confirmed"] = avg_volume > 0 and curr_volume >= avg_volume * self._vol_surge
            state["bull_count"] += 1
            state["bear_count"] = 0
        elif bear_break:
            if state["bear_count"] == 0:
                state["volume_confirmed"] = avg_volume > 0 and curr_volume >= avg_volume * self._vol_surge
            state["bear_count"] += 1
            state["bull_count"] = 0
        else:
            state["bull_count"] = 0
            state["bear_count"] = 0
            state["volume_confirmed"] = False
            return None

        trailing_pct = self._trailing_stop_pct or 0.08

        if state["bull_count"] >= self._confirm_bars and state["volume_confirmed"]:
            if daily_uptrend is False:
                return None
            entry = curr_close
            stop_loss = entry - self._atr_stop_mult * atr_val
            if stop_loss <= 0:
                return None
            risk_dist = entry - stop_loss
            take_profit = (entry * 1e6 if self.config.take_profit_r >= _NO_FIXED_TP
                           else entry + self.config.take_profit_r * risk_dist)
            state["bull_count"] = 0
            state["volume_confirmed"] = False
            return Signal(
                strategy_id=self.strategy_id,
                symbol=symbol,
                direction="long",
                strength=min(curr_volume / max(avg_volume * self._vol_surge, 1), 1.0),
                entry_price=entry,
                stop_loss=stop_loss,
                take_profit=take_profit,
                timeframe=signal_tf,
                timestamp=context.timestamp,
                metadata={
                    "resistance": round(resistance, 6),
                    "volume_ratio": round(curr_volume / max(avg_volume, 1), 2),
                    "atr": round(atr_val, 6),
                    "trailing_stop_pct": trailing_pct,
                },
            )

        if state["bear_count"] >= self._confirm_bars and state["volume_confirmed"]:
            if daily_uptrend is True:
                return None
            entry = curr_close
            stop_loss = entry + self._atr_stop_mult * atr_val
            risk_dist = stop_loss - entry
            if risk_dist <= 0:
                return None
            take_profit = (entry / 1e6 if self.config.take_profit_r >= _NO_FIXED_TP
                           else entry - self.config.take_profit_r * risk_dist)
            state["bear_count"] = 0
            state["volume_confirmed"] = False
            if take_profit <= 0:
                return None
            return Signal(
                strategy_id=self.strategy_id,
                symbol=symbol,
                direction="short",
                strength=min(curr_volume / max(avg_volume * self._vol_surge, 1), 1.0),
                entry_price=entry,
                stop_loss=stop_loss,
                take_profit=take_profit,
                timeframe=signal_tf,
                timestamp=context.timestamp,
                metadata={
                    "support": round(support, 6),
                    "volume_ratio": round(curr_volume / max(avg_volume, 1), 2),
                    "atr": round(atr_val, 6),
                    "trailing_stop_pct": trailing_pct,
                },
            )

        return None
