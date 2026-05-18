#!/usr/bin/env python3
"""
Phase 4 — Parameter optimizer (event-driven, no vectorbt required).

Runs a grid search over key strategy parameters using the BacktestEngine.
Splits data 70/30 in-sample / out-of-sample and ranks combinations by OOS Sharpe.

Usage:
  python scripts/optimize_params.py --strategy ema_crossover \
      --data-file data/synthetic/BTCUSDT_1h_2023-01-01_2024-12-31.parquet \
      --timeframe 1h

Output: reports/optimization/<strategy>/best_params.json
"""
from __future__ import annotations

import argparse
import asyncio
import itertools
import json
import sys
from pathlib import Path

import pandas as pd

sys.path.insert(0, str(Path(__file__).parent.parent))

from dotenv import load_dotenv

from bot.core.config import StrategyConfig, load_broker_config, load_risk_config, load_strategy_config
from bot.backtesting.engine import BacktestEngine
from bot.reporting.logger import configure_logging
from bot.strategies.ema_crossover import EMACrossoverStrategy
from bot.strategies.mean_reversion import MeanReversionStrategy
from bot.strategies.breakout import BreakoutStrategy
from bot.strategies.momentum_sniper import MomentumSniperStrategy

_STRATEGY_MAP = {
    "ema_crossover": EMACrossoverStrategy,
    "mean_reversion": MeanReversionStrategy,
    "breakout": BreakoutStrategy,
    "momentum_sniper": MomentumSniperStrategy,
}

_PARAM_GRIDS = {
    "ema_crossover": {
        "ema_fast": [7, 9, 12],
        "ema_slow": [18, 21, 26],
        "adx_threshold": [24.0, 27.0, 30.0],
        "take_profit_r": [2.5, 3.0, 4.0],
    },
    "mean_reversion": {
        "rsi_oversold": [25.0, 28.0, 30.0],
        "rsi_overbought": [70.0, 72.0, 75.0],
        "bb_std": [1.8, 2.0, 2.5],
        "take_profit_r": [2.0, 2.5, 3.0],
    },
    "breakout": {
        "lookback_bars": [15, 20, 25],
        "volume_surge_multiplier": [1.2, 1.4, 1.6],
        "atr_stop_multiplier": [1.5, 2.0, 2.5],
        "take_profit_r": [2.5, 3.0, 3.5],
    },
}


def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(description="Strategy parameter optimizer")
    p.add_argument("--strategy", required=True, choices=list(_STRATEGY_MAP))
    p.add_argument("--symbol", default="BTCUSDT")
    p.add_argument("--timeframe", default="1h")
    p.add_argument("--data-file", required=True)
    p.add_argument("--config-dir", default="config")
    p.add_argument("--out-dir", default="reports/optimization")
    p.add_argument("--top-n", type=int, default=5)
    p.add_argument("--train-pct", type=float, default=0.70)
    p.add_argument("--from", dest="date_from", default=None)
    p.add_argument("--to", dest="date_to", default=None)
    return p.parse_args()


def _load_and_resample(path: str, timeframe: str) -> pd.DataFrame:
    df = pd.read_parquet(path)
    if df.index.tz is None:
        df.index = df.index.tz_localize("UTC")
    _TF_HOURS = {"1m": 1/60, "5m": 5/60, "15m": 0.25, "30m": 0.5, "1h": 1, "4h": 4, "1D": 24}
    _RULE = {"1m": "1min", "5m": "5min", "15m": "15min", "1h": "1h", "4h": "4h", "1D": "1D"}
    if len(df) >= 2:
        gap_h = (df.index[1:] - df.index[:-1]).median().total_seconds() / 3600
        target_h = _TF_HOURS.get(timeframe, 1.0)
        if abs(target_h - gap_h) > 0.1 * target_h:
            df = df.resample(_RULE.get(timeframe, timeframe)).agg(
                {"open": "first", "high": "max", "low": "min", "close": "last", "volume": "sum"}
            ).dropna()
    return df


