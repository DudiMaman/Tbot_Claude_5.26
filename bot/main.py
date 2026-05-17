"""
Entry point — loads config, builds all components, starts the engine.
Usage:
  python -m bot.main                    # paper trading mode
  python -m bot.main --mode backtest    # backtesting (requires --symbol and --from/--to)
  python -m bot.main --mode live        # live trading
"""
from __future__ import annotations

import argparse
import asyncio
import os
import sys
from pathlib import Path

from dotenv import load_dotenv

from bot.core.config import load_broker_config, load_risk_config, load_strategy_config
from bot.core.engine import TradingEngine
from bot.core.modes import ExecutionMode
from bot.execution.binance import BinanceBroker
from bot.execution.paper import PaperBroker
from bot.reporting.logger import configure_logging
from bot.strategies.ema_crossover import EMACrossoverStrategy
from bot.strategies.mean_reversion import MeanReversionStrategy
from bot.strategies.breakout import BreakoutStrategy


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Automated Trading Bot")
    parser.add_argument(
        "--mode", default=os.environ.get("EXECUTION_MODE", "paper"),
        choices=["backtest", "paper", "live"],
    )
    parser.add_argument("--config-dir", default="config")
    parser.add_argument(
        "--strategies", nargs="+",
        default=["ema_crossover"],
        choices=["ema_crossover", "mean_reversion", "breakout"],
    )
    parser.add_argument("--log-level", default=os.environ.get("LOG_LEVEL", "INFO"))
    parser.add_argument("--prometheus-port", type=int, default=8000)
    return parser.parse_args()


def build_strategies(names: list[str], config_dir: str) -> list:
    strategy_map = {
        "ema_crossover": EMACrossoverStrategy,
        "mean_reversion": MeanReversionStrategy,
        "breakout": BreakoutStrategy,
    }
    strategies = []
    for name in names:
        cfg = load_strategy_config(name, config_dir)
        cls = strategy_map[name]
        strategies.append(cls(cfg))
    return strategies


async def run_paper_or_live(args: argparse.Namespace) -> None:
    risk_cfg = load_risk_config(args.config_dir)
    broker_cfg = load_broker_config("binance", args.config_dir)
    mode = ExecutionMode(args.mode)
    strategies = build_strategies(args.strategies, args.config_dir)

    if mode == ExecutionMode.LIVE:
        broker = BinanceBroker(broker_cfg)
    else:
        broker = PaperBroker(broker_cfg, initial_cash=risk_cfg.capital_usd)

    engine = TradingEngine(
        risk_config=risk_cfg,
        broker_config=broker_cfg,
        broker=broker,
        strategies=strategies,
        execution_mode=mode,
        prometheus_port=args.prometheus_port,
    )

    await engine.run()


def main() -> None:
    load_dotenv()
    args = parse_args()
    configure_logging(log_level=args.log_level)

    if args.mode == "backtest":
        # Backtesting is launched via scripts/run_backtest.py
        print("For backtesting, use: python scripts/run_backtest.py --help")
        sys.exit(0)

    asyncio.run(run_paper_or_live(args))


if __name__ == "__main__":
    main()
