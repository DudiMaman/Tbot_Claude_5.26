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
    ) -> None:
        self._rcfg = risk_config
        self._bcfg = broker_config
        self._factory = strategy_factory
        self._train_periods = train_periods
        self._test_periods = test_periods
        self._output_dir = output_dir

    async def run(
        self,
        df: pd.DataFrame,
        primary_tf: str = "1h",
        step_size: float = 0.0001,
    ) -> list[dict[str, Any]]:
        """
        Split df into rolling windows and run backtest on each test window.
        Returns list of per-fold metrics.
        """
        total_len = len(df)
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

            train_df = df.iloc[start_idx:train_end_idx]
            test_df = df.iloc[train_end_idx:test_end_idx]

            logger.info(
                "walk_forward_fold",
                fold=fold,
                train_start=str(train_df.index[0]),
                train_end=str(train_df.index[-1]),
                test_start=str(test_df.index[0]),
                test_end=str(test_df.index[-1]),
            )

            # In-sample run
            engine_is = BacktestEngine(
                self._rcfg, self._bcfg,
                [self._factory()],
                output_dir=f"{self._output_dir}/fold_{fold}_insample",
            )
            in_sample_metrics = await engine_is.run({primary_tf: train_df}, primary_tf, step_size)

            # Out-of-sample run
            engine_oos = BacktestEngine(
                self._rcfg, self._bcfg,
                [self._factory()],
                output_dir=f"{self._output_dir}/fold_{fold}_outofsample",
            )
            out_sample_metrics = await engine_oos.run({primary_tf: test_df}, primary_tf, step_size)

            # Degradation check
            is_sharpe = in_sample_metrics.get("sharpe_ratio", 0)
            oos_sharpe = out_sample_metrics.get("sharpe_ratio", 0)
            degradation = (is_sharpe - oos_sharpe) / abs(is_sharpe) if is_sharpe != 0 else 1.0

            fold_results.append({
                "fold": fold,
                "train_bars": len(train_df),
                "test_bars": len(test_df),
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
