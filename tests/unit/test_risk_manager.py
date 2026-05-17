"""Unit tests for RiskManager."""
import pytest
from datetime import datetime, timezone
from unittest.mock import patch

from bot.core.config import BrokerConfig, BrokerFeeSchedule, RiskConfig
from bot.core.events import Signal
from bot.core.modes import RiskMode
from bot.portfolio.manager import PortfolioManager
from bot.risk.manager import RiskManager


@pytest.fixture
def risk_cfg():
    return RiskConfig(
        capital_usd=5000.0,
        risk_per_trade_pct=0.01,
        max_daily_loss_pct=0.03,
        max_open_positions=5,
        min_r_after_fees=1.5,
        risk_mode="normal",
        execution_mode="paper",
    )


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
def portfolio():
    return PortfolioManager(initial_cash=5000.0)


@pytest.fixture
def risk_mgr(risk_cfg, broker_cfg, portfolio):
    return RiskManager(risk_cfg, broker_cfg, portfolio)


def make_signal(entry=50000.0, sl=49000.0, tp=52000.0, symbol="BTCUSDT"):
    return Signal(
        strategy_id="test",
        symbol=symbol,
        direction="long",
        strength=0.8,
        entry_price=entry,
        stop_loss=sl,
        take_profit=tp,
        timeframe="1h",
        timestamp=datetime(2024, 1, 1, tzinfo=timezone.utc),
    )


def test_valid_signal_approved(risk_mgr):
    signal = make_signal()
    qty, rejection = risk_mgr.validate(signal, capital=5000.0, step_size=0.000001)
    assert rejection is None
    assert qty > 0


def test_insufficient_r_rejected(risk_mgr):
    # TP barely above entry — will fail fee gate
    signal = make_signal(entry=50000, sl=49000, tp=50050)
    qty, rejection = risk_mgr.validate(signal, capital=5000.0)
    assert rejection is not None
    assert "insufficient_r" in rejection.reason


def test_insufficient_cash_rejected(risk_mgr, portfolio):
    # Drain cash
    portfolio._cash = 0.0
    signal = make_signal()
    qty, rejection = risk_mgr.validate(signal, capital=0.0)
    assert rejection is not None


def test_kill_switch_rejects(risk_mgr):
    with patch("bot.risk.circuit_breaker.KillSwitch.is_active", return_value=True):
        signal = make_signal()
        qty, rejection = risk_mgr.validate(signal, capital=5000.0)
        assert rejection is not None
        assert rejection.reason == "kill_switch_active"


def test_daily_loss_limit(risk_mgr, portfolio):
    # Simulate a large daily loss
    portfolio._tracker._daily_net_pnl = -200.0   # > 3% of $5000 = $150
    signal = make_signal()
    qty, rejection = risk_mgr.validate(signal, capital=5000.0)
    assert rejection is not None
    assert "daily_loss" in rejection.reason


def test_max_positions_rejected(risk_mgr, portfolio, risk_cfg):
    # Fill up positions
    portfolio._positions = {f"SYM{i}": object() for i in range(risk_cfg.max_open_positions)}
    signal = make_signal()
    qty, rejection = risk_mgr.validate(signal, capital=5000.0)
    assert rejection is not None
    assert rejection.reason == "max_open_positions_reached"


def test_position_sizing_respects_1pct(risk_mgr):
    signal = make_signal(entry=50000, sl=49000, tp=52000)
    qty, rejection = risk_mgr.validate(signal, capital=5000.0, step_size=0.000001)
    assert rejection is None
    # $50 max risk / $1000 per unit = 0.05 BTC max
    risk_dollars = qty * abs(50000 - 49000)
    assert risk_dollars <= 5000 * 0.01 * 1.6  # allow for min-notional size-up
