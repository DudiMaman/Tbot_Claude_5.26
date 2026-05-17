"""Converts raw broker OHLCV data to unified OHLCVBar dataclass."""
from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from bot.core.events import OHLCVBar


def normalize_ccxt_ohlcv(
    raw: list[Any],
    symbol: str,
    timeframe: str,
    source: str = "binance",
) -> OHLCVBar:
    """
    ccxt returns: [timestamp_ms, open, high, low, close, volume]
    """
    ts_ms, open_, high, low, close, volume = raw
    ts = datetime.fromtimestamp(ts_ms / 1000, tz=timezone.utc)
    return OHLCVBar(
        symbol=symbol,
        timeframe=timeframe,
        timestamp=ts,
        open=float(open_),
        high=float(high),
        low=float(low),
        close=float(close),
        volume=float(volume),
        source=source,
    )


def normalize_alpaca_bar(raw: dict[str, Any], symbol: str, timeframe: str) -> OHLCVBar:
    ts = raw.get("t") or raw.get("timestamp")
    if isinstance(ts, str):
        ts = datetime.fromisoformat(ts.replace("Z", "+00:00"))
    return OHLCVBar(
        symbol=symbol,
        timeframe=timeframe,
        timestamp=ts.astimezone(timezone.utc),
        open=float(raw["o"]),
        high=float(raw["h"]),
        low=float(raw["l"]),
        close=float(raw["c"]),
        volume=float(raw["v"]),
        source="alpaca",
    )


def bars_to_dataframe(bars: list[OHLCVBar]) -> "pd.DataFrame":  # type: ignore[name-defined]
    import pandas as pd

    records = [
        {
            "timestamp": b.timestamp,
            "open": b.open,
            "high": b.high,
            "low": b.low,
            "close": b.close,
            "volume": b.volume,
        }
        for b in bars
    ]
    df = pd.DataFrame(records)
    if not df.empty:
        df.set_index("timestamp", inplace=True)
        df.sort_index(inplace=True)
    return df
