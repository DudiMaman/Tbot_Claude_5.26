"""
CryptoFeed — Binance WebSocket kline feed + REST fallback.
Emits OHLCVBar on each closed candle (x: true).
"""
from __future__ import annotations

import asyncio
import json
import logging
from datetime import datetime, timezone
from typing import AsyncIterator, Optional

import aiohttp

from bot.core.events import OHLCVBar
from bot.data.base import AbstractDataFeed
from bot.data.historical import HistoricalLoader
from bot.data.normalizer import bars_to_dataframe

logger = logging.getLogger(__name__)

_WS_URL = "wss://stream.binance.com:9443/ws"
_WS_TESTNET_URL = "wss://testnet.binance.vision/ws"


class CryptoFeed(AbstractDataFeed):
    def __init__(self, testnet: bool = False) -> None:
        self._testnet = testnet
        self._ws_url = _WS_TESTNET_URL if testnet else _WS_URL
        self._loader = HistoricalLoader(testnet=testnet)

    async def fetch_historical(self, symbol: str, timeframe: str, start, end) -> "pd.DataFrame":  # type: ignore[override]
        return await self._loader.fetch_crypto(symbol, timeframe, start, end)

    async def stream_bars(self, symbol: str, timeframe: str) -> AsyncIterator[OHLCVBar]:
        stream_name = f"{symbol.lower()}@kline_{timeframe}"
        url = f"{self._ws_url}/{stream_name}"
        retry_delay = 2.0

        while True:
            try:
                async with aiohttp.ClientSession() as session:
                    async with session.ws_connect(url, heartbeat=20) as ws:
                        logger.info(f"Connected to Binance WS: {stream_name}")
                        retry_delay = 2.0
                        async for msg in ws:
                            if msg.type == aiohttp.WSMsgType.TEXT:
                                bar = self._parse_kline(msg.data, symbol, timeframe)
                                if bar is not None:
                                    yield bar
                            elif msg.type in (aiohttp.WSMsgType.ERROR, aiohttp.WSMsgType.CLOSED):
                                break
            except Exception as e:
                logger.warning(f"WS disconnected ({e}); reconnecting in {retry_delay}s")
                await asyncio.sleep(retry_delay)
                retry_delay = min(retry_delay * 2, 60)

    def _parse_kline(self, raw: str, symbol: str, timeframe: str) -> Optional[OHLCVBar]:
        try:
            data = json.loads(raw)
            k = data.get("k") or data
            if not k.get("x", False):   # only emit on candle close
                return None
            return OHLCVBar(
                symbol=symbol,
                timeframe=timeframe,
                timestamp=datetime.fromtimestamp(k["t"] / 1000, tz=timezone.utc),
                open=float(k["o"]),
                high=float(k["h"]),
                low=float(k["l"]),
                close=float(k["c"]),
                volume=float(k["v"]),
                source="binance",
            )
        except Exception:
            return None
