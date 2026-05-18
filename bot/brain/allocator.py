"""
StrategyAllocator — maps {regime, strategy_metrics} → allocation decisions.

Decision hierarchy (first matching rule wins):
  1. Not enough data → keep defaults, no change
  2. Extreme streak AND terrible profit factor → disable strategy
     (profit_factor guard prevents disabling high-RR strategies that are
      briefly losing — a 10% WR strategy with 25R avg winners will hit
      7 consecutive losses 48% of the time; that is normal, not a failure)
  3. Auto re-enable if streak + profit_factor have recovered
  4. Still disabled and not yet recovered → stay disabled
  5. Bad profit factor + bad Sharpe → defensive
  6. Regime mismatch + bad Sharpe → defensive
  7. Good Sharpe + good profit factor + regime match → aggressive
  8. Default → normal

Parameter overrides emitted based on vol regime:
  HIGH_VOL → wider ATR stop (2.5×)
  LOW_VOL  → tighter ATR stop (1.5×)
  else     → standard (2.0×)

RSI thresholds for mean reversion adapt to vol:
  HIGH_VOL → looser (25/75) to avoid false entries in spikes
  LOW_VOL  → tighter (33/67) since reversions are shallower
"""
from __future__ import annotations

from dataclasses import dataclass, field

from bot.brain.monitor import StrategyMetrics
from bot.brain.regime import MarketRegime, STRATEGY_REGIME_AFFINITY
from bot.core.modes import RiskMode


@dataclass
class AllocationDecision:
    risk_mode: RiskMode
    enabled: bool
    param_overrides: dict[str, float]
    reason: str


