"""Unit tests for circuit breakers."""
import pytest
from bot.core.config import RiskConfig
from bot.risk.circuit_breaker import DailyLossBreaker, KillSwitch, LosingStreakGuard
from bot.core.modes import RiskMode
from unittest.mock import patch
from pathlib import Path


@pytest.fixture
def cfg():
    return RiskConfig(
        capital_usd=5000.0,
        risk_per_trade_pct=0.01,
        max_daily_loss_pct=0.03,
        max_open_positions=5,
        min_r_after_fees=1.5,
        losing_streak_defensive=3,
        losing_streak_halt=6,
    )


def test_daily_loss_not_triggered_under_limit(cfg):
    breaker = DailyLossBreaker(cfg)
    event = breaker.check(-100.0, 5000.0)   # -100 is less than 3% of $5000 = $150
    assert event is None
    assert not breaker.is_triggered


def test_daily_loss_triggered_at_limit(cfg):
    breaker = DailyLossBreaker(cfg)
    event = breaker.check(-151.0, 5000.0)   # exceeds $150 limit
    assert event is not None
    assert event.reason == "daily_loss_limit"
    assert breaker.is_triggered


def test_daily_loss_resets(cfg):
    breaker = DailyLossBreaker(cfg)
    breaker.check(-200.0, 5000.0)
    assert breaker.is_triggered
    breaker.reset()
    assert not breaker.is_triggered


def test_losing_streak_switches_to_defensive(cfg):
    guard = LosingStreakGuard(cfg)
    mode = guard.update(3)
    assert mode == RiskMode.DEFENSIVE
    assert not guard.is_halted


def test_losing_streak_halts_at_threshold(cfg):
    guard = LosingStreakGuard(cfg)
    mode = guard.update(6)
    assert guard.is_halted
    assert mode == RiskMode.DEFENSIVE


def test_losing_streak_normal_below_threshold(cfg):
    guard = LosingStreakGuard(cfg)
    mode = guard.update(2)
    assert mode == RiskMode.NORMAL
    assert not guard.is_halted


def test_kill_switch_file(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    assert not KillSwitch.is_active()
    KillSwitch.activate()
    assert KillSwitch.is_active()
    KillSwitch.deactivate()
    assert not KillSwitch.is_active()


def test_kill_switch_env(monkeypatch):
    monkeypatch.setenv("KILL_SWITCH", "1")
    assert KillSwitch.is_active()
    monkeypatch.setenv("KILL_SWITCH", "0")
    assert not KillSwitch.is_active()
