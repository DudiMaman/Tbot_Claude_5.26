from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from typing import Literal, Optional


@dataclass
class Position:
    symbol: str
    side: Literal["long", "short"]
    entry_price: float
    qty: float
    stop_loss: float
    take_profit: float
    strategy_id: str
    idempotency_key: str
    opened_at: datetime

    qty_filled: float = 0.0
    trailing_stop_pct: Optional[float] = None
    trailing_stop_high: float = 0.0      # highest close since entry (long) or lowest (short)
    fees_paid_entry: float = 0.0
    fees_paid_exit: float = 0.0
    closed_at: Optional[datetime] = None
    exit_price: Optional[float] = None
    is_closed: bool = False

    @property
    def gross_pnl(self) -> float:
        if self.exit_price is None:
            return 0.0
        if self.side == "long":
            return (self.exit_price - self.entry_price) * self.qty_filled
        return (self.entry_price - self.exit_price) * self.qty_filled

    @property
    def net_pnl(self) -> float:
        return self.gross_pnl - self.fees_paid_entry - self.fees_paid_exit

    @property
    def unrealized_pnl(self, current_price: float = 0.0) -> float:
        if current_price <= 0:
            return 0.0
        if self.side == "long":
            return (current_price - self.entry_price) * self.qty_filled
        return (self.entry_price - current_price) * self.qty_filled

    def update_trailing_stop(self, current_price: float) -> Optional[float]:
        """Update trailing stop; return new SL if it moved, else None."""
        if self.trailing_stop_pct is None:
            return None

        if self.side == "long":
            if current_price > self.trailing_stop_high:
                self.trailing_stop_high = current_price
                new_sl = current_price * (1 - self.trailing_stop_pct)
                if new_sl > self.stop_loss:
                    self.stop_loss = new_sl
                    return new_sl
        else:
            if self.trailing_stop_high == 0.0 or current_price < self.trailing_stop_high:
                self.trailing_stop_high = current_price
                new_sl = current_price * (1 + self.trailing_stop_pct)
                if new_sl < self.stop_loss:
                    self.stop_loss = new_sl
                    return new_sl
        return None

    def close(self, exit_price: float, fee_paid: float, closed_at: datetime) -> None:
        self.exit_price = exit_price
        self.fees_paid_exit = fee_paid
        self.closed_at = closed_at
        self.is_closed = True
