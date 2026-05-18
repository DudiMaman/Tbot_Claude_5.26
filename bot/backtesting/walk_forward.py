"""Walk-forward test harness: rolling in-sample / out-of-sample splits."""
from __future__ import annotations

import asyncio
import structlog
from datetime import datetime
from typing import Any

import pandas as pd

from bot.core.config import BrokerConfig, RiskConfig
from bot.backtesting.engine import BacktestEngine
from bot.strategies.base import BaseStrategy

logger = structlog.get_logger(__name__)


class WalkForwardTester:
    def __init__(
        self,
        risk_config: RiskConfig,
        broker_config: BrokerConfig,
        strategy_factory,            # callable() → BaseStrategy
        train_periods: int = 4,      # number of out-of-sample periods in training window
        test_periods: int = 1,       # number of periods per test window
        output_dir: str = "reports/walk_forward",
        enable_brain: bool = True,
    ) -> None:
        self._rcfg = risk_config
        self._bcfg = broker_config
        self._factory = strategy_factory
        self._train_periods = train_periods
        self._test_periods = test_periods
        self._output_dir = output_dir
        self._enable_brain = enable_brain

    async def run(
        self,
        bars_by_tf: "dict[str, pd.DataFrame] | pd.DataFrame",
        primary_tf: str = "1h",
        step_size: float = 0.0001,
    ) -> list[dict[str, Any]]:
        """
        Split data into rolling windows and run backtest on each fold.
        bars_by_tf: dict of {timeframe: DataFrame} or a single DataFrame (legacy).
        Splits are applied to the primary TF; secondary TFs are sliced by timestamp.
        Returns list of per-fold metrics.
        """
        # Accept legacy single-DataFrame call
        if isinstance(bars_by_tf, pd.DataFrame):
            bars_by_tf = {primary_tf: bars_by_tf}

        primary_df = bars_by_tf[primary_tf]
        total_len = len(primary_df)
        period_size = total_len // (self._train_periods + self._test_periods + 1)

        if period_size < 50:
            raise ValueError("Insufficient data for walk-forward: need at least 50 bars per period")

        fold_results: list[dict[str, Any]] = []
        fold = 0
        start_idx = 0

        while True:
            train_end_idx = start_idx + self._train_periods * period_size
            test_end_idx = train_end_idx + self._test_periods * period_size

            if test_end_idx > total_len:
                break

            train_primary = primary_df.iloc[start_idx:train_end_idx]
            test_primary  = primary_df.iloc[train_end_idx:test_end_idx]

            train_ts_end = train_primary.index[-1]
            test_ts_start = test_primary.index[0]
            test_ts_end   = test_primary.index[-1]

            # Build multi-TF dicts, slicing secondary TFs by timestamp
            def _slice(ts_start, ts_end) -> "dict[str, pd.DataFrame]":
                result: dict[str, pd.DataFrame] = {}
                for tf, df in bars_by_tf.items():
                    if tf == primary_tf:
                        result[tf] = primary_df.loc[ts_start:ts_end]
                    else:
                        result[tf] = df.loc[:ts_end]
                return result

            train_bars = _slice(train_primary.index[0], train_ts_end)
            test_bars  = _slice(test_ts_start, test_ts_end)

            logger.info(
                "walk_forward_fold",
                fold=fold,
                train_start=str(train_primary.index[0]),
                train_end=str(train_ts_end),
                test_start=str(test_ts_start),
                test_end=str(test_ts_end),
            )

            # In-sample run
            engine_is = BacktestEngine(
                self._rcfg, self._bcfg,
                [self._factory()],
                output_dir=f"{self._output_dir}/fold_{fold}_insample",
                enable_brain=self._enable_brain,
            )
            in_sample_metrics = await engine_is.run(train_bars, primary_tf, step_size)

            # Out-of-sample run
            engine_oos = BacktestEngine(
                self._rcfg, self._bcfg,
                [self._factory()],
                output_dir=f"{self._output_dir}/fold_{fold}_outofsample",
                enable_brain=self._enable_brain,
            )
            out_sample_metrics = await engine_oos.run(test_bars, primary_tf, step_size)

            # Degradation check
            is_sharpe = in_sample_metrics.get("sharpe_ratio", 0)
            oos_sharpe = out_sample_metrics.get("sharpe_ratio", 0)
            degradation = (is_sharpe - oos_sharpe) / abs(is_sharpe) if is_sharpe != 0 else 1.0

            fold_results.append({
                "fold": fold,
                "train_bars": len(train_primary),
                "test_bars": len(test_primary),
                "in_sample": in_sample_metrics,
                "out_of_sample": out_sample_metrics,
                "sharpe_degradation_pct": round(degradation * 100, 2),
                "robust": degradation <= 0.30,
            })

            logger.info(
                "fold_complete",
                fold=fold,
                is_sharpe=round(is_sharpe, 3),
                oos_sharpe=round(oos_sharpe, 3),
                degradation_pct=round(degradation * 100, 2),
                robust=degradation <= 0.30,
            )

            start_idx += self._test_periods * period_size
            fold += 1

        robust_folds = sum(1 for r in fold_results if r["robust"])
        logger.info(
            "walk_forward_complete",
            total_folds=len(fold_results),
            robust_folds=robust_folds,
        )
        return fold_results
