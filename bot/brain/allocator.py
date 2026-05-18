"""
StrategyAllocator — maps {regime, strategy_metrics} → allocation decisions.

Decision hierarchy (first matching rule wins):
  1. Not enough data → keep defaults, no change
  2. Extreme losing streak → disable strategy
  3. Auto re-enable if streak has cleared and strategy was disabled
  4. Consecutive losses above threshold → defensive
  5. Regime mismatch + bad Sharpe → defensive
  6. Good Sharpe + regime match → aggressive
  7. Default → normal

Parameter overrides are also emitted based on the vol regime:
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
        min_trades: int = 5,
        sharpe_aggressive: float = 0.7,
        sharpe_defensive: float = 0.15,
        sharpe_disable: float = -0.6,
        losses_defensive: int = 3,
        losses_disable: int = 7,
        losses_reenable: int = 1,       # re-enable once streak drops below this
    ) -> None:
        self._min_trades = min_trades
        self._sharpe_aggressive = sharpe_aggressive
        self._sharpe_defensive = sharpe_defensive
        self._sharpe_disable = sharpe_disable
        self._losses_defensive = losses_defensive
        self._losses_disable = losses_disable
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
        affinity = STRATEGY_REGIME_AFFINITY.get(strategy_id, [])
        regime_match = (not affinity) or (regime in affinity) or (regime == MarketRegime.UNKNOWN)

        # ── 2. Extreme streak → disable ─────────────────────────────────────
        if streak >= self._losses_disable:
            return AllocationDecision(
                risk_mode=RiskMode.DEFENSIVE,
                enabled=False,
                param_overrides={},
                reason=f"disabled: {streak} consecutive losses (threshold {self._losses_disable})",
            )

        # ── 3. Re-enable after streak cleared ───────────────────────────────
        if not currently_enabled and streak < self._losses_reenable:
            return AllocationDecision(
                risk_mode=RiskMode.DEFENSIVE,
                enabled=True,
                param_overrides=self._param_overrides(regime, strategy_id),
                reason=f"re-enabled: losing streak resolved (streak={streak})",
            )

        if not currently_enabled:
            # Still disabled — streak hasn't cleared yet
            return AllocationDecision(
                risk_mode=RiskMode.DEFENSIVE,
                enabled=False,
                param_overrides={},
                reason=f"still disabled: streak={streak} >= reenable threshold {self._losses_reenable}",
            )

        # ── 4. Consecutive losses threshold → defensive ──────────────────────
        if streak >= self._losses_defensive:
            return AllocationDecision(
                risk_mode=RiskMode.DEFENSIVE,
                enabled=True,
                param_overrides=self._param_overrides(regime, strategy_id),
                reason=f"defensive: {streak} consecutive losses",
            )

        # ── 5. Bad Sharpe + regime mismatch → defensive ─────────────────────
        if sharpe < self._sharpe_defensive or not regime_match:
            reason_parts = []
            if sharpe < self._sharpe_defensive:
                reason_parts.append(f"sharpe={sharpe:.2f}")
            if not regime_match:
                reason_parts.append(f"regime_mismatch ({regime.value})")
            return AllocationDecision(
                risk_mode=RiskMode.DEFENSIVE,
                enabled=True,
                param_overrides=self._param_overrides(regime, strategy_id),
                reason="defensive: " + ", ".join(reason_parts),
            )

        # ── 6. High Sharpe + regime match → aggressive ───────────────────────
        if sharpe >= self._sharpe_aggressive and regime_match:
            return AllocationDecision(
                risk_mode=RiskMode.AGGRESSIVE,
                enabled=True,
                param_overrides=self._param_overrides(regime, strategy_id),
                reason=f"aggressive: sharpe={sharpe:.2f}, regime aligned ({regime.value})",
            )

        # ── 7. Default ───────────────────────────────────────────────────────
        return AllocationDecision(
            risk_mode=RiskMode.NORMAL,
            enabled=True,
            param_overrides=self._param_overrides(regime, strategy_id),
            reason=f"normal: sharpe={sharpe:.2f}, regime={regime.value}",
        )

    @staticmethod
    def _param_overrides(regime: MarketRegime, strategy_id: str) -> dict[str, float]:
        overrides: dict[str, float] = {}

        # ATR multiplier: wider in high-vol, tighter in low-vol
        if regime == MarketRegime.HIGH_VOL:
            overrides["atr_multiplier"] = 2.5
        elif regime == MarketRegime.LOW_VOL:
            overrides["atr_multiplier"] = 1.5
        else:
            overrides["atr_multiplier"] = 2.0

        # Mean reversion RSI thresholds adapt to vol regime
        if strategy_id == "mean_reversion":
            if regime == MarketRegime.HIGH_VOL:
                overrides["rsi_oversold"] = 25.0
                overrides["rsi_overbought"] = 75.0
            elif regime == MarketRegime.LOW_VOL:
                overrides["rsi_oversold"] = 33.0
                overrides["rsi_overbought"] = 67.0
            # RANGING/TRENDING: keep config defaults (no override)

        return overrides