async def _run_one(
    strategy_name: str, params: dict, df_split: pd.DataFrame,
    risk_cfg, broker_cfg, base_cfg: StrategyConfig,
    symbol: str, timeframe: str, out_path: Path,
) -> dict:
    cfg_data = base_cfg.model_dump()
    cfg_data["symbols"] = [symbol]
    cfg_data.update(params)
    strategy_cfg = StrategyConfig(**cfg_data)

    engine = BacktestEngine(
        risk_cfg, broker_cfg,
        [_STRATEGY_MAP[strategy_name](strategy_cfg)],
        output_dir=str(out_path),
        enable_brain=False,
    )
    bars = {timeframe: df_split}
    if timeframe != "1D":
        daily = df_split.resample("1D").agg(
            {"open": "first", "high": "max", "low": "min", "close": "last", "volume": "sum"}
        ).dropna()
        if not daily.empty:
            bars["1D"] = daily

    return await engine.run(bars, primary_tf=timeframe)


async def main() -> None:
    load_dotenv()
    args = parse_args()
    configure_logging(log_level="WARNING")

    df = _load_and_resample(args.data_file, args.timeframe)
    print(f"Loaded {len(df)} bars ({args.timeframe})")

    split = int(len(df) * args.train_pct)
    df_train, df_test = df.iloc[:split], df.iloc[split:]
    print(f"Train: {len(df_train)} bars  |  Test: {len(df_test)} bars")

    risk_cfg = load_risk_config(args.config_dir)
    broker_cfg = load_broker_config("binance", args.config_dir)
    base_cfg = load_strategy_config(args.strategy, args.config_dir)

    grid = _PARAM_GRIDS.get(args.strategy, {})
    if not grid:
        print(f"No grid for {args.strategy}")
        sys.exit(1)

    param_names = list(grid.keys())
    combos = list(itertools.product(*grid.values()))
    total = len(combos)
    print(f"\nOptimizing {args.strategy}: {total} combinations\n")

    out_dir = Path(args.out_dir) / args.strategy
    out_dir.mkdir(parents=True, exist_ok=True)

    results = []
    for i, combo in enumerate(combos):
        params = dict(zip(param_names, combo))
        try:
            is_m = await _run_one(args.strategy, params, df_train, risk_cfg, broker_cfg,
                                  base_cfg, args.symbol, args.timeframe,
                                  out_dir / f"run_{i:04d}_is")
            oos_m = await _run_one(args.strategy, params, df_test, risk_cfg, broker_cfg,
                                   base_cfg, args.symbol, args.timeframe,
                                   out_dir / f"run_{i:04d}_oos")
            results.append({
                "params": params,
                "is_sharpe": is_m.get("sharpe_ratio", 0),
                "is_return": is_m.get("net_return_pct", 0),
                "is_trades": is_m.get("total_trades", 0),
                "oos_sharpe": oos_m.get("sharpe_ratio", 0),
                "oos_return": oos_m.get("net_return_pct", 0),
                "oos_trades": oos_m.get("total_trades", 0),
                "oos_win_rate": oos_m.get("win_rate", 0),
                "oos_pf": oos_m.get("profit_factor", 0),
            })
        except Exception as e:
            pass  # skip invalid param combos silently

        if (i + 1) % 20 == 0:
            best_so_far = max(results, key=lambda r: r["oos_sharpe"]) if results else {}
            print(f"  [{i+1}/{total}] Best OOS Sharpe={best_so_far.get('oos_sharpe', 0):.3f}  "
                  f"Params={best_so_far.get('params', {})}")

    if not results:
        print("No results.")
        sys.exit(1)

    results.sort(key=lambda r: r["oos_sharpe"], reverse=True)
    top = results[: args.top_n]

    print(f"\n{'='*72}")
    print(f"TOP {args.top_n} — {args.strategy.upper()} | OOS period: last {100-int(args.train_pct*100)}%")
    print(f"{'='*72}")
    print(f"{'Rank':<5} {'OOS Sharpe':>10} {'OOS Ret%':>9} {'OOS WR':>7} {'OOS PF':>7} {'IS Sharpe':>9}  Params")
    print("-" * 72)
    for rank, r in enumerate(top, 1):
        print(f"{rank:<5} {r['oos_sharpe']:>10.3f} {r['oos_return']:>9.2f} "
              f"{r['oos_win_rate']:>7.1%} {r['oos_pf']:>7.3f} {r['is_sharpe']:>9.3f}  {r['params']}")

    best_path = out_dir / "best_params.json"
    best_path.write_text(json.dumps({"strategy": args.strategy, "best": top[0], "all_top": top}, indent=2))
    print(f"\nBest params: {top[0]['params']}")
    print(f"Saved to: {best_path}")


if __name__ == "__main__":
    asyncio.run(main())
