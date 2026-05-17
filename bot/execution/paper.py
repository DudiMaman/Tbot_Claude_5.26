"""
PaperBroker — simulates fills with realistic fees and slippage.
Fills at the next bar's open price (bar N signal → bar N+1 fill) to prevent lookahead.
"""
from __future__ import annotations

import random
import uuid
from collections import defaultdict
from datetime import datetime, timezone
from typing import Optional

from bot.core.events import FillEvent, OHLCVBar, OrderEvent
from bot.core.config import BrokerConfig
from bot.execution.base import AbstractBroker
from bot.execution.fee_model import FeeModel
from bot.execution.order import Order, OrderStatus


class PaperBroker(AbstractBroker):
    def __init__(self, broker_config: BrokerConfig, initial_cash: float = 5000.0) -> None:
        self._fee_model = FeeModel(broker_config)
        self._cfg = broker_config
        self._cash = initial_cash
        self._orders: dict[str, Order] = {}
        self._pending_orders: list[Order] = []  # waiting for next bar to fill
        self._fill_callbacks: list = []

    def register_fill_callback(self, cb) -> None:  # type: ignore[type-arg]
        self._fill_callbacks.append(cb)

    async def place_order(self, order_event: OrderEvent) -> Order:
        order = Order(
            order_id=str(uuid.uuid4())[:8],
            symbol=order_event.symbol,
            side=order_event.side,
            qty=order_event.qty,
            order_type=order_event.order_type,
            price=order_event.price,
            stop_price=order_event.stop_price,
            strategy_id=order_event.strategy_id,
            idempotency_key=order_event.idempotency_key,
            status=OrderStatus.PENDING,
            created_at=datetime.now(timezone.utc),
            updated_at=datetime.now(timezone.utc),
        )
        self._orders[order.order_id] = order
        self._pending_orders.append(order)
        return order

    async def on_bar(self, bar: OHLCVBar) -> list[FillEvent]:
        """Call on each new bar to simulate pending order fills."""
        fills: list[FillEvent] = []
        still_pending: list[Order] = []

        for order in self._pending_orders:
            if order.symbol != bar.symbol:
                still_pending.append(order)
                continue

            fill = self._simulate_fill(order, bar)
            if fill:
                fills.append(fill)
                for cb in self._fill_callbacks:
                    await cb(fill)
            else:
                still_pending.append(order)

        self._pending_orders = still_pending
        return fills

    def _simulate_fill(self, order: Order, bar: OHLCVBar) -> Optional[FillEvent]:
        # Fill at bar open + slippage
        slippage_bps = self._cfg.slippage_estimate_bps
        slippage = random.gauss(0, slippage_bps / 10_000)
        fill_price = bar.open * (1 + slippage if order.side == "buy" else 1 - slippage)

        # Check stop orders
        if order.order_type in ("stop_limit", "stop_loss"):
            if order.side == "buy" and bar.high < order.stop_price:
                return None
            if order.side == "sell" and bar.low > order.stop_price:
                return None

        fee_rate = self._cfg.fee_schedule.taker
        fee_paid = order.qty * fill_price * fee_rate

        # Update cash
        if order.side == "buy":
            cost = order.qty * fill_price + fee_paid
            if cost > self._cash:
                order.status = OrderStatus.REJECTED
                return None
            self._cash -= cost
        else:
            self._cash += order.qty * fill_price - fee_paid

        order.status = OrderStatus.FILLED
        order.qty_filled = order.qty
        order.avg_fill_price = fill_price
        order.fee_paid = fee_paid
        order.updated_at = bar.timestamp

        return FillEvent(
            order_id=order.order_id,
            symbol=order.symbol,
            side=order.side,
            qty_filled=order.qty,
            avg_price=fill_price,
            fee_paid=fee_paid,
            timestamp=bar.timestamp,
            strategy_id=order.strategy_id,
            idempotency_key=order.idempotency_key,
            is_partial=False,
        )

    async def cancel_order(self, order_id: str, symbol: str) -> bool:
        order = self._orders.get(order_id)
        if order and not order.is_complete:
            order.status = OrderStatus.CANCELLED
            self._pending_orders = [o for o in self._pending_orders if o.order_id != order_id]
            return True
        return False

    async def get_order_status(self, order_id: str, symbol: str) -> Optional[Order]:
        return self._orders.get(order_id)

    async def get_open_orders(self, symbol: Optional[str] = None) -> list[Order]:
        orders = [o for o in self._pending_orders if not o.is_complete]
        if symbol:
            orders = [o for o in orders if o.symbol == symbol]
        return orders

    async def get_account_balance(self) -> dict[str, float]:
        return {"cash": self._cash}

    async def simulate_stop_fill(
        self,
        symbol: str,
        side: str,
        qty: float,
        fill_price: float,
        strategy_id: str,
        idempotency_key: str,
        timestamp: "datetime",
    ) -> Optional[FillEvent]:
        """Immediately simulate a stop/TP fill without waiting for the next bar."""
        fee_rate = self._cfg.fee_schedule.taker
        fee_paid = qty * fill_price * fee_rate

        if side == "buy":
            cost = qty * fill_price + fee_paid
            if cost > self._cash:
                return None
            self._cash -= cost
        else:
            self._cash += qty * fill_price - fee_paid

        fill = FillEvent(
            order_id=str(uuid.uuid4())[:8],
            symbol=symbol,
            side=side,
            qty_filled=qty,
            avg_price=fill_price,
            fee_paid=fee_paid,
            timestamp=timestamp,
            strategy_id=strategy_id,
            idempotency_key=idempotency_key,
            is_partial=False,
        )
        for cb in self._fill_callbacks:
            await cb(fill)
        return fill

    async def sync_positions(self) -> list[dict]:
        return []

    @property
    def cash(self) -> float:
        return self._cash
