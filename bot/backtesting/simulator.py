"""
Vectorized backtesting via vectorbt — fast parameter sweeps.
Falls back gracefully if vectorbt is not installed.
"""
from __future__ import annotations

import structlog
from typing import Any, Optional

import numpy as np
import pandas as pd

logger = structlog.get_logger(__name__)


def run_vectorized(
    df: pd.DataFrame,
    entries: pd.Series,           # Boolean series: True = enter long
    exits: pd.Series,             # Boolean series: True = exit
    sl_pct: float = 0.015,
    tp_pct: float = 0.03,
    fees_pct: float = 0.001,      # per side
    slippage_pct: float = 0.0005,
    initial_capital: float = 5000.0,
    symbol: str = "BT",
) -> dict[str, Any]:
    """
    Vectorized backtest using vectorbt.
    Returns metrics dict.
    """
    try:
        import vectorbt as vbt
    except ImportError:
        logger.warning("vectorbt not installed; skipping vectorized backtest")
        return {}

    close = df["close"]

    pf = vbt.Portfolio.from_signals(
        close,
        entries=entries.reindex(close.index, fill_value=False),
        exits=exits.reindex(close.index, fill_value=False),
        sl_stop=sl_pct,
        tp_stop=tp_pct,
        fees=fees_pct,
        slippage=slippage_pct,
        init_cash=initial_capital,
        freq="1h",
    )

    stats = pf.stats()
    return {
        "total_trades": int(stats.get("Total Trades", 0)),
        "win_rate": float(stats.get("Win Rate [%]", 0)) / 100,
        "profit_factor": float(stats.get("Profit Factor", 0)),
        "max_drawdown_pct": float(stats.get("Max Drawdown [%]", 0)),
        "sharpe_ratio": float(stats.get("Sharpe Ratio", 0)),
        "net_return_pct": float(stats.get("Total Return [%]", 0)),
        "equity_final": float(pf.final_value()),
    }


def optimize_params(
    df: pd.DataFrame,
    param_grid: dict[str, list],      # {"ema_fast": [5,9,13], "ema_slow": [21,34,50]}
    signal_fn,                        # callable(df, **params) -> (entries, exits)
    sl_pct: float = 0.015,
    tp_pct: float = 0.03,
    fees_pct: float = 0.001,
    initial_capital: float = 5000.0,
) -> pd.DataFrame:
    """Grid search over param_grid; returns sorted results DataFrame."""
    import itertools

    keys = list(param_grid.keys())
    values = list(param_grid.values())
    results = []

    for combo in itertools.product(*values):
        params = dict(zip(keys, combo))
        try:
            entries, exits = signal_fn(df, **params)
            metrics = run_vectorized(df, entries, exits, sl_pct, tp_pct, fees_pct,
                                     initial_capital=initial_capital)
            metrics.update(params)
            results.append(metrics)
        except Exception as e:
            logger.debug(f"Param combo {params} failed: {e}")

    if not results:
        return pd.DataFrame()

    result_df = pd.DataFrame(results)
    return result_df.sort_values("sharpe_ratio", ascending=False).reset_index(drop=True)
