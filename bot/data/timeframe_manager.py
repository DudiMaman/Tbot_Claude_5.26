"""
Multi-timeframe manager — maintains rolling ring buffers of OHLCV bars
for each symbol × timeframe pair, and converts lower TF bars into higher TFs.
"""
from __future__ import annotations

from collections import deque
from datetime import datetime, timezone
from typing import Optional

import pandas as pd

from bot.core.events import OHLCVBar
from bot.data.normalizer import bars_to_dataframe

_MINUTES = {
    "1m": 1, "3m": 3, "5m": 5, "15m": 15, "30m": 30,
    "1h": 60, "2h": 120, "4h": 240, "1D": 1440,
}

_BUFFER_SIZES = {
    "1m": 60, "5m": 60, "15m": 100, "1h": 200, "4h": 200, "1D": 365,
}


class TimeframeManager:
    def __init__(self, timeframes: list[str], buffer_size: int = 200) -> None:
        self._timeframes = timeframes
        self._buffer_size = buffer_size
        # {symbol: {timeframe: deque[OHLCVBar]}}
        self._buffers: dict[str, dict[str, deque]] = {}
        # track which bars are new this tick
        self._new_bars: dict[str, dict[str, bool]] = {}
        # 1m bar counter for synthesis
        self._one_min_counts: dict[str, int] = {}

    def _ensure(self, symbol: str) -> None:
        if symbol not in self._buffers:
            self._buffers[symbol] = {
                tf: deque(maxlen=_BUFFER_SIZES.get(tf, self._buffer_size))
                for tf in self._timeframes
            }
            self._new_bars[symbol] = {tf: False for tf in self._timeframes}
            self._one_min_counts[symbol] = 0

    def update(self, bar: OHLCVBar) -> list[str]:
        """
        Add a bar to the appropriate buffer.
        Returns list of timeframes that have a new completed bar this tick.
        """
        self._ensure(bar.symbol)
        # Reset new-bar flags
        for tf in self._timeframes:
            self._new_bars[bar.symbol][tf] = False

        tf = bar.timeframe
        if tf in self._buffers[bar.symbol]:
            self._buffers[bar.symbol][tf].append(bar)
            self._new_bars[bar.symbol][tf] = True

        return [tf for tf in self._timeframes if self._new_bars[bar.symbol].get(tf, False)]

    def pre_warm(self, symbol: str, timeframe: str, bars: list[OHLCVBar]) -> None:
        """Load historical bars into buffer before live trading starts."""
        self._ensure(symbol)
        buf = self._buffers[symbol][timeframe]
        buf.clear()
        for bar in bars[-buf.maxlen:]:
            buf.append(bar)

    def get_dataframe(self, symbol: str, timeframe: str) -> pd.DataFrame:
        self._ensure(symbol)
        bars = list(self._buffers[symbol].get(timeframe, []))
        return bars_to_dataframe(bars)

    def latest_bar(self, symbol: str, timeframe: str) -> Optional[OHLCVBar]:
        self._ensure(symbol)
        buf = self._buffers[symbol].get(timeframe)
        if not buf:
            return None
        return buf[-1]

    def bar_count(self, symbol: str, timeframe: str) -> int:
        self._ensure(symbol)
        return len(self._buffers[symbol].get(timeframe, []))
