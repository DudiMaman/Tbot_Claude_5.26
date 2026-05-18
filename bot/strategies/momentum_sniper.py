"""
Momentum Sniper Strategy
Entry: Price breaks out of N-bar high/low with volume surge + RSI momentum + EMA alignment.

Signal logic (LONG):
  1. Close breaks above N-bar (lookback=10) highest high (excluding current bar).
  2. Current volume >= 2.0x 20-bar average volume.
  3. RSI(14) between 50 and 72 (momentum building, not overbought).
  4. EMA9 > EMA21 on signal timeframe (short-term aligned bullish).
  5. 1h trend filter: close > EMA50 on 1h bars (optional, only if 1h data available).

Signal logic (SHORT): mirror image
  1. Close breaks below N-bar lowest low.
  2. Volume surge >= 2.0x.
  3. RSI between 28 and 50.
  4. EMA9 < EMA21.
  5. 1h trend: close < EMA50 on 1h.

Stop:  entry - 1.5 * ATR(14) for longs; entry + 1.5 * ATR(14) for shorts.
TP:    entry + take_profit_r * risk_distance (default take_profit_r=2.5).

Cooldown: minimum 3-bar gap between signals on same symbol to avoid rapid re-entry.
"""
from __future__ import annotations

from typing import Optional

import pandas as pd

from bot.core.events import Signal
from bot.core.config import StrategyConfig
from bot.strategies.base import BaseStrategy, StrategyContext
from bot.utils.indicators import atr as calc_atr, ema as calc_ema

# Try pandas-ta for RSI; fall back to manual implementation
try:
    import pandas_ta as ta  # type: ignore
    _HAS_PANDAS_TA = True
except ImportError:
    _HAS_PANDAS_TA = False


def _calc_rsi(series: pd.Series, length: int = 14) -> pd.Series:
    """RSI — uses pandas-ta if available, otherwise manual EWM implementation."""
    if _HAS_PANDAS_TA:
        try:
            result = ta.rsi(series, length)
            if result is not None and not result.isna().all():
                return result
        except Exception:
            pass
    # Manual fallback
    delta = series.diff()
    gain = delta.clip(lower=0).ewm(com=length - 1, adjust=False).mean()
    loss = (-delta.clip(upper=0)).ewm(com=length - 1, adjust=False).mean()
    rs = gain / loss.replace(0, float("nan"))
    return 100 - (100 / (1 + rs))


_NO_FIXED_TP = 100.0


