"""Unit tests for the Brain meta-controller layer."""
from __future__ import annotations

import pytest
import pandas as pd
import numpy as np
from datetime import datetime, timezone
from pathlib import Path


# ── helpers ───────────────────────────────────────────────────────────────────

from bot.portfolio.tracker import TradeSummary


_TS = datetime(2024, 1, 1, tzinfo=timezone.utc)


def _trade(net_pnl: float, strategy_id: str = "ema", gross_pnl: float | None = None) -> TradeSummary:
    gp = gross_pnl if gross_pnl is not None else net_pnl * 1.1
    return TradeSummary(
        symbol="BTCUSDT",
        strategy_id=strategy_id,
        side="long",
        entry_price=30000.0,
        exit_price=30000.0 + net_pnl / 0.001,
        qty=0.001,
        gross_pnl=gp,
        fees_paid=abs(gp - net_pnl),
        net_pnl=net_pnl,
        opened_at=_TS,
        closed_at=_TS,
        duration_seconds=3600.0,
    )


# ── PerformanceMonitor ────────────────────────────────────────────────────────

from bot.brain.monitor import PerformanceMonitor


def test_performance_monitor_empty():
    mon = PerformanceMonitor(["ema"])
    m = mon.get_metrics("ema")
    assert m is not None
    assert m.win_rate == 0.0
    assert m.total_trades == 0


def test_performance_monitor_ingest_and_metrics():
    mon = PerformanceMonitor(["ema"])
    trades = [_trade(100), _trade(-50), _trade(80)]
    mon.ingest_new_trades(trades)
    m = mon.get_metrics("ema")
    assert m.total_trades == 3
    assert abs(m.win_rate - 2 / 3) < 1e-6
    assert m.total_net_pnl == pytest.approx(130.0)


def test_performance_monitor_consecutive_losses():
    mon = PerformanceMonitor(["ema"])
    trades = [_trade(100), _trade(-30), _trade(-40), _trade(-20)]
    mon.ingest_new_trades(trades)
    m = mon.get_metrics("ema")
    assert m.consecutive_losses == 3
    assert m.consecutive_wins == 0


def test_performance_monitor_deduplicate_trades():
    mon = PerformanceMonitor(["ema"])
    trades = [_trade(100)]
    mon.ingest_new_trades(trades)
    mon.ingest_new_trades(trades)  # same list again — should not double-count
    m = mon.get_metrics("ema")
    assert m.total_trades == 1


def test_performance_monitor_unknown_strategy_ignored():
    mon = PerformanceMonitor(["ema"])
    trades = [_trade(100, strategy_id="breakout")]
    mon.ingest_new_trades(trades)  # should not raise; ignored
    m = mon.get_metrics("ema")
    assert m.total_trades == 0


def test_performance_monitor_profit_factor():
    mon = PerformanceMonitor(["ema"])
    trades = [_trade(200, gross_pnl=200), _trade(-100, gross_pnl=-100)]
    mon.ingest_new_trades(trades)
    m = mon.get_metrics("ema")
    assert m.profit_factor == pytest.approx(2.0)


def test_performance_monitor_profit_factor_no_losses():
    mon = PerformanceMonitor(["ema"])
    trades = [_trade(100), _trade(50)]
    mon.ingest_new_trades(trades)
    m = mon.get_metrics("ema")
    assert m.profit_factor >= 1.0  # returns 1.0 sentinel when no losses


def test_performance_monitor_multiple_strategies():
    mon = PerformanceMonitor(["ema", "breakout"])
    trades = [_trade(100, "ema"), _trade(-50, "breakout"), _trade(30, "ema")]
    mon.ingest_new_trades(trades)
    assert mon.get_metrics("ema").total_trades == 2
    assert mon.get_metrics("breakout").total_trades == 1


# ── RegimeDetector ────────────────────────────────────────────────────────────

from bot.brain.regime import RegimeDetector, MarketRegime


def _make_price_df(n: int = 100, trend: float = 0.001, vol: float = 0.005, seed: int = 42):
    rng = np.random.default_rng(seed)
    closes = [100.0]
    for _ in range(n - 1):
        r = trend + vol * rng.standard_normal()
        closes.append(closes[-1] * (1 + r))
    return pd.DataFrame({"close": closes})


def test_regime_detector_too_few_bars():
    det = RegimeDetector()
    df = _make_price_df(10)
    assert det.detect(df) == MarketRegime.UNKNOWN


def test_regime_detector_trending_up():
    det = RegimeDetector()
    df = _make_price_df(200, trend=0.01, vol=0.001, seed=7)
    assert det.detect(df) == MarketRegime.TRENDING_UP


