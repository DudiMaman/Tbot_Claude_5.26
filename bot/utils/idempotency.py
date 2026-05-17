"""Idempotency key generation — one key per (strategy, symbol, direction, bar)."""
from __future__ import annotations

import hashlib
from datetime import datetime


def make_key(strategy_id: str, symbol: str, direction: str, bar_timestamp: datetime) -> str:
    raw = f"{strategy_id}|{symbol}|{direction}|{bar_timestamp.isoformat()}"
    return hashlib.sha256(raw.encode()).hexdigest()[:16]
