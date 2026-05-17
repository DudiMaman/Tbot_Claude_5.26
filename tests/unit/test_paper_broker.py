"""Unit tests for PaperBroker."""
import pytest
import asyncio
from datetime import datetime, timezone

from bot.core.config import BrokerConfig, BrokerFeeSchedule
from bot.core.events import OHLCVBar, OrderEvent
from bot.execution.paper import PaperBroker
from bot.execution.order import OrderStatus


@pytest.fixture
def broker_cfg():
    return BrokerConfig(
        name="binance",
        asset_class="crypto",
        fee_schedule=BrokerFeeSchedule(maker=0.001, taker=0.001),
        slippage_estimate_bps=5.0,
        min_notional_usd=10.0,
        default_symbols=[],
    )


@pytest.fixture
def broker(broker_cfg):
    return PaperBroker(broker_cfg, initial_cash=5000.0)


def make_bar(price=50000.0, symbol="BTCUSDT"):
    return OHLCVBar(
        symbol=symbol,
        timeframe="1h",
        timestamp=datetime(2024, 1, 1, 12, 0, tzinfo=timezone.utc),
        open=price,
        high=price * 1.01,
        low=price * 0.99,
        close=price,
        volume=100.0,
    )


def make_order(symbol="BTCUSDT", side="buy", qty=0.001, order_type="market"):
    return OrderEvent(
        symbol=symbol,
        side=side,
        qty=qty,
        order_type=order_type,
        price=0.0,
        strategy_id="test",
        idempotency_key="test_key_001",
        timestamp=datetime(2024, 1, 1, 11, 0, tzinfo=timezone.utc),
    )


@pytest.mark.asyncio
async def test_place_and_fill(broker):
    order = await broker.place_order(make_order())
    assert order.status == OrderStatus.PENDING

    fills = await broker.on_bar(make_bar())
    assert len(fills) == 1
    fill = fills[0]
    assert fill.qty_filled == 0.001
    assert fill.fee_paid > 0
    assert fill.side == "buy"


@pytest.mark.asyncio
async def test_fee_deducted_from_cash(broker):
    initial_cash = broker.cash
    await broker.place_order(make_order(qty=0.001))
    await broker.on_bar(make_bar(price=50000))

    # Cash should decrease by: qty * price + fee
    expected_cost = 0.001 * 50000 * (1 + 0.001)  # price * (1 + fee_rate) approx
    assert broker.cash < initial_cash
    assert broker.cash > initial_cash - expected_cost * 1.1   # within 10% of expected


@pytest.mark.asyncio
async def test_cancel_order(broker):
    order = await broker.place_order(make_order())
    cancelled = await broker.cancel_order(order.order_id, "BTCUSDT")
    assert cancelled

    fills = await broker.on_bar(make_bar())
    assert len(fills) == 0


@pytest.mark.asyncio
async def test_no_fill_wrong_symbol(broker):
    await broker.place_order(make_order(symbol="BTCUSDT"))
    fills = await broker.on_bar(make_bar(symbol="ETHUSDT"))
    assert len(fills) == 0


@pytest.mark.asyncio
async def test_insufficient_cash_rejected(broker):
    broker._cash = 1.0   # only $1 left
    order = await broker.place_order(make_order(qty=1.0))   # $50000 order
    fills = await broker.on_bar(make_bar())
    filled = [f for f in fills if f.qty_filled > 0]
    assert len(filled) == 0
