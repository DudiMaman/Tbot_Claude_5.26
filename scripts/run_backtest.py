#!/usr/bin/env python3
"""
CLI: run a named strategy backtest and emit report.
Usage:
  python scripts/run_backtest.py --strategy ema_crossover --symbol BTCUSDT \
      --from 2023-01-01 --to 2023-12-31 --timeframe 1h
"""
from __future__ import annotations

import argparse
import asyncio
import sys
from datetime import date
from pathlib import Path

# Allow running from project root
sys.path.insert(0, str(Path(__file__).parent.parent))

from dotenv import load_dotenv

from bot.core.config import load_broker_config, load_risk_config, load_strategy_config
from bot.backtesting.engine import BacktestEngine
from bot.data.historical import HistoricalLoader
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
    parser = argparse.ArgumentParser(description="Trading Bot Backtester")
    parser.add_argument("--strategy", required=True, choices=list(_STRATEGY_MAP.keys()))
    parser.add_argument("--symbol", default="BTCUSDT")
    parser.add_argument("--from", dest="date_from", required=True)
    parser.add_argument("--to", dest="date_to", required=True)
    parser.add_argument("--timeframe", default="1h")
    parser.add_argument("--output-dir", default="reports")
    parser.add_argument("--config-dir", default="config")
    parser.add_argument("--market", default="crypto", choices=["crypto", "stocks"])
    parser.add_argument("--data-file", default=None,
                        help="Path to a pre-generated parquet file (skips network fetch)")
    parser.add_argument("--no-brain", action="store_true",
                        help="Disable the Brain meta-controller")
    parser.add_argument("--brain-interval", type=int, default=50,
                        help="Bars between Brain assessment cycles (default: 50)")
    return parser.parse_args()


async def main() -> None:
    load_dotenv()
    args = parse_args()
    configure_logging()

    start = date.fromisoformat(args.date_from)
    end = date.fromisoformat(args.date_to)

    risk_cfg = load_risk_config(args.config_dir)
    broker_name = "binance" if args.market == "crypto" else "alpaca"
    broker_cfg = load_broker_config(broker_name, args.config_dir)
    strategy_cfg = load_strategy_config(args.strategy, args.config_dir)

    # Override symbols to the one specified
    strategy_cfg_data = strategy_cfg.model_dump()
    strategy_cfg_data["symbols"] = [args.symbol]
    from bot.core.config import StrategyConfig
    strategy_cfg = StrategyConfig(**strategy_cfg_data)

    strategy_cls = _STRATEGY_MAP[args.strategy]
    strategy = strategy_cls(strategy_cfg)

    if args.data_file:
        import pandas as pd
        print(f"Loading data from {args.data_file}...")
        df = pd.read_parquet(args.data_file)
        if df.index.tz is None:
            df.index = df.index.tz_localize("UTC")

        # Auto-resample if the file's actual resolution differs from the requested timeframe.
        # Infer actual resolution from median bar gap.
        _RESAMPLE_RULE = {
            "1m": "1min", "5m": "5min", "15m": "15min", "30m": "30min",
            "1h": "1h", "4h": "4h", "1D": "1D",
        }
        _TF_HOURS = {
            "1m": 1/60, "5m": 5/60, "15m": 0.25, "30m": 0.5,
            "1h": 1, "4h": 4, "1D": 24,
        }
        if len(df) >= 2:
            median_gap_h = (df.index[1:] - df.index[:-1]).median().total_seconds() / 3600
            target_h = _TF_HOURS.get(args.timeframe, 1.0)
            if abs(target_h - median_gap_h) > 0.1 * target_h:
                rule = _RESAMPLE_RULE.get(args.timeframe, args.timeframe)
                df = df.resample(rule).agg(
                    {"open": "first", "high": "max", "low": "min",
                     "close": "last", "volume": "sum"}
                ).dropna()
                print(f"Resampled to {args.timeframe}: {len(df)} bars")
    else:
        loader = HistoricalLoader()
        print(f"Fetching {args.symbol} {args.timeframe} data {start} → {end}...")
        if args.market == "crypto":
            df = await loader.fetch_crypto(args.symbol, args.timeframe, start, end)
        else:
            df = await loader.fetch_stocks(args.symbol, args.timeframe, start, end)

    if df.empty:
        print("No data fetched. Check symbol/timeframe/dates.")
        sys.exit(1)

    print(f"Loaded {len(df)} bars. Running backtest...")

    # Also fetch/derive daily data for trend filter
    bars_by_tf = {args.timeframe: df}
    if args.timeframe != "1D":
        if args.data_file:
            # Resample intraday data to daily for the trend filter
            import pandas as pd
            daily_df = df.resample("1D").agg(
                {"open": "first", "high": "max", "low": "min", "close": "last", "volume": "sum"}
            ).dropna()
            if not daily_df.empty:
                bars_by_tf["1D"] = daily_df
        else:
            try:
                loader2 = HistoricalLoader()
                if args.market == "crypto":
                    daily_df = await loader2.fetch_crypto(args.symbol, "1D", start, end)
                else:
                    daily_df = await loader2.fetch_stocks(args.symbol, "1D", start, end)
                if not daily_df.empty:
                    bars_by_tf["1D"] = daily_df
            except Exception:
                pass

    engine = BacktestEngine(
        risk_config=risk_cfg,
        broker_config=broker_cfg,
        strategies=[strategy],
        output_dir=args.output_dir,
        enable_brain=not args.no_brain,
        brain_interval_bars=args.brain_interval,
    )

    metrics = await engine.run(bars_by_tf, primary_tf=args.timeframe)

    print("\n" + "=" * 60)
    print(f"Backtest Results: {args.strategy} | {args.symbol} | {args.timeframe}")
    print("=" * 60)
    for k, v in metrics.items():
        print(f"  {k:<35} {v}")

    if engine._brain is not None:
        summary = engine._brain.get_summary()
        print()
        print(f"Brain: regime={summary['regime']}  decisions={summary['decisions']['total_decisions']}")
        if summary["decisions"]["action_counts"]:
            print("  Actions:", dict(summary["decisions"]["action_counts"]))

    print(f"\nReports saved to: {args.output_dir}/")


if __name__ == "__main__":
    asyncio.run(main())
