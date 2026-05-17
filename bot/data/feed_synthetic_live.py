"""
SyntheticLiveFeed — real-time GBM bar generator for paper-trading when
external market data is unavailable (network restrictions, CI, demos).

Each bar takes `bar_seconds` of real time. Prices follow Geometric Brownian
Motion scaled from the supplied annual drift / volatility parameters.
"""
from __future__ import annotations

import asyncio
import math
import random
from datetime import datetime, timezone
from typing import AsyncIterator, Optional

from bot.core.events import OHLCVBar
from bot.data.base import AbstractDataFeed

_INITIAL_PRICES: dict[str, float] = {
    "BTCUSDT":  95_000.0,
    "ETHUSDT":   3_500.0,
    "BNBUSDT":     600.0,
    "SOLUSDT":     150.0,
    "XRPUSDT":       0.6,
    "ADAUSDT":       0.4,
}

# Each timeframe's fraction of a 252-day trading year
_TIMEFRAME_DT: dict[str, float] = {
    "1m":  1 / (252 * 24 * 60),
    "3m":  3 / (252 * 24 * 60),
    "5m":  5 / (252 * 24 * 60),
    "15m": 15 / (252 * 24 * 60),
    "30m": 30 / (252 * 24 * 60),
    "1h":  1 / (252 * 24),
    "2h":  2 / (252 * 24),
    "4h":  4 / (252 * 24),
    "1D":  1 / 252,
    "1W":  5 / 252,
}


class SyntheticLiveFeed(AbstractDataFeed):
    """
    Generates synthetic OHLCV bars in real time at a configurable speed.

    Useful when live data feeds are unreachable; exercises the full paper-
    trading pipeline (strategies, risk manager, fills, reporting) without
    requiring network access.

    Parameters
    ----------
    bar_seconds : float
        Real-time seconds between emitted bars (default 5).
        Lower = faster paper trading; higher = more realistic pacing.
    annual_drift : float
        Annualised drift (log-return mean). 0.50 = 50% annual uptrend.
    annual_vol : float
        Annualised volatility. 0.75 matches historic BTC vol.
    seed : int | None
        Optional RNG seed for reproducibility.
    """

    def __init__(
        self,
        bar_seconds: float = 5.0,
        annual_drift: float = 0.50,
        annual_vol: float = 0.75,
        seed: Optional[int] = None,
    ) -> None:
        self._bar_seconds = bar_seconds
        self._annual_drift = annual_drift
        self._annual_vol = annual_vol
        self._rng = random.Random(seed)

    async def fetch_historical(self, symbol: str, timeframe: str, start, end):  # type: ignore[override]
        raise NotImplementedError("SyntheticLiveFeed does not support historical fetch")

    async def stream_bars(self, symbol: str, timeframe: str) -> AsyncIterator[OHLCVBar]:
        price = _INITIAL_PRICES.get(symbol, 1_000.0)
        rng = self._rng

        # Price movement is based on the bar's timeframe, not real elapsed seconds.
        # This ensures 1h bars carry 1h-worth of vol regardless of bar_seconds.
        dt = _TIMEFRAME_DT.get(timeframe, _TIMEFRAME_DT["1h"])
        mu = self._annual_drift * dt
        sigma = self._annual_vol * math.sqrt(dt)

        while True:
            await asyncio.sleep(self._bar_seconds)

            # GBM log-return step
            log_ret = rng.gauss(mu - 0.5 * sigma ** 2, sigma)
            close = price * math.exp(log_ret)

            # Simulate intra-bar wick using a smaller vol
            wick_sigma = sigma * 0.4
            high_wick = abs(rng.gauss(0, wick_sigma))
            low_wick = abs(rng.gauss(0, wick_sigma))
            high = max(price, close) * math.exp(high_wick)
            low = min(price, close) * math.exp(-low_wick)

            volume = max(10.0, rng.gauss(500, 150))

            yield OHLCVBar(
                symbol=symbol,
                timeframe=timeframe,
                timestamp=datetime.now(timezone.utc),
                open=round(price, 8),
                high=round(high, 8),
                low=round(low, 8),
                close=round(close, 8),
                volume=round(volume, 4),
                source="synthetic_live",
            )

            price = close