def test_regime_detector_trending_down():
    det = RegimeDetector()
    df = _make_price_df(200, trend=-0.01, vol=0.001, seed=7)
    assert det.detect(df) == MarketRegime.TRENDING_DOWN


def test_regime_detector_high_vol():
    # Build a calm period followed by explosive volatility
    closes = list(np.linspace(100, 105, 150))
    rng = np.random.default_rng(99)
    for _ in range(50):
        closes.append(closes[-1] * (1 + 0.05 * rng.standard_normal()))
    df = pd.DataFrame({"close": closes})
    regime = RegimeDetector().detect(df)
    assert regime in (MarketRegime.HIGH_VOL, MarketRegime.TRENDING_UP, MarketRegime.TRENDING_DOWN)


def test_regime_detector_returns_known_regime():
    det = RegimeDetector()
    df = _make_price_df(200, trend=0.002, vol=0.003, seed=1)
    regime = det.detect(df)
    assert regime in set(MarketRegime)


# ── StrategyAllocator ─────────────────────────────────────────────────────────

from bot.brain.monitor import StrategyMetrics
from bot.brain.allocator import StrategyAllocator


def _make_metrics(
    strategy_id: str = "ema",
    trades: list | None = None,
    extra_losses: int = 0,
) -> StrategyMetrics:
    m = StrategyMetrics(strategy_id=strategy_id)
    if trades is None:
        trades = [_trade(100, strategy_id)] * 15 + [_trade(-30, strategy_id)] * 5
    for t in trades:
        m.record_trade(t)
    # Manually inject consecutive losses to test thresholds
    m.consecutive_losses = extra_losses
    return m


def test_allocator_warming_up():
    alloc = StrategyAllocator(min_trades=5)
    m = StrategyMetrics(strategy_id="ema")
    m.record_trade(_trade(100))
    m.record_trade(_trade(-50))  # only 2 trades — below min_trades
    dec = alloc.decide("ema", m, MarketRegime.TRENDING_UP, currently_enabled=True)
    assert "warm" in dec.reason.lower()
    assert dec.risk_mode == "normal" or dec.risk_mode.value == "normal"


def test_allocator_disable_requires_both_streak_and_bad_pf():
    """Disable requires BOTH extreme streak AND terrible profit_factor.
    A high-RR strategy with 10% WR regularly hits 7+ consecutive losses but
    is profitable overall — it must NOT be disabled based on streak alone."""
    alloc = StrategyAllocator(losses_disable=7, pf_disable=0.3)
    m = StrategyMetrics(strategy_id="ema")
    # Good trades (profit_factor > 0.3)
    for _ in range(20):
        m.record_trade(_trade(10))
    m.consecutive_losses = 7  # inject streak
    # profit_factor is > 0.3 (all profitable trades), so should NOT disable
    dec = alloc.decide("ema", m, MarketRegime.TRENDING_UP, currently_enabled=True)
    assert dec.enabled is True

    # Now inject terrible profit factor (all losing trades)
    m2 = StrategyMetrics(strategy_id="ema")
    for _ in range(20):
        m2.record_trade(_trade(-10))  # all losses
    m2.consecutive_losses = 7
    dec2 = alloc.decide("ema", m2, MarketRegime.TRENDING_UP, currently_enabled=True)
    assert dec2.enabled is False


def test_allocator_reenable_after_recovery():
    alloc = StrategyAllocator(losses_disable=7, losses_reenable=3, pf_defensive=0.7)
    m = StrategyMetrics(strategy_id="ema")
    # Add some trades so we're past warmup
    for _ in range(20):
        m.record_trade(_trade(10))
    m.consecutive_losses = 0  # streak cleared
    # profit_factor >= pf_defensive (all wins → PF = 1.0 > 0.7)
    dec = alloc.decide("ema", m, MarketRegime.TRENDING_UP, currently_enabled=False)
    assert dec.enabled is True
    mode = dec.risk_mode if isinstance(dec.risk_mode, str) else dec.risk_mode.value
    assert mode == "defensive"


def test_allocator_defensive_on_bad_pf_and_sharpe():
    """Defensive mode when profit_factor is low AND Sharpe is negative."""
    alloc = StrategyAllocator(pf_defensive=0.7)
    m = StrategyMetrics(strategy_id="ema")
    for _ in range(20):
        m.record_trade(_trade(-5))  # consistent small losses → bad PF and Sharpe
    dec = alloc.decide("ema", m, MarketRegime.TRENDING_UP, currently_enabled=True)
    mode = dec.risk_mode if isinstance(dec.risk_mode, str) else dec.risk_mode.value
    assert mode == "defensive"


