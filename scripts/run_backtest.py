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


_STRATEGY_MAP = {
    "ema_crossover": EMACrossoverStrategy,
    "mean_reversion": MeanReversionStrategy,
    "breakout": BreakoutStrategy,
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

    # Also fetch daily data for trend filter if available
    bars_by_tf = {args.timeframe: df}
    if args.timeframe != "1D":
        try:
            if args.market == "crypto":
                daily_df = await loader.fetch_crypto(args.symbol, "1D", start, end)
            else:
                daily_df = await loader.fetch_stocks(args.symbol, "1D", start, end)
            if not daily_df.empty:
                bars_by_tf["1D"] = daily_df
        except Exception:
            pass

    engine = BacktestEngine(
        risk_config=risk_cfg,
        broker_config=broker_cfg,
        strategies=[strategy],
        output_dir=args.output_dir,
    )

    metrics = await engine.run(bars_by_tf, primary_tf=args.timeframe)

    print("\n" + "=" * 60)
    print(f"Backtest Results: {args.strategy} | {args.symbol} | {args.timeframe}")
    print("=" * 60)
    for k, v in metrics.items():
        print(f"  {k:<35} {v}")
    print(f"\nReports saved to: {args.output_dir}/")


if __name__ == "__main__":
    asyncio.run(main())
