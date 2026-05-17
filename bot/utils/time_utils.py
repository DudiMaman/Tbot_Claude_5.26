"""Market-hours checks and timezone utilities."""
from __future__ import annotations

from datetime import datetime, time, timezone

try:
    from zoneinfo import ZoneInfo
except ImportError:
    from backports.zoneinfo import ZoneInfo  # type: ignore[no-redef]

_ET = ZoneInfo("America/New_York")

# NYSE/NASDAQ regular session hours (Eastern time)
_MARKET_OPEN = time(9, 30)
_MARKET_CLOSE = time(16, 0)

# US federal holidays (simplified — expand as needed)
_US_HOLIDAYS_2024_2025 = {
    (2024, 1, 1), (2024, 1, 15), (2024, 2, 19), (2024, 3, 29),
    (2024, 5, 27), (2024, 6, 19), (2024, 7, 4), (2024, 9, 2),
    (2024, 11, 28), (2024, 12, 25),
    (2025, 1, 1), (2025, 1, 20), (2025, 2, 17), (2025, 4, 18),
    (2025, 5, 26), (2025, 6, 19), (2025, 7, 4), (2025, 9, 1),
    (2025, 11, 27), (2025, 12, 25),
    (2026, 1, 1), (2026, 1, 19), (2026, 2, 16), (2026, 4, 3),
    (2026, 5, 25), (2026, 6, 19), (2026, 7, 3), (2026, 9, 7),
    (2026, 11, 26), (2026, 12, 25),
}


def is_stock_market_open(dt: datetime | None = None) -> bool:
    """Return True if NYSE/NASDAQ regular session is currently open."""
    dt = dt or datetime.now(timezone.utc)
    et = dt.astimezone(_ET)
    if et.weekday() >= 5:  # Saturday or Sunday
        return False
    if (et.year, et.month, et.day) in _US_HOLIDAYS_2024_2025:
        return False
    return _MARKET_OPEN <= et.time() < _MARKET_CLOSE


def to_utc(dt: datetime) -> datetime:
    if dt.tzinfo is None:
        return dt.replace(tzinfo=timezone.utc)
    return dt.astimezone(timezone.utc)


def utc_now() -> datetime:
    return datetime.now(timezone.utc)
