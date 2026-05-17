"""Unit tests for FeeModel."""
import pytest
from bot.core.config import BrokerConfig, BrokerFeeSchedule
from bot.execution.fee_model import FeeModel


@pytest.fixture
def binance_cfg() -> BrokerConfig:
    return BrokerConfig(
        name="binance",
        asset_class="crypto",
        fee_schedule=BrokerFeeSchedule(maker=0.001, taker=0.001),
        slippage_estimate_bps=5.0,
        min_notional_usd=10.0,
        default_symbols=["BTCUSDT"],
    )


@pytest.fixture
def fee_model(binance_cfg) -> FeeModel:
    return FeeModel(binance_cfg)


def test_trade_cost_round_trip(fee_model):
    """0.2% round-trip fee on a $1000 notional = $2 in fees."""
    cost = fee_model.compute_trade_cost(qty=0.01, entry_price=50000, exit_price=51000)
    # entry: 0.01 * 50000 * 0.001 = $0.50
    # exit:  0.01 * 51000 * 0.001 = $0.51
    assert abs(cost.commission_entry - 0.50) < 0.001
    assert abs(cost.commission_exit - 0.51) < 0.001


def test_expected_r_long(fee_model):
    """Net R:R must be less than gross R:R due to fees."""
    gross_r = 2.0  # TP is 2× the risk
    entry = 50000.0
    stop = 49000.0
    tp = 52000.0    # 2 × $1000 risk
    qty = 0.001

    r = fee_model.compute_expected_r(entry, stop, tp, qty, "long")
    # Gross R = (tp - entry) / (entry - sl) = 2000 / 1000 = 2.0
    # Net R must be less than 2.0 because fees eat into reward
    assert r < gross_r
    assert r > 0.0


def test_expected_r_zero_qty(fee_model):
    r = fee_model.compute_expected_r(50000, 49000, 52000, 0, "long")
    assert r == 0.0


def test_expected_r_short(fee_model):
    entry = 50000.0
    stop = 51000.0
    tp = 48000.0
    qty = 0.001

    r = fee_model.compute_expected_r(entry, stop, tp, qty, "short")
    assert r > 0.0
    assert r < 2.5  # some fee drag


def test_slippage_included_in_cost(fee_model):
    """Total cost must include slippage on top of commission."""
    cost = fee_model.compute_trade_cost(0.01, 50000, 51000)
    assert cost.slippage_entry > 0.0
    assert cost.slippage_exit > 0.0
    assert cost.total > cost.commission_entry + cost.commission_exit


def test_insufficient_r_at_tiny_profit(fee_model):
    """A trade with TP barely above entry should have very low R after fees."""
    entry = 50000.0
    stop = 49500.0   # $500 risk
    tp = 50010.0     # only $10 reward — fee-unfeasible
    qty = 0.001

    r = fee_model.compute_expected_r(entry, stop, tp, qty, "long")
    assert r < 0.1   # basically 0 or negative after fees