class StrategyAllocator:
    def __init__(
        self,
        min_trades: int = 15,           # raised: 5 is too few for 10% WR strategies
        sharpe_aggressive: float = 0.5,
        sharpe_defensive: float = -0.3,
        losses_defensive: int = 12,     # raised from 3: 3 losses in a row is normal at 10% WR
        losses_disable: int = 20,       # raised from 7: P(20 in a row @ 10% WR) = 12%
        pf_disable: float = 0.3,        # profit factor must ALSO be terrible to disable
        pf_defensive: float = 0.7,      # profit factor for defensive mode
        pf_aggressive: float = 1.5,     # profit factor for aggressive mode
        losses_reenable: int = 3,       # re-enable once streak drops below this
    ) -> None:
        self._min_trades = min_trades
        self._sharpe_aggressive = sharpe_aggressive
        self._sharpe_defensive = sharpe_defensive
        self._losses_defensive = losses_defensive
        self._losses_disable = losses_disable
        self._pf_disable = pf_disable
        self._pf_defensive = pf_defensive
        self._pf_aggressive = pf_aggressive
        self._losses_reenable = losses_reenable

    def decide(
        self,
        strategy_id: str,
        metrics: StrategyMetrics,
        regime: MarketRegime,
        currently_enabled: bool,
    ) -> AllocationDecision:
        # ── 1. Insufficient data ────────────────────────────────────────────
        if metrics.total_trades < self._min_trades:
            return AllocationDecision(
                risk_mode=RiskMode.NORMAL,
                enabled=True,
                param_overrides=self._param_overrides(regime, strategy_id),
                reason=f"warming_up ({metrics.total_trades}/{self._min_trades} trades)",
            )

        streak = metrics.consecutive_losses
        sharpe = metrics.rolling_sharpe
        pf = metrics.profit_factor
        affinity = STRATEGY_REGIME_AFFINITY.get(strategy_id, [])
        regime_match = (not affinity) or (regime in affinity) or (regime == MarketRegime.UNKNOWN)

        # ── 2. Extreme streak AND terrible profit factor → disable ──────────
        # Both conditions required: high-RR strategies (10% WR, 15R winners)
        # regularly hit 7-10 consecutive losses but are profitable overall.
        # Only disable if the money is actually being destroyed (PF < 0.3).
        if streak >= self._losses_disable and pf < self._pf_disable:
            return AllocationDecision(
                risk_mode=RiskMode.DEFENSIVE,
                enabled=False,
                param_overrides={},
                reason=(
                    f"disabled: {streak} consecutive losses and "
                    f"profit_factor={pf:.2f} < {self._pf_disable}"
                ),
            )

        # ── 3. Re-enable after streak + PF have recovered ───────────────────
        if not currently_enabled and streak < self._losses_reenable and pf >= self._pf_defensive:
            return AllocationDecision(
                risk_mode=RiskMode.DEFENSIVE,
                enabled=True,
                param_overrides=self._param_overrides(regime, strategy_id),
                reason=f"re-enabled: streak={streak}, profit_factor={pf:.2f}",
            )

        if not currently_enabled:
            # Still disabled — conditions haven't recovered yet
            return AllocationDecision(
                risk_mode=RiskMode.DEFENSIVE,
                enabled=False,
                param_overrides={},
                reason=f"still disabled: streak={streak}, profit_factor={pf:.2f}",
            )

        # ── 4. Bad profit factor + bad Sharpe → defensive ───────────────────
        # Use PF as the primary guard: if the strategy is consistently losing
        # more than it wins (PF < 0.7) AND the Sharpe is negative, cut size.
        if pf < self._pf_defensive and sharpe < self._sharpe_defensive:
            return AllocationDecision(
                risk_mode=RiskMode.DEFENSIVE,
                enabled=True,
                param_overrides=self._param_overrides(regime, strategy_id),
                reason=f"defensive: profit_factor={pf:.2f}, sharpe={sharpe:.2f}",
            )

        # ── 5. Regime mismatch + bad Sharpe → defensive ─────────────────────
        if not regime_match and sharpe < self._sharpe_defensive:
            return AllocationDecision(
                risk_mode=RiskMode.DEFENSIVE,
                enabled=True,
                param_overrides=self._param_overrides(regime, strategy_id),
                reason=f"defensive: regime_mismatch ({regime.value}), sharpe={sharpe:.2f}",
            )

        # ── 6. Strong metrics + regime match → aggressive ────────────────────
        if (
            sharpe >= self._sharpe_aggressive
            and pf >= self._pf_aggressive
            and regime_match
        ):
            return AllocationDecision(
                risk_mode=RiskMode.AGGRESSIVE,
                enabled=True,
                param_overrides=self._param_overrides(regime, strategy_id),
                reason=(
                    f"aggressive: sharpe={sharpe:.2f}, "
                    f"profit_factor={pf:.2f}, regime={regime.value}"
                ),
            )

        # ── 7. Default ───────────────────────────────────────────────────────
        return AllocationDecision(
            risk_mode=RiskMode.NORMAL,
            enabled=True,
            param_overrides=self._param_overrides(regime, strategy_id),
            reason=f"normal: sharpe={sharpe:.2f}, pf={pf:.2f}, regime={regime.value}",
        )

    @staticmethod
    def _param_overrides(regime: MarketRegime, strategy_id: str) -> dict[str, float]:
        overrides: dict[str, float] = {}

        # ATR stop multiplier: wider in high-vol, tighter in low-vol
        if regime == MarketRegime.HIGH_VOL:
            overrides["atr_multiplier"] = 2.5
        elif regime == MarketRegime.LOW_VOL:
            overrides["atr_multiplier"] = 1.5
        else:
            overrides["atr_multiplier"] = 2.0

        # Trailing stop: wider in trending regimes to ride 100-300% bull moves.
        # TRENDING_UP/DOWN: 10% — large enough to survive 10% pullbacks in a 200% rally.
        # HIGH_VOL: 8% — volatility spikes require room.
        # RANGING: 3% — mean reversion exits quickly.
        # LOW_VOL: 2% — tight trailing in quiet markets.
        if strategy_id != "mean_reversion":  # mean reversion uses fixed TP, not trailing
            if regime == MarketRegime.TRENDING_UP:
                overrides["trailing_stop_pct"] = 0.20   # 20%: survive 20% corrections in 300%+ bull runs
            elif regime == MarketRegime.TRENDING_DOWN:
                overrides["trailing_stop_pct"] = 0.15   # 15%: short-side bounces are violent
            elif regime == MarketRegime.HIGH_VOL:
                overrides["trailing_stop_pct"] = 0.12
            elif regime == MarketRegime.RANGING:
                overrides["trailing_stop_pct"] = 0.05
            elif regime == MarketRegime.LOW_VOL:
                overrides["trailing_stop_pct"] = 0.04

        # Mean reversion RSI thresholds adapt to vol regime
        if strategy_id == "mean_reversion":
            if regime == MarketRegime.HIGH_VOL:
                overrides["rsi_oversold"] = 25.0
                overrides["rsi_overbought"] = 75.0
            elif regime == MarketRegime.LOW_VOL:
                overrides["rsi_oversold"] = 33.0
                overrides["rsi_overbought"] = 67.0

        return overrides
