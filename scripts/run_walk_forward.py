#!/usr/bin/env python3
"""
Phase 4 — Walk-forward validation CLI.

Splits historical data into rolling in-sample / out-of-sample windows and
runs the full backtest pipeline on each fold.  Reports per-fold Sharpe ratios
and flags folds where out-of-sample degrades by more than 30%.

Usage:
  python scripts/run_walk_forward.py --strategy ema_crossover \
      --data-file data/synthetic/BTCUSDT_1h_2023-01-01_2024-12-31.parquet \
      --timeframe 1h --train-periods 4 --test-periods 1

Output: reports/walk_forward/<strategy>/<timestamp>/
"""
from __future__ import annotations

import argparse
import asyncio
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

import pandas as pd

sys.path.insert(0, str(Path(__file__).parent.parent))

from dotenv import load_dotenv

from bot.core.config import load_broker_config, load_risk_config, load_strategy_config
from bot.backtesting.walk_forward import WalkForwardTester
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


def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(description="Walk-forward strategy validation")
    p.add_argument("--strategy", required=True, choices=list(_STRATEGY_MAP))
    p.add_argument("--no-brain", action="store_true", help="Disable Brain adaptive engine")
    p.add_argument("--symbol", default="BTCUSDT")
    p.add_argument("--timeframe", default="1h")
    p.add_argument("--data-file", required=True, help="Path to .parquet historical data file")
    p.add_argument("--config-dir", default="config")
    p.add_argument("--out-dir", default="reports/walk_forward")
    p.add_argument("--train-periods", type=int, default=4,
                   help="Number of periods in the training window (default: 4)")
    p.add_argument("--test-periods", type=int, default=1,
                   help="Number of periods per test window (default: 1)")
    p.add_argument("--market", default="crypto", choices=["crypto", "stocks"])
    return p.parse_args()


def _load_data(path: str, timeframe: str) -> pd.DataFrame:
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


def _build_bars_by_tf(primary_df: pd.DataFrame, primary_tf: str, strategy_cfg) -> dict:
    """Build {tf: DataFrame} dict for all TFs required by the strategy."""
    _RESAMPLE = {"1h": "1h", "4h": "4h", "1D": "1D", "1d": "1D"}

    bars: dict[str, pd.DataFrame] = {primary_tf: primary_df}
    required_tfs = set(strategy_cfg.timeframes.values()) - {primary_tf}

    for tf in required_tfs:
        rule = _RESAMPLE.get(tf)
        if rule and tf not in bars:
            if tf in ("1h", "1H") and primary_tf in ("15m", "5m", "1m"):
                bars[tf] = primary_df.resample("1h").agg(
                    {"open": "first", "high": "max", "low": "min", "close": "last", "volume": "sum"}
                ).dropna()
            elif rule:
                bars[tf] = primary_df.resample(rule).agg(
                    {"open": "first", "high": "max", "low": "min", "close": "last", "volume": "sum"}
                ).dropna()
    return bars