class MomentumSniperStrategy(BaseStrategy):
    def __init__(self, config: StrategyConfig) -> None:
        super().__init__(config)
        self._lookback: int = int(config.model_extra.get("lookback_bars", 10))
        self._vol_surge: float = float(config.model_extra.get("volume_surge_multiplier", 2.0))
        self._rsi_min_long: float = float(config.model_extra.get("rsi_min_long", 50.0))
        self._rsi_max_long: float = float(config.model_extra.get("rsi_max_long", 72.0))
        self._rsi_min_short: float = float(config.model_extra.get("rsi_min_short", 28.0))
        self._rsi_max_short: float = float(config.model_extra.get("rsi_max_short", 50.0))
        self._atr_stop_mult: float = float(config.model_extra.get("atr_stop_multiplier", 1.5))
        self._cooldown_bars: int = int(config.model_extra.get("signal_cooldown_bars", 3))
        self._trailing_stop_pct: Optional[float] = config.trailing_stop_pct

    def _init_symbol_state(self):
        return {
            "bar_count": 0,
            "last_signal_bar": 0,
        }

    def on_bar(self, context: StrategyContext) -> Optional[Signal]:
        symbol = context.symbol
        self._increment_bar_count(symbol)

        if not self.is_warmed_up(symbol):
            return None

        if context.portfolio.has_position(symbol):
            return None

        signal_tf = self.config.timeframes.get("signal", "15m")
        df = context.bars.get(signal_tf)
        min_bars = self._lookback + 20 + 5  # lookback + vol_avg_window + buffer
        if df is None or len(df) < min_bars:
            return None

        state = self._symbol_state[symbol]
        current_bar = state["bar_count"]

        # Enforce cooldown between signals
        bars_since_signal = current_bar - state["last_signal_bar"]
        if bars_since_signal < self._cooldown_bars:
            return None

        curr = df.iloc[-1]
        curr_close = float(curr["close"])
        curr_volume = float(curr["volume"])

        # Lookback window excludes current bar (no lookahead)
        lookback_window = df.iloc[-(self._lookback + 1):-1]
        resistance = float(lookback_window["high"].max())
        support = float(lookback_window["low"].min())

        # 20-bar average volume (excluding current bar)
        avg_volume = float(df["volume"].iloc[-21:-1].mean())
        if avg_volume <= 0:
            return None

        volume_ratio = curr_volume / avg_volume
        volume_confirmed = volume_ratio >= self._vol_surge

        # ATR
        try:
            atr_series = calc_atr(df["high"], df["low"], df["close"], 14)
            atr_val = float(atr_series.iloc[-1])
            if pd.isna(atr_val) or atr_val <= 0:
                atr_val = (resistance - support) * 0.05
        except Exception:
            atr_val = (resistance - support) * 0.05

        # RSI
        try:
            rsi_series = _calc_rsi(df["close"], 14)
            rsi_val = float(rsi_series.iloc[-1])
        except Exception:
            rsi_val = float("nan")

        # EMA alignment
        ema9 = calc_ema(df["close"], 9).iloc[-1]
        ema21 = calc_ema(df["close"], 21).iloc[-1]
        ema9_bullish = float(ema9) > float(ema21)

        # Trend filter — wait for full 50-bar warmup before trading.
        # When no trend TF is configured the filter is skipped entirely.
        trend_tf = self.config.timeframes.get("trend")
        trend_bullish: bool | None = None
        trend_bearish: bool | None = None
        if trend_tf is not None:
            trend_df = context.bars.get(trend_tf)
            if trend_df is None or len(trend_df) < 50:
                return None  # skip until trend EMA50 is warmed up
            ema50_trend = calc_ema(trend_df["close"], 50).iloc[-1]
            last_close_1h = float(trend_df["close"].iloc[-1])
            trend_bullish = last_close_1h > float(ema50_trend)
            trend_bearish = last_close_1h < float(ema50_trend)

        trailing_pct = self._trailing_stop_pct or 0.05

        # LONG signal
        long_breakout = curr_close > resistance
        if (
            long_breakout
            and volume_confirmed
            and not pd.isna(rsi_val)
            and self._rsi_min_long <= rsi_val <= self._rsi_max_long
            and ema9_bullish
            and trend_bearish is not True
        ):
            entry = curr_close
            stop_loss = entry - self._atr_stop_mult * atr_val
            if stop_loss <= 0:
                return None
            risk_dist = entry - stop_loss
            take_profit = (entry * 1e6 if self.config.take_profit_r >= _NO_FIXED_TP
                           else entry + self.config.take_profit_r * risk_dist)

            state["last_signal_bar"] = current_bar
            return Signal(
                strategy_id=self.strategy_id,
                symbol=symbol,
                direction="long",
                strength=min(volume_ratio / (self._vol_surge * 2), 1.0),
                entry_price=entry,
                stop_loss=stop_loss,
                take_profit=take_profit,
                timeframe=signal_tf,
                timestamp=context.timestamp,
                metadata={
                    "breakout_level": round(resistance, 6),
                    "volume_ratio": round(volume_ratio, 2),
                    "rsi": round(rsi_val, 2),
                    "atr": round(atr_val, 6),
                    "trailing_stop_pct": trailing_pct,
                },
            )

        # SHORT signal
        short_breakdown = curr_close < support
        if (
            short_breakdown
            and volume_confirmed
            and not pd.isna(rsi_val)
            and self._rsi_min_short <= rsi_val <= self._rsi_max_short
            and not ema9_bullish
            and trend_bullish is not True
        ):
            entry = curr_close
            stop_loss = entry + self._atr_stop_mult * atr_val
            risk_dist = stop_loss - entry
            if risk_dist <= 0:
                return None
            take_profit = (entry / 1e6 if self.config.take_profit_r >= _NO_FIXED_TP
                           else entry - self.config.take_profit_r * risk_dist)
            if take_profit <= 0:
                return None

            state["last_signal_bar"] = current_bar
            return Signal(
                strategy_id=self.strategy_id,
                symbol=symbol,
                direction="short",
                strength=min(volume_ratio / (self._vol_surge * 2), 1.0),
                entry_price=entry,
                stop_loss=stop_loss,
                take_profit=take_profit,
                timeframe=signal_tf,
                timestamp=context.timestamp,
                metadata={
                    "breakout_level": round(support, 6),
                    "volume_ratio": round(volume_ratio, 2),
                    "rsi": round(rsi_val, 2),
                    "atr": round(atr_val, 6),
                    "trailing_stop_pct": trailing_pct,
                },
            )

        return None