def test_allocator_normal_default():
    alloc = StrategyAllocator()
    m = _make_metrics()
    dec = alloc.decide("ema", m, MarketRegime.TRENDING_UP, currently_enabled=True)
    # With decent metrics, should be normal or better
    mode = dec.risk_mode if isinstance(dec.risk_mode, str) else dec.risk_mode.value
    assert mode in ("normal", "aggressive")


def test_allocator_regime_mismatch_and_bad_sharpe_is_defensive():
    """Regime mismatch alone should NOT cut size if the strategy is performing well.
    Both mismatch AND bad Sharpe are required to trigger defensive mode."""
    alloc = StrategyAllocator(sharpe_defensive=-0.3)
    # EMA crossover in RANGING → mismatch, but _make_metrics gives good PF/Sharpe
    m = _make_metrics()
    dec = alloc.decide("ema_crossover", m, MarketRegime.RANGING, currently_enabled=True)
    mode = dec.risk_mode if isinstance(dec.risk_mode, str) else dec.risk_mode.value
    # Good metrics → should be NORMAL or better despite regime mismatch
    assert mode in ("normal", "aggressive")

    # With bad Sharpe AND mismatch → defensive
    m_bad = StrategyMetrics(strategy_id="ema_crossover")
    for _ in range(20):
        m_bad.record_trade(_trade(-5))
    dec2 = alloc.decide("ema_crossover", m_bad, MarketRegime.RANGING, currently_enabled=True)
    mode2 = dec2.risk_mode if isinstance(dec2.risk_mode, str) else dec2.risk_mode.value
    assert mode2 == "defensive"


# ── RiskManager per-strategy risk mode ───────────────────────────────────────

from bot.risk.manager import RiskManager
from bot.core.modes import RiskMode
from bot.core.events import Signal


def _make_risk_cfg():
    from bot.core.config import RiskConfig
    return RiskConfig(
        capital_usd=5000,
        risk_per_trade_pct=0.01,
        max_daily_loss_pct=0.03,
        min_r_after_fees=1.5,
        risk_mode="normal",
    )


def _make_broker_cfg():
    from bot.core.config import BrokerConfig
    return BrokerConfig(
        name="binance",
        asset_class="crypto",
        fee_schedule={"maker": 0.001, "taker": 0.001},
        slippage_estimate_bps=5.0,
    )


def _make_portfolio():
    from bot.portfolio.manager import PortfolioManager
    return PortfolioManager(initial_cash=5000.0, asset_class_map={"BTCUSDT": "crypto"})


def test_risk_manager_set_strategy_risk_mode():
    rm = RiskManager(_make_risk_cfg(), _make_broker_cfg(), _make_portfolio())
    rm.set_risk_mode("ema_crossover", RiskMode.DEFENSIVE)
    assert rm.get_risk_mode("ema_crossover") == RiskMode.DEFENSIVE


def test_risk_manager_get_fallback_to_global():
    rm = RiskManager(_make_risk_cfg(), _make_broker_cfg(), _make_portfolio())
    assert rm.get_risk_mode("ema_crossover") == RiskMode.NORMAL


def test_risk_manager_strategy_risk_modes_dict():
    rm = RiskManager(_make_risk_cfg(), _make_broker_cfg(), _make_portfolio())
    rm.set_risk_mode("ema_crossover", RiskMode.AGGRESSIVE)
    rm.set_risk_mode("breakout", RiskMode.DEFENSIVE)
    modes = rm.strategy_risk_modes()
    assert modes["ema_crossover"] == "aggressive"
    assert modes["breakout"] == "defensive"


def test_risk_manager_defensive_reduces_sizing():
    rm_n = RiskManager(_make_risk_cfg(), _make_broker_cfg(), _make_portfolio())
    rm_d = RiskManager(_make_risk_cfg(), _make_broker_cfg(), _make_portfolio())
    rm_d.set_risk_mode("ema_crossover", RiskMode.DEFENSIVE)

    def _sig():
        return Signal(
            strategy_id="ema_crossover",
            symbol="BTCUSDT",
            direction="long",
            strength=1.0,
            entry_price=30000.0,
            stop_loss=29400.0,
            take_profit=33000.0,
            timeframe="1h",
            timestamp=datetime.now(timezone.utc),
            metadata={},
        )

    qty_n, rej_n = rm_n.validate(_sig(), 5000.0)
    qty_d, rej_d = rm_d.validate(_sig(), 5000.0)
    assert rej_n is None
    assert rej_d is None
    assert qty_d < qty_n
