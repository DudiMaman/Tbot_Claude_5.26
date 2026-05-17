"""Disk cache for historical OHLCV data (Parquet format)."""
from __future__ import annotations

import hashlib
from datetime import datetime, date
from pathlib import Path
from typing import Optional

import pandas as pd

from bot.core.events import OHLCVBar
from bot.data.normalizer import bars_to_dataframe


class DataCache:
    def __init__(self, cache_dir: str | Path = "data_cache") -> None:
        self._dir = Path(cache_dir)
        self._dir.mkdir(parents=True, exist_ok=True)

    def _path(self, symbol: str, timeframe: str, start: date, end: date) -> Path:
        key = hashlib.md5(f"{symbol}_{timeframe}_{start}_{end}".encode()).hexdigest()[:12]
        return self._dir / f"{symbol.lower()}_{timeframe}_{key}.parquet"

    def load(
        self, symbol: str, timeframe: str, start: date, end: date
    ) -> Optional[pd.DataFrame]:
        path = self._path(symbol, timeframe, start, end)
        if not path.exists():
            return None
        try:
            return pd.read_parquet(path)
        except Exception:
            return None

    def save(
        self, symbol: str, timeframe: str, start: date, end: date, df: pd.DataFrame
    ) -> None:
        path = self._path(symbol, timeframe, start, end)
        df.to_parquet(path)

    def load_bars(
        self, symbol: str, timeframe: str, start: date, end: date
    ) -> Optional[list[OHLCVBar]]:
        df = self.load(symbol, timeframe, start, end)
        if df is None or df.empty:
            return None
        return dataframe_to_bars(df, symbol, timeframe)


def dataframe_to_bars(df: pd.DataFrame, symbol: str, timeframe: str, source: str = "cache") -> list[OHLCVBar]:
    bars = []
    for ts, row in df.iterrows():
        bars.append(OHLCVBar(
            symbol=symbol,
            timeframe=timeframe,
            timestamp=ts if hasattr(ts, "tzinfo") else pd.Timestamp(ts).to_pydatetime(),
            open=float(row["open"]),
            high=float(row["high"]),
            low=float(row["low"]),
            close=float(row["close"]),
            volume=float(row["volume"]),
            source=source,
        ))
    return bars
