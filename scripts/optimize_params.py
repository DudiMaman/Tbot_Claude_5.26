#!/usr/bin/env python3
"""
CLI: grid-search strategy parameters over the backtesting engine.
Usage:
  python scripts/optimize_params.py --strategy ema_crossover --symbol BTCUSDT \
      --from 2023-01-01 --to 2023-12-31
"""
from __future__ import annotations

import argparse
import asyncio
import json
import sys
from datetime import date
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from bot.backtesting.simulator import optimize_params, run_vectorized
from bot.data.historical import HistoricalLoader


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--strategy", default="ema_crossover")
    parser.add_argument("--symbol", default="BTCUSDT")
    parser.add_argument("--from", dest="date_from", required=True)
    parser.add_argument("--to", dest="date_to", required=True)
    parser.add_argument("--timeframe", default="1h")
    return parser.parse_args()


def ema_signal_fn(df, ema_fast=9, ema_slow=21, adx_threshold=25):
    """Simple EMA crossover signal for vectorized sweep."""
    try:
        import pandas_ta as ta
        import pandas as pd

        df = df.copy()
        df.ta.ema(length=ema_fast, append=True, col_names=[f"ema_f"])
        df.ta.ema(length=ema_slow, append=True, col_names=[f"ema_s"])
        df.ta.adx(length=14, append=True)

        adx_col = f"ADX_14"
        entries = (
            (df["ema_f"].shift(1) < df["ema_s"].shift(1)) &
            (df["ema_f"] > df["ema_s"]) &
            (df[adx_col] > adx_threshold)
        ).fillna(False)

        exits = (
            (df["ema_f"].shift(1) > df["ema_s"].shift(1)) &
            (df["ema_f"] < df["ema_s"])
        ).fillna(False)

        return entries, exits
    except Exception as e:
        raise ValueError(f"Signal computation failed: {e}")


_PARAM_GRIDS = {
    "ema_crossover": {
        "ema_fast": [5, 9, 13],
        "ema_slow": [21, 34, 50],
        "adx_threshold": [20.0, 25.0, 30.0],
    }
}

_SIGNAL_FNS = {
    "ema_crossover": ema_signal_fn,
}


async def main() -> None:
    args = parse_args()
    start = date.fromisoformat(args.date_from)
    end = date.fromisoformat(args.date_to)

    loader = HistoricalLoader()
    df = await loader.fetch_crypto(args.symbol, args.timeframe, start, end)
    if df.empty:
        print("No data.")
        sys.exit(1)

    param_grid = _PARAM_GRIDS.get(args.strategy)
    signal_fn = _SIGNAL_FNS.get(args.strategy)
    if not param_grid or not signal_fn:
        print(f"No optimization grid for strategy: {args.strategy}")
        sys.exit(1)

    print(f"Running grid search: {len(param_grid)} param axes on {len(df)} bars...")
    results = optimize_params(df, param_grid, signal_fn)

    if results.empty:
        print("No results (vectorbt may not be installed).")
        sys.exit(0)

    print("\nTop 10 parameter combinations by Sharpe ratio:")
    print(results.head(10).to_string(index=False))

    out = Path("reports") / f"optimize_{args.strategy}_{args.symbol}.csv"
    out.parent.mkdir(exist_ok=True)
    results.to_csv(out, index=False)
    print(f"\nFull results saved to {out}")


if __name__ == "__main__":
    asyncio.run(main())
