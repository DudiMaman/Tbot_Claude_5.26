"""
HistoricalLoader — fetches and caches OHLCV data for backtesting.
Crypto via ccxt (Binance), stocks via yfinance.
"""
from __future__ import annotations

import asyncio
import time
from datetime import date, datetime, timezone
from typing import Optional

import pandas as pd

from bot.data.cache import DataCache
from bot.data.normalizer import normalize_ccxt_ohlcv


_TF_MAP = {
    "1m": "1m", "5m": "5m", "15m": "15m",
    "1h": "1h", "4h": "4h", "1D": "1d",
}

_YFINANCE_TF_MAP = {
    "1m": "1m", "5m": "5m", "15m": "15m",
    "1h": "1h", "4h": "1h",  # yfinance max is 1h for intraday
    "1D": "1d",
}


class HistoricalLoader:
    def __init__(
        self,
        cache: Optional[DataCache] = None,
        testnet: bool = False,
    ) -> None:
        self._cache = cache or DataCache()
        self._testnet = testnet

    async def fetch_crypto(
        self,
        symbol: str,
        timeframe: str,
        start: date,
        end: date,
    ) -> pd.DataFrame:
        cached = self._cache.load(symbol, timeframe, start, end)
        if cached is not None:
            return cached

        df = await asyncio.to_thread(
            self._fetch_ccxt_sync, symbol, timeframe, start, end
        )
        if not df.empty:
            self._cache.save(symbol, timeframe, start, end, df)
        return df

    def _fetch_ccxt_sync(
        self, symbol: str, timeframe: str, start: date, end: date
    ) -> pd.DataFrame:
        try:
            import ccxt
        except ImportError:
            raise ImportError("ccxt is required for crypto historical data: pip install ccxt")

        exchange = ccxt.binance({"enableRateLimit": True})
        if self._testnet:
            exchange.set_sandbox_mode(True)

        ccxt_tf = _TF_MAP.get(timeframe, timeframe)
        since_ms = int(datetime(start.year, start.month, start.day, tzinfo=timezone.utc).timestamp() * 1000)
        end_ms = int(datetime(end.year, end.month, end.day, tzinfo=timezone.utc).timestamp() * 1000)

        all_bars = []
        while since_ms < end_ms:
            raw = exchange.fetch_ohlcv(symbol, ccxt_tf, since=since_ms, limit=1000)
            if not raw:
                break
            all_bars.extend(raw)
            since_ms = raw[-1][0] + 1
            if len(raw) < 1000:
                break
            time.sleep(exchange.rateLimit / 1000)

        bars = [normalize_ccxt_ohlcv(r, symbol, timeframe) for r in all_bars]
        bars = [b for b in bars if b.timestamp.date() < end]

        if not bars:
            return pd.DataFrame(columns=["open", "high", "low", "close", "volume"])

        records = [
            {"timestamp": b.timestamp, "open": b.open, "high": b.high,
             "low": b.low, "close": b.close, "volume": b.volume}
            for b in bars
        ]
        df = pd.DataFrame(records).set_index("timestamp").sort_index()
        return df

    async def fetch_stocks(
        self,
        symbol: str,
        timeframe: str,
        start: date,
        end: date,
    ) -> pd.DataFrame:
        cached = self._cache.load(symbol, timeframe, start, end)
        if cached is not None:
            return cached

        df = await asyncio.to_thread(self._fetch_yfinance_sync, symbol, timeframe, start, end)
        if not df.empty:
            self._cache.save(symbol, timeframe, start, end, df)
        return df

    def _fetch_yfinance_sync(
        self, symbol: str, timeframe: str, start: date, end: date
    ) -> pd.DataFrame:
        try:
            import yfinance as yf
        except ImportError:
            raise ImportError("yfinance is required: pip install yfinance")

        yf_tf = _YFINANCE_TF_MAP.get(timeframe, "1d")
        ticker = yf.Ticker(symbol)
        df = ticker.history(start=start.isoformat(), end=end.isoformat(), interval=yf_tf)

        if df.empty:
            return pd.DataFrame(columns=["open", "high", "low", "close", "volume"])

        df = df[["Open", "High", "Low", "Close", "Volume"]].copy()
        df.columns = ["open", "high", "low", "close", "volume"]
        df.index = pd.to_datetime(df.index, utc=True)
        df.index.name = "timestamp"
        return df.sort_index()
