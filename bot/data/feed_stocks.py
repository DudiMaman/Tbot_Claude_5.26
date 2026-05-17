"""
StockFeed — Alpaca WebSocket bar feed with REST polling fallback.
Respects market hours; emits OHLCVBar on each closed bar.
"""
from __future__ import annotations

import asyncio
import logging
from datetime import date, datetime, timezone
from typing import AsyncIterator

import pandas as pd

from bot.core.events import OHLCVBar
from bot.data.base import AbstractDataFeed
from bot.data.historical import HistoricalLoader
from bot.utils.time_utils import is_stock_market_open

logger = logging.getLogger(__name__)


class StockFeed(AbstractDataFeed):
    def __init__(self, api_key: str = "", api_secret: str = "", paper: bool = True) -> None:
        self._api_key = api_key
        self._api_secret = api_secret
        self._paper = paper
        self._loader = HistoricalLoader()

    async def fetch_historical(self, symbol: str, timeframe: str, start: date, end: date) -> pd.DataFrame:
        return await self._loader.fetch_stocks(symbol, timeframe, start, end)

    async def stream_bars(self, symbol: str, timeframe: str) -> AsyncIterator[OHLCVBar]:
        """Yields bars via Alpaca SDK if available, else polls REST."""
        try:
            from alpaca.data.live import StockDataStream
            from alpaca.data.models import Bar

            stream = StockDataStream(self._api_key, self._api_secret)

            queue: asyncio.Queue[OHLCVBar] = asyncio.Queue()

            async def handler(bar: Bar) -> None:
                await queue.put(OHLCVBar(
                    symbol=bar.symbol,
                    timeframe=timeframe,
                    timestamp=bar.timestamp.astimezone(timezone.utc),
                    open=float(bar.open),
                    high=float(bar.high),
                    low=float(bar.low),
                    close=float(bar.close),
                    volume=float(bar.volume),
                    source="alpaca",
                ))

            stream.subscribe_bars(handler, symbol)
            asyncio.create_task(stream.run())

            while True:
                yield await queue.get()

        except ImportError:
            logger.warning("alpaca-py not available; falling back to polling")
            async for bar in self._poll_bars(symbol, timeframe):
                yield bar

    async def _poll_bars(self, symbol: str, timeframe: str) -> AsyncIterator[OHLCVBar]:
        """Fallback: poll Alpaca REST every 60s for new bars."""
        import httpx
        base = "https://paper-api.alpaca.markets" if self._paper else "https://api.alpaca.markets"
        headers = {"APCA-API-KEY-ID": self._api_key, "APCA-API-SECRET-KEY": self._api_secret}

        while True:
            if not is_stock_market_open():
                await asyncio.sleep(60)
                continue
            try:
                async with httpx.AsyncClient() as client:
                    resp = await client.get(
                        f"{base}/v2/stocks/{symbol}/bars/latest",
                        headers=headers,
                        params={"timeframe": timeframe},
                    )
                    resp.raise_for_status()
                    bar_data = resp.json().get("bar", {})
                    if bar_data:
                        ts = datetime.fromisoformat(bar_data["t"].replace("Z", "+00:00"))
                        yield OHLCVBar(
                            symbol=symbol,
                            timeframe=timeframe,
                            timestamp=ts.astimezone(timezone.utc),
                            open=float(bar_data["o"]),
                            high=float(bar_data["h"]),
                            low=float(bar_data["l"]),
                            close=float(bar_data["c"]),
                            volume=float(bar_data["v"]),
                            source="alpaca",
                        )
            except Exception as e:
                logger.warning(f"Stock feed poll error: {e}")
            await asyncio.sleep(60)
