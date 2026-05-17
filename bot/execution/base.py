"""Abstract broker interface — all brokers implement this contract."""
from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Optional

from bot.core.events import FillEvent, OrderEvent
from bot.execution.order import Order


class AbstractBroker(ABC):
    @abstractmethod
    async def place_order(self, order_event: OrderEvent) -> Order:
        ...

    @abstractmethod
    async def cancel_order(self, order_id: str, symbol: str) -> bool:
        ...

    @abstractmethod
    async def get_order_status(self, order_id: str, symbol: str) -> Optional[Order]:
        ...

    @abstractmethod
    async def get_open_orders(self, symbol: Optional[str] = None) -> list[Order]:
        ...

    @abstractmethod
    async def get_account_balance(self) -> dict[str, float]:
        ...

    @abstractmethod
    async def sync_positions(self) -> list[dict]:
        """Re-fetch all open positions from broker on startup/reconnect."""
        ...

    async def start(self) -> None:
        """Optional: start WebSocket feed, heartbeat tasks, etc."""

    async def stop(self) -> None:
        """Graceful shutdown."""
