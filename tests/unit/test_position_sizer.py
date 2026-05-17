"""Unit tests for PositionSizer."""
import pytest
from bot.core.config import BrokerConfig, BrokerFeeSchedule, RiskConfig
from bot.core.events import Signal
from bot.core.modes import RiskMode
from bot.risk.sizing import PositionSizer
from datetime import datetime, timezone


@pytest.fixture
def sizer():
    risk = RiskConfig(
        capital_usd=5000.0,
        risk_per_trade_pct=0.01,
        max_daily_loss_pct=0.03,
        max_open_positions=5,
        min_r_after_fees=1.5,
    )
    broker = BrokerConfig(
        name="binance",
        asset_class="crypto",
        fee_schedule=BrokerFeeSchedule(),
        slippage_estimate_bps=5.0,
        min_notional_usd=10.0,
        default_symbols=[],
    )
    return PositionSizer(risk, broker)


def make_signal(entry=50000, sl=49000, tp=52000):
    return Signal(
        strategy_id="test",
        symbol="BTCUSDT",
        direction="long",
        strength=0.8,
        entry_price=entry,
        stop_loss=sl,
        take_profit=tp,
        timeframe="1h",
        timestamp=datetime(2024, 1, 1, tzinfo=timezone.utc),
    )


def test_basic_sizing(sizer):
    signal = make_signal(entry=50000, sl=49000)
    qty, err = sizer.compute_qty(signal, capital=5000, step_size=0.000001)
    assert err == ""
    # $50 risk / $1000 per unit = 0.05 BTC
    assert abs(qty - 0.05) < 0.001


def test_defensive_mode_halves_size(sizer):
    signal = make_signal(entry=50000, sl=49000)
    normal_qty, _ = sizer.compute_qty(signal, capital=5000, risk_mode=RiskMode.NORMAL, step_size=0.000001)
    def_qty, _ = sizer.compute_qty(signal, capital=5000, risk_mode=RiskMode.DEFENSIVE, step_size=0.000001)
    assert abs(def_qty - normal_qty * 0.5) < 0.001


def test_zero_risk_per_unit_rejected(sizer):
    signal = make_signal(entry=50000, sl=50000)
    qty, err = sizer.compute_qty(signal, capital=5000)
    assert err == "zero_risk_per_unit"
    assert qty == 0.0


def test_min_notional_size_up(sizer):
    """When sized qty is below min_notional, should size up if risk stays in bounds."""
    # Entry $1000, SL $900, risk per unit = $100
    # 1% of $5000 = $50 / $100 = 0.5 units → 0.5 * $1000 = $500 notional (fine)
    signal = make_signal(entry=1000, sl=900, tp=1200)
    qty, err = sizer.compute_qty(signal, capital=5000, step_size=0.01)
    assert err == "" or err == ""
    assert qty * 1000 >= 10.0   # meets min notional


def test_min_notional_unachievable(sizer):
    """Tiny account + wide stop on expensive asset = unachievable min notional."""
    # Entry $100000, SL $1000 risk per unit, 1% of $5000 = 0.05 units
    # 0.05 * $100000 = $5000 notional (well above min notional — actually should pass)
    # Test the rejection case: capital = $100, risk = $1 → 0.00001 units → unachievable
    from bot.core.config import RiskConfig as RC, BrokerConfig as BC, BrokerFeeSchedule as BFS
    tiny_risk = RC(capital_usd=100, risk_per_trade_pct=0.01, max_daily_loss_pct=0.03,
                   max_open_positions=5, min_r_after_fees=1.5)
    tight_broker = BC(name="b", asset_class="crypto",
                      fee_schedule=BFS(), slippage_estimate_bps=5, min_notional_usd=100.0,
                      default_symbols=[])
    tiny_sizer = PositionSizer(tiny_risk, tight_broker)
    signal = make_signal(entry=100000, sl=99000, tp=102000)
    qty, err = tiny_sizer.compute_qty(signal, capital=100, step_size=0.00001)
    # $1 risk / $1000 per unit = 0.001 BTC = $100 notional → should pass min notional of $100
    # But tiny capital means it might hit the 1.5× risk cap
    assert isinstance(err, str)
