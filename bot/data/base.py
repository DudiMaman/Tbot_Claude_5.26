"""Abstract DataFeed interface."""
from __future__ import annotations

from abc import ABC, abstractmethod
from datetime import date
from typing import AsyncIterator, Optional

import pandas as pd

from bot.core.events import OHLCVBar


class AbstractDataFeed(ABC):
    @abstractmethod
    async def fetch_historical(
        self,
        symbol: str,
        timeframe: str,
        start: date,
        end: date,
    ) -> pd.DataFrame:
        """Fetch OHLCV bars for backtesting; returns DataFrame indexed by timestamp."""
        ...

    @abstractmethod
    async def stream_bars(
        self,
        symbol: str,
        timeframe: str,
    ) -> AsyncIterator[OHLCVBar]:
        """Async generator yielding live OHLCVBars as they close."""
        ...
