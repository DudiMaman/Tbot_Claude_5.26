from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Literal


class OrderStatus(str, Enum):
    PENDING = "pending"
    OPEN = "open"
    PARTIALLY_FILLED = "partially_filled"
    FILLED = "filled"
    CANCELLED = "cancelled"
    REJECTED = "rejected"
    EXPIRED = "expired"


@dataclass
class Order:
    order_id: str
    symbol: str
    side: Literal["buy", "sell"]
    qty: float
    order_type: Literal["market", "limit", "stop_limit", "stop_loss"]
    price: float                     # 0 for market orders
    stop_price: float = 0.0
    strategy_id: str = ""
    idempotency_key: str = ""
    status: OrderStatus = OrderStatus.PENDING
    qty_filled: float = 0.0
    avg_fill_price: float = 0.0
    fee_paid: float = 0.0
    created_at: datetime = field(default_factory=datetime.utcnow)
    updated_at: datetime = field(default_factory=datetime.utcnow)

    @property
    def is_complete(self) -> bool:
        return self.status in (
            OrderStatus.FILLED,
            OrderStatus.CANCELLED,
            OrderStatus.REJECTED,
            OrderStatus.EXPIRED,
        )

    @property
    def qty_remaining(self) -> float:
        return self.qty - self.qty_filled