async def main() -> None:
    load_dotenv()
    args = parse_args()
    configure_logging(log_level="WARNING")

    broker_name = "binance" if args.market == "crypto" else "alpaca"
    risk_cfg = load_risk_config(args.config_dir)
    broker_cfg = load_broker_config(broker_name, args.config_dir)
    base_cfg = load_strategy_config(args.strategy, args.config_dir)

    df = _load_data(args.data_file, args.timeframe)
    print(f"Loaded {len(df)} bars ({args.timeframe})")
    bars_by_tf = _build_bars_by_tf(df, args.timeframe, base_cfg)
    tfs_loaded = {tf: len(d) for tf, d in bars_by_tf.items()}
    print(f"Timeframes: {tfs_loaded}")

    # Override symbol
    cfg_data = base_cfg.model_dump()
    cfg_data["symbols"] = [args.symbol]
    from bot.core.config import StrategyConfig
    strategy_cfg = StrategyConfig(**cfg_data)

    strategy_cls = _STRATEGY_MAP[args.strategy]

    def factory():
        return strategy_cls(strategy_cfg)

    ts = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
    out_dir = Path(args.out_dir) / args.strategy / ts
    out_dir.mkdir(parents=True, exist_ok=True)

    tester = WalkForwardTester(
        risk_config=risk_cfg,
        broker_config=broker_cfg,
        strategy_factory=factory,
        train_periods=args.train_periods,
        test_periods=args.test_periods,
        output_dir=str(out_dir),
        enable_brain=not args.no_brain,
    )

    print(f"\nRunning walk-forward: {args.strategy} | train={args.train_periods} periods, "
          f"test={args.test_periods} period(s)\n")

    folds = await tester.run(bars_by_tf, primary_tf=args.timeframe)

    if not folds:
        print("Not enough data for walk-forward splits.")
        sys.exit(1)

    # Print results table
    print(f"\n{'='*80}")
    print(f"WALK-FORWARD RESULTS — {args.strategy.upper()}")
    print(f"{'='*80}")
    header = (
        f"{'Fold':<5} {'IS Bars':>8} {'OOS Bars':>9} {'IS Sharpe':>10} "
        f"{'OOS Sharpe':>11} {'Degrad%':>8} {'Robust':>7}"
    )
    print(header)
    print("-" * 80)

    for r in folds:
        is_s = r["in_sample"].get("sharpe_ratio", 0)
        oos_s = r["out_of_sample"].get("sharpe_ratio", 0)
        robust_str = "YES" if r["robust"] else "NO"
        print(
            f"{r['fold']:<5} {r['train_bars']:>8} {r['test_bars']:>9} "
            f"{is_s:>10.3f} {oos_s:>11.3f} {r['sharpe_degradation_pct']:>8.1f}%  {robust_str:>7}"
        )

    robust_count = sum(1 for r in folds if r["robust"])
    robust_pct = robust_count / len(folds) * 100
    avg_oos_sharpe = sum(r["out_of_sample"].get("sharpe_ratio", 0) for r in folds) / len(folds)
    avg_oos_return = sum(r["out_of_sample"].get("net_return_pct", 0) for r in folds) / len(folds)

    print(f"\n{'='*80}")
    print(f"  Total folds    : {len(folds)}")
    print(f"  Robust folds   : {robust_count}/{len(folds)} ({robust_pct:.0f}%)")
    print(f"  Avg OOS Sharpe : {avg_oos_sharpe:.3f}")
    print(f"  Avg OOS Return : {avg_oos_return:.2f}%")

    verdict = "PASS" if robust_pct >= 60 and avg_oos_sharpe > 0 else "REVIEW"
    print(f"  Verdict        : {verdict}")
    print(f"{'='*80}")

    # Save summary
    summary = {
        "strategy": args.strategy,
        "symbol": args.symbol,
        "timeframe": args.timeframe,
        "total_folds": len(folds),
        "robust_folds": robust_count,
        "robust_pct": round(robust_pct, 1),
        "avg_oos_sharpe": round(avg_oos_sharpe, 3),
        "avg_oos_return_pct": round(avg_oos_return, 2),
        "verdict": verdict,
        "folds": [
            {
                "fold": r["fold"],
                "train_bars": r["train_bars"],
                "test_bars": r["test_bars"],
                "is_sharpe": round(r["in_sample"].get("sharpe_ratio", 0), 3),
                "oos_sharpe": round(r["out_of_sample"].get("sharpe_ratio", 0), 3),
                "oos_return_pct": round(r["out_of_sample"].get("net_return_pct", 0), 2),
                "oos_win_rate": round(r["out_of_sample"].get("win_rate", 0), 3),
                "oos_profit_factor": round(r["out_of_sample"].get("profit_factor", 0), 3),
                "degradation_pct": float(r["sharpe_degradation_pct"]),
                "robust": bool(r["robust"]),
            }
            for r in folds
        ],
    }
    summary_path = out_dir / "walk_forward_summary.json"
    summary_path.write_text(json.dumps(summary, indent=2))
    print(f"\nSaved to: {summary_path}")


if __name__ == "__main__":
    asyncio.run(main())
