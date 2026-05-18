"""
RegimeDetector — classifies current market state from OHLCV price data.

Regime determines which strategy the Brain should favor:
  TRENDING_UP   → EMA crossover; mean reversion risky (fighting trend)
  TRENDING_DOWN → EMA short side; mean reversion still risky
  RANGING       → Mean reversion optimal; breakouts get faded
  HIGH_VOL      → All strategies need wider stops; reduce sizing
  LOW_VOL       → Mean reversion best; breakouts stall
  UNKNOWN       → Not enough history; hold defaults
"""
from __future__ import annotations

from enum import Enum
from typing import Optional

import pandas as pd


class MarketRegime(Enum):
    TRENDING_UP = "trending_up"
    TRENDING_DOWN = "trending_down"
    RANGING = "ranging"
    HIGH_VOL = "high_vol"
    LOW_VOL = "low_vol"
    UNKNOWN = "unknown"


# Which regimes each strategy type naturally thrives in
STRATEGY_REGIME_AFFINITY: dict[str, list[MarketRegime]] = {
    "ema_crossover": [MarketRegime.TRENDING_UP, MarketRegime.TRENDING_DOWN],
    "mean_reversion": [MarketRegime.RANGING, MarketRegime.LOW_VOL],
    "breakout": [
        MarketRegime.HIGH_VOL,
        MarketRegime.TRENDING_UP,
        MarketRegime.TRENDING_DOWN,
    ],
}


class RegimeDetector:
    """
    Classifies market regime using three signals:
      1. Realized volatility ratio (recent / long-term) → vol regime
      2. EMA(fast) vs EMA(slow) spread → trend vs ranging
      3. Sign of spread → up vs down
    """

    def __init__(
        self,
        ema_fast: int = 20,
        ema_slow: int = 50,
        vol_recent_bars: int = 20,
        vol_long_bars: int = 100,
        vol_high_ratio: float = 1.6,   # recent_vol > 1.6× long-term → HIGH_VOL
        vol_low_ratio: float = 0.55,   # recent_vol < 0.55× long-term → LOW_VOL
        trend_spread_pct: float = 0.004,  # 0.4% EMA spread → trending
    ) -> None:
        self._fast = ema_fast
        self._slow = ema_slow
        self._vol_recent = vol_recent_bars
        self._vol_long = vol_long_bars
        self._vol_high = vol_high_ratio
        self._vol_low = vol_low_ratio
        self._trend_thr = trend_spread_pct

    def detect(self, df: pd.DataFrame) -> MarketRegime:
        min_bars = max(self._slow, self._vol_long) + 5
        if df is None or len(df) < min_bars:
            return MarketRegime.UNKNOWN

        close = df["close"]
        log_ret = close.pct_change().dropna()

        recent_vol = float(log_ret.iloc[-self._vol_recent:].std())
        long_vol = float(log_ret.iloc[-self._vol_long:].std())
        vol_ratio = recent_vol / long_vol if long_vol > 0 else 1.0

        # Vol regime takes priority — extreme vol overrides trend classification
        if vol_ratio > self._vol_high:
            return MarketRegime.HIGH_VOL
        if vol_ratio < self._vol_low:
            return MarketRegime.LOW_VOL

        # EMA spread
        ema_fast = float(close.ewm(span=self._fast, adjust=False).mean().iloc[-1])
        ema_slow = float(close.ewm(span=self._slow, adjust=False).mean().iloc[-1])
        spread_pct = (ema_fast - ema_slow) / ema_slow if ema_slow > 0 else 0.0

        if spread_pct > self._trend_thr:
            return MarketRegime.TRENDING_UP
        if spread_pct < -self._trend_thr:
            return MarketRegime.TRENDING_DOWN
        return MarketRegime.RANGING

    def describe(self, regime: MarketRegime) -> str:
        return {
            MarketRegime.TRENDING_UP: "Strong uptrend — EMA strategies favored",
            MarketRegime.TRENDING_DOWN: "Strong downtrend — EMA short side favored",
            MarketRegime.RANGING: "Sideways market — mean reversion favored",
            MarketRegime.HIGH_VOL: "Elevated volatility — wider stops, reduced sizing",
            MarketRegime.LOW_VOL: "Compressed volatility — mean reversion optimal",
            MarketRegime.UNKNOWN: "Insufficient data for classification",
        }.get(regime, "Unknown")
