"""
Central event dataclasses — the contract between every component.
All cross-component communication flows through these types.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Literal, Optional


@dataclass(frozen=True)
class OHLCVBar:
    symbol: str
    timeframe: str
    timestamp: datetime       # UTC, candle open time
    open: float
    high: float
    low: float
    close: float
    volume: float
    source: str = "unknown"


@dataclass(frozen=True)
class MarketEvent:
    symbol: str
    timeframe: str
    bar: OHLCVBar
    timestamp: datetime


@dataclass
class Signal:
    strategy_id: str
    symbol: str
    direction: Literal["long", "short", "flat", "close"]
    strength: float                    # 0.0–1.0
    entry_price: float                 # 0 = market order
    stop_loss: float
    take_profit: float
    timeframe: str
    timestamp: datetime
    fee_estimate: float = 0.0          # filled by FeeModel
    expected_r_after_fees: float = 0.0 # filled by FeeModel
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass
class OrderEvent:
    symbol: str
    side: Literal["buy", "sell"]
    qty: float
    order_type: Literal["market", "limit", "stop_limit", "stop_loss"]
    price: float                       # 0 for market orders
    stop_price: float = 0.0
    strategy_id: str = ""
    signal_direction: str = ""
    idempotency_key: str = ""
    timestamp: datetime = field(default_factory=lambda: datetime.now())


@dataclass
class FillEvent:
    order_id: str
    symbol: str
    side: Literal["buy", "sell"]
    qty_filled: float
    avg_price: float
    fee_paid: float
    timestamp: datetime
    strategy_id: str = ""
    idempotency_key: str = ""
    is_partial: bool = False


@dataclass
class RejectionEvent:
    symbol: str
    strategy_id: str
    reason: str
    signal: Optional[Signal]
    timestamp: datetime


@dataclass
class CircuitBreakerEvent:
    reason: str
    trigger_value: float
    threshold: float
    timestamp: datetime


@dataclass
class MarketClosedEvent:
    symbol: str
    timestamp: datetime
    reason: str = "outside_market_hours"
