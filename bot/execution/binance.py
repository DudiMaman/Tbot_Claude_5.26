"""
BinanceBroker — REST + WebSocket user data stream.
Handles lot-size normalization, min notional, partial fills, and rate limits.
"""
from __future__ import annotations

import asyncio
import hashlib
import hmac
import json
import math
import os
import time
import uuid
import structlog
from datetime import datetime, timezone
from typing import Any, Optional
from urllib.parse import urlencode

import aiohttp

from bot.core.events import FillEvent, OrderEvent
from bot.core.config import BrokerConfig
from bot.execution.base import AbstractBroker
from bot.execution.order import Order, OrderStatus
from bot.utils.retry import async_retry

logger = structlog.get_logger(__name__)

_REST_URL = "https://api.binance.com"
_TESTNET_URL = "https://testnet.binance.vision"
_WS_USER_STREAM = "wss://stream.binance.com:9443/ws"
_WS_USER_STREAM_TESTNET = "wss://testnet.binance.vision/ws"


class BinanceBroker(AbstractBroker):
    def __init__(self, broker_config: BrokerConfig) -> None:
        self._cfg = broker_config
        testnet = os.environ.get("BINANCE_TESTNET", "true").lower() == "true"
        self._base_url = _TESTNET_URL if testnet else _REST_URL
        self._ws_base = _WS_USER_STREAM_TESTNET if testnet else _WS_USER_STREAM
        self._api_key = os.environ.get("BINANCE_API_KEY", "")
        self._secret = os.environ.get("BINANCE_SECRET", "")
        self._orders: dict[str, Order] = {}
        self._fill_callbacks: list = []
        self._weight_used: int = 0
        self._weight_reset_ts: float = time.time()
        self._weight_backoff_until: float = 0.0  # epoch seconds; sleep until this before next request
        self._listen_key: Optional[str] = None
        self._exchange_info: dict[str, Any] = {}
        self._ws_task: Optional[asyncio.Task] = None

    def register_fill_callback(self, cb) -> None:  # type: ignore[type-arg]
        self._fill_callbacks.append(cb)

    async def start(self) -> None:
        if not self._api_key or not self._secret:
            raise RuntimeError(
                "BINANCE_API_KEY and BINANCE_SECRET must be set before starting BinanceBroker"
            )
        await self._load_exchange_info()
        self._listen_key = await self._create_listen_key()
        if self._listen_key:
            self._ws_task = asyncio.create_task(self._user_stream_loop())
            asyncio.create_task(self._heartbeat_loop())

    async def stop(self) -> None:
        if self._ws_task:
            self._ws_task.cancel()

    # ------------------------------------------------------------------
    # Order management
    # ------------------------------------------------------------------

    @async_retry(max_attempts=4)
    async def place_order(self, order_event: OrderEvent) -> Order:
        symbol_info = self._exchange_info.get(order_event.symbol, {})
        qty = self._round_qty(order_event.qty, symbol_info)
        notional = qty * order_event.price if order_event.price > 0 else 0

        min_notional = symbol_info.get("minNotional", 10.0)
        if order_event.price > 0 and qty * order_event.price < min_notional:
            raise ValueError(
                f"Order notional {qty * order_event.price:.4f} < min notional {min_notional} for {order_event.symbol}"
            )

        params: dict[str, Any] = {
            "symbol": order_event.symbol,
            "side": order_event.side.upper(),
            "type": self._order_type(order_event.order_type),
            "quantity": qty,
            "newClientOrderId": order_event.idempotency_key or str(uuid.uuid4())[:16],
        }

        if order_event.order_type == "limit":
            params["price"] = order_event.price
            params["timeInForce"] = "GTC"
        elif order_event.order_type in ("stop_limit", "stop_loss"):
            params["stopPrice"] = order_event.stop_price
            if order_event.price > 0:
                params["price"] = order_event.price
                params["type"] = "STOP_LOSS_LIMIT"
                params["timeInForce"] = "GTC"
            else:
                params["type"] = "STOP_LOSS"

        resp = await self._signed_request("POST", "/api/v3/order", params)
        order = Order(
            order_id=str(resp.get("orderId", "")),
            symbol=resp.get("symbol", order_event.symbol),
            side=order_event.side,
            qty=float(resp.get("origQty", qty)),
            order_type=order_event.order_type,
            price=float(resp.get("price", 0)),
            strategy_id=order_event.strategy_id,
            idempotency_key=order_event.idempotency_key,
            status=OrderStatus.OPEN,
            created_at=datetime.now(timezone.utc),
            updated_at=datetime.now(timezone.utc),
        )
        self._orders[order.order_id] = order
        logger.info("order_placed", symbol=order.symbol, side=order.side, qty=order.qty, order_id=order.order_id)
        return order

    @async_retry(max_attempts=3)
    async def cancel_order(self, order_id: str, symbol: str) -> bool:
        try:
            await self._signed_request("DELETE", "/api/v3/order", {"symbol": symbol, "orderId": order_id})
            if order_id in self._orders:
                self._orders[order_id].status = OrderStatus.CANCELLED
            return True
        except Exception as e:
            logger.warning("cancel_failed", order_id=order_id, error=str(e))
            return False

    @async_retry(max_attempts=3)
    async def get_order_status(self, order_id: str, symbol: str) -> Optional[Order]:
        resp = await self._signed_request("GET", "/api/v3/order", {"symbol": symbol, "orderId": order_id})
        order = self._orders.get(order_id)
        if order and resp:
            order.qty_filled = float(resp.get("executedQty", 0))
            order.avg_fill_price = float(resp.get("cummulativeQuoteQty", 0)) / max(order.qty_filled, 1e-10)
            order.status = _map_binance_status(resp.get("status", ""))
        return order

    async def get_open_orders(self, symbol: Optional[str] = None) -> list[Order]:
        params: dict[str, Any] = {}
        if symbol:
            params["symbol"] = symbol
        resp = await self._signed_request("GET", "/api/v3/openOrders", params)
        return [self._orders[str(o["orderId"])] for o in resp if str(o["orderId"]) in self._orders]

    @async_retry(max_attempts=3)
    async def get_account_balance(self) -> dict[str, float]:
        resp = await self._signed_request("GET", "/api/v3/account", {})
        balances = {b["asset"]: float(b["free"]) for b in resp.get("balances", [])}
        return balances

    async def sync_positions(self) -> list[dict]:
        try:
            balances = await self.get_account_balance()
            return [{"asset": k, "free": v} for k, v in balances.items() if v > 0]
        except Exception:
            return []

    # ------------------------------------------------------------------
    # WebSocket user data stream
    # ------------------------------------------------------------------

    async def _user_stream_loop(self) -> None:
        while True:
            try:
                url = f"{self._ws_base}/{self._listen_key}"
                async with aiohttp.ClientSession() as session:
                    async with session.ws_connect(url, heartbeat=20) as ws:
                        logger.info("user_stream_connected")
                        async for msg in ws:
                            if msg.type == aiohttp.WSMsgType.TEXT:
                                await self._handle_user_event(json.loads(msg.data))
            except asyncio.CancelledError:
                return
            except Exception as e:
                logger.warning("user_stream_disconnected", error=str(e))
                await asyncio.sleep(5)

    async def _handle_user_event(self, event: dict[str, Any]) -> None:
        if event.get("e") != "executionReport":
            return

        order_id = str(event.get("i", ""))
        status = _map_binance_status(event.get("X", ""))
        qty_filled = float(event.get("z", 0))
        # "ap" = averagePrice (post-fill), "L" = lastExecutedPrice, "p" = orderPrice (pre-fill)
        avg_price = float(event.get("ap", 0)) or float(event.get("L", 0)) or float(event.get("p", 0))
        fee = float(event.get("n", 0))
        symbol = event.get("s", "")
        side = "buy" if event.get("S", "") == "BUY" else "sell"
        idem_key = event.get("c", "")

        if status in (OrderStatus.FILLED, OrderStatus.PARTIALLY_FILLED):
            fill = FillEvent(
                order_id=order_id,
                symbol=symbol,
                side=side,
                qty_filled=qty_filled,
                avg_price=avg_price,
                fee_paid=fee,
                timestamp=datetime.now(timezone.utc),
                idempotency_key=idem_key,
                is_partial=(status == OrderStatus.PARTIALLY_FILLED),
            )
            for cb in self._fill_callbacks:
                await cb(fill)

        if order_id in self._orders:
            self._orders[order_id].status = status

    # ------------------------------------------------------------------
    # REST helpers
    # ------------------------------------------------------------------

    async def _signed_request(
        self, method: str, endpoint: str, params: dict[str, Any]
    ) -> Any:
        wait = self._weight_backoff_until - time.time()
        if wait > 0:
            logger.info("rate_limit_backoff", sleep_seconds=round(wait, 1))
            await asyncio.sleep(wait)

        params["timestamp"] = int(time.time() * 1000)
        query = urlencode(params)
        sig = hmac.new(self._secret.encode(), query.encode(), hashlib.sha256).hexdigest()
        params["signature"] = sig

        headers = {"X-MBX-APIKEY": self._api_key}
        url = f"{self._base_url}{endpoint}"

        async with aiohttp.ClientSession() as session:
            if method == "GET":
                async with session.get(url, params=params, headers=headers) as resp:
                    self._track_weight(resp.headers.get("X-MBX-USED-WEIGHT-1M", "0"))
                    resp.raise_for_status()
                    return await resp.json()
            elif method == "POST":
                async with session.post(url, params=params, headers=headers) as resp:
                    self._track_weight(resp.headers.get("X-MBX-USED-WEIGHT-1M", "0"))
                    resp.raise_for_status()
                    return await resp.json()
            elif method == "DELETE":
                async with session.delete(url, params=params, headers=headers) as resp:
                    self._track_weight(resp.headers.get("X-MBX-USED-WEIGHT-1M", "0"))
                    resp.raise_for_status()
                    return await resp.json()

    def _track_weight(self, weight_str: str) -> None:
        try:
            self._weight_used = int(weight_str)
            limit = self._cfg.rest_weight_limit_per_minute
            threshold = self._cfg.rest_weight_backoff_threshold
            if self._weight_used > limit * threshold:
                # Pause new requests until next minute window resets
                self._weight_backoff_until = time.time() + 60.0
                logger.warning("rate_limit_approaching", weight_used=self._weight_used,
                               limit=limit, backoff_seconds=60)
        except ValueError:
            pass

    async def _create_listen_key(self) -> Optional[str]:
        try:
            headers = {"X-MBX-APIKEY": self._api_key}
            async with aiohttp.ClientSession() as session:
                async with session.post(
                    f"{self._base_url}/api/v3/userDataStream", headers=headers
                ) as resp:
                    resp.raise_for_status()
                    data = await resp.json()
                    return data.get("listenKey")
        except Exception as e:
            logger.warning("listen_key_failed", error=str(e))
            return None

    async def _heartbeat_loop(self) -> None:
        while True:
            await asyncio.sleep(30 * 60)   # every 30 minutes
            if self._listen_key:
                try:
                    headers = {"X-MBX-APIKEY": self._api_key}
                    async with aiohttp.ClientSession() as session:
                        await session.put(
                            f"{self._base_url}/api/v3/userDataStream",
                            headers=headers,
                            params={"listenKey": self._listen_key},
                        )
                except Exception as e:
                    logger.warning("heartbeat_failed", error=str(e))

    async def _load_exchange_info(self) -> None:
        try:
            async with aiohttp.ClientSession() as session:
                async with session.get(f"{self._base_url}/api/v3/exchangeInfo") as resp:
                    resp.raise_for_status()
                    data = await resp.json()
                    for s in data.get("symbols", []):
                        filters = {f["filterType"]: f for f in s.get("filters", [])}
                        self._exchange_info[s["symbol"]] = {
                            "stepSize": float(filters.get("LOT_SIZE", {}).get("stepSize", 0.0001)),
                            "minNotional": float(filters.get("MIN_NOTIONAL", {}).get("minNotional", 10.0)),
                        }
        except Exception as e:
            logger.warning("exchange_info_failed", error=str(e))

    def _round_qty(self, qty: float, symbol_info: dict) -> float:
        step = symbol_info.get("stepSize", 0.0001)
        if step <= 0:
            return round(qty, 8)
        return math.floor(qty / step) * step

    def _order_type(self, order_type: str) -> str:
        return {
            "market": "MARKET",
            "limit": "LIMIT",
            "stop_limit": "STOP_LOSS_LIMIT",
            "stop_loss": "STOP_LOSS",
        }.get(order_type, "MARKET")


def _map_binance_status(status: str) -> OrderStatus:
    return {
        "NEW": OrderStatus.OPEN,
        "PARTIALLY_FILLED": OrderStatus.PARTIALLY_FILLED,
        "FILLED": OrderStatus.FILLED,
        "CANCELED": OrderStatus.CANCELLED,
        "REJECTED": OrderStatus.REJECTED,
        "EXPIRED": OrderStatus.EXPIRED,
    }.get(status, OrderStatus.PENDING)
