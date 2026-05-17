"""
AlpacaBroker — REST + WebSocket; market-hours guard; PDT rule tracking.
"""
from __future__ import annotations

import asyncio
import os
import uuid
import structlog
from collections import deque
from datetime import datetime, date, timezone
from typing import Any, Optional

from bot.core.events import FillEvent, OrderEvent
from bot.core.config import BrokerConfig
from bot.execution.base import AbstractBroker
from bot.execution.order import Order, OrderStatus
from bot.utils.retry import async_retry
from bot.utils.time_utils import is_stock_market_open

logger = structlog.get_logger(__name__)


class AlpacaBroker(AbstractBroker):
    def __init__(self, broker_config: BrokerConfig) -> None:
        self._cfg = broker_config
        paper = os.environ.get("ALPACA_BASE_URL", "https://paper-api.alpaca.markets")
        self._base_url = os.environ.get("ALPACA_BASE_URL", paper)
        self._api_key = os.environ.get("ALPACA_API_KEY", "")
        self._secret = os.environ.get("ALPACA_SECRET", "")
        self._orders: dict[str, Order] = {}
        self._fill_callbacks: list = []
        self._day_trades: deque[date] = deque()  # rolling PDT tracker

    def register_fill_callback(self, cb) -> None:  # type: ignore[type-arg]
        self._fill_callbacks.append(cb)

    async def place_order(self, order_event: OrderEvent) -> Order:
        if not is_stock_market_open():
            raise RuntimeError(f"Market closed; cannot place order for {order_event.symbol}")

        if self._cfg.model_extra.get("enforce_pdt_rules", True):
            self._check_pdt()

        try:
            from alpaca.trading.client import TradingClient
            from alpaca.trading.requests import MarketOrderRequest, LimitOrderRequest
            from alpaca.trading.enums import OrderSide, TimeInForce

            client = TradingClient(self._api_key, self._secret, paper=("paper" in self._base_url))
            side = OrderSide.BUY if order_event.side == "buy" else OrderSide.SELL

            if order_event.order_type == "market":
                request = MarketOrderRequest(
                    symbol=order_event.symbol,
                    qty=order_event.qty,
                    side=side,
                    time_in_force=TimeInForce.DAY,
                    client_order_id=order_event.idempotency_key or str(uuid.uuid4()),
                )
            else:
                request = LimitOrderRequest(
                    symbol=order_event.symbol,
                    qty=order_event.qty,
                    side=side,
                    time_in_force=TimeInForce.DAY,
                    limit_price=order_event.price,
                    client_order_id=order_event.idempotency_key or str(uuid.uuid4()),
                )

            resp = await asyncio.to_thread(client.submit_order, request)
            order = Order(
                order_id=str(resp.id),
                symbol=order_event.symbol,
                side=order_event.side,
                qty=order_event.qty,
                order_type=order_event.order_type,
                price=order_event.price,
                strategy_id=order_event.strategy_id,
                idempotency_key=order_event.idempotency_key,
                status=OrderStatus.OPEN,
                created_at=datetime.now(timezone.utc),
                updated_at=datetime.now(timezone.utc),
            )
            self._orders[order.order_id] = order
            logger.info("alpaca_order_placed", symbol=order.symbol, side=order.side, qty=order.qty)
            return order

        except ImportError:
            # Fallback to REST
            return await self._place_order_rest(order_event)

    async def _place_order_rest(self, order_event: OrderEvent) -> Order:
        import aiohttp
        headers = {
            "APCA-API-KEY-ID": self._api_key,
            "APCA-API-SECRET-KEY": self._secret,
        }
        body: dict[str, Any] = {
            "symbol": order_event.symbol,
            "qty": str(order_event.qty),
            "side": order_event.side,
            "type": order_event.order_type,
            "time_in_force": "day",
            "client_order_id": order_event.idempotency_key or str(uuid.uuid4()),
        }
        if order_event.order_type == "limit":
            body["limit_price"] = str(order_event.price)

        async with aiohttp.ClientSession() as session:
            async with session.post(
                f"{self._base_url}/v2/orders", json=body, headers=headers
            ) as resp:
                resp.raise_for_status()
                data = await resp.json()

        order = Order(
            order_id=str(data["id"]),
            symbol=order_event.symbol,
            side=order_event.side,
            qty=order_event.qty,
            order_type=order_event.order_type,
            price=order_event.price,
            strategy_id=order_event.strategy_id,
            idempotency_key=order_event.idempotency_key,
            status=OrderStatus.OPEN,
            created_at=datetime.now(timezone.utc),
            updated_at=datetime.now(timezone.utc),
        )
        self._orders[order.order_id] = order
        return order

    def _check_pdt(self) -> None:
        today = date.today()
        # Clean trades older than 5 business days
        cutoff = _business_days_ago(today, 5)
        while self._day_trades and self._day_trades[0] < cutoff:
            self._day_trades.popleft()

        pdt_limit = int(self._cfg.model_extra.get("pdt_day_trade_limit", 3))
        if len(self._day_trades) >= pdt_limit:
            raise RuntimeError(
                f"PDT limit reached: {len(self._day_trades)} day trades in rolling 5 business days"
            )

    def record_day_trade(self) -> None:
        self._day_trades.append(date.today())

    async def cancel_order(self, order_id: str, symbol: str) -> bool:
        try:
            import aiohttp
            headers = {
                "APCA-API-KEY-ID": self._api_key,
                "APCA-API-SECRET-KEY": self._secret,
            }
            async with aiohttp.ClientSession() as session:
                async with session.delete(
                    f"{self._base_url}/v2/orders/{order_id}", headers=headers
                ) as resp:
                    if resp.status in (200, 204):
                        if order_id in self._orders:
                            self._orders[order_id].status = OrderStatus.CANCELLED
                        return True
            return False
        except Exception as e:
            logger.warning("alpaca_cancel_failed", order_id=order_id, error=str(e))
            return False

    async def get_order_status(self, order_id: str, symbol: str) -> Optional[Order]:
        return self._orders.get(order_id)

    async def get_open_orders(self, symbol: Optional[str] = None) -> list[Order]:
        return [o for o in self._orders.values() if not o.is_complete
                and (symbol is None or o.symbol == symbol)]

    async def get_account_balance(self) -> dict[str, float]:
        try:
            import aiohttp
            headers = {
                "APCA-API-KEY-ID": self._api_key,
                "APCA-API-SECRET-KEY": self._secret,
            }
            async with aiohttp.ClientSession() as session:
                async with session.get(
                    f"{self._base_url}/v2/account", headers=headers
                ) as resp:
                    resp.raise_for_status()
                    data = await resp.json()
                    return {
                        "cash": float(data.get("cash", 0)),
                        "equity": float(data.get("equity", 0)),
                        "buying_power": float(data.get("buying_power", 0)),
                    }
        except Exception:
            return {"cash": 0.0}

    async def sync_positions(self) -> list[dict]:
        try:
            import aiohttp
            headers = {
                "APCA-API-KEY-ID": self._api_key,
                "APCA-API-SECRET-KEY": self._secret,
            }
            async with aiohttp.ClientSession() as session:
                async with session.get(
                    f"{self._base_url}/v2/positions", headers=headers
                ) as resp:
                    resp.raise_for_status()
                    return await resp.json()
        except Exception:
            return []


def _business_days_ago(from_date: date, n: int) -> date:
    count = 0
    current = from_date
    while count < n:
        current = date.fromordinal(current.toordinal() - 1)
        if current.weekday() < 5:
            count += 1
    return current
