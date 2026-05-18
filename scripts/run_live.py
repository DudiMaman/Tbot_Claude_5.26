#!/usr/bin/env python3
"""
Phase 5 — Live crypto trading on Binance mainnet.

SAFETY: This script trades with REAL funds on Binance mainnet.
        It will NOT start unless:
          - BINANCE_TESTNET=false is set in environment
          - --confirm-live flag is passed explicitly
          - Risk mode is forced to DEFENSIVE for first 30 days

Usage:
  python scripts/run_live.py --strategies ema_crossover --confirm-live
  python scripts/run_live.py --strategies ema_crossover mean_reversion --confirm-live
"""
from __future__ import annotations

import argparse
import asyncio
import os
import signal
import sys
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from dotenv import load_dotenv

from bot.core.config import load_broker_config, load_risk_config, load_strategy_config
from bot.core.engine import TradingEngine
from bot.core.modes import ExecutionMode, RiskMode
from bot.execution.binance import BinanceBroker
from bot.reporting.logger import configure_logging
from bot.strategies.ema_crossover import EMACrossoverStrategy
from bot.strategies.mean_reversion import MeanReversionStrategy
from bot.strategies.breakout import BreakoutStrategy

STRATEGY_MAP = {
    "ema_crossover": EMACrossoverStrategy,
    "mean_reversion": MeanReversionStrategy,
    "breakout": BreakoutStrategy,
}

_BANNER = """
╔══════════════════════════════════════════════════════════════╗
║          PHASE 5 — BINANCE MAINNET LIVE TRADING             ║
║   ⚠️  REAL FUNDS — LOSSES ARE REAL — PROCEED WITH CARE      ║
║   Risk mode   : DEFENSIVE (0.5x sizing)                     ║
║   Brain       : ENABLED (regime detection + adaptation)     ║
║   Kill switch : create ./KILL_SWITCH file to halt           ║
╚══════════════════════════════════════════════════════════════╝
"""


def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(description="Phase 5 — Binance mainnet live trading")
    p.add_argument(
        "--strategies", nargs="+",
        default=["ema_crossover"],
        choices=list(STRATEGY_MAP),
    )
    p.add_argument("--config-dir", default="config")
    p.add_argument("--log-level", default="INFO", choices=["DEBUG", "INFO", "WARNING", "ERROR"])
    p.add_argument("--status-interval", type=int, default=300,
                   help="Seconds between equity log lines (default: 300)")
    p.add_argument("--prometheus-port", type=int, default=8000)
    p.add_argument("--no-brain", action="store_true",
                   help="Disable the Brain meta-controller")
    p.add_argument("--brain-interval", type=int, default=50)
    p.add_argument(
        "--confirm-live", action="store_true",
        help="REQUIRED: explicitly confirm you are trading with real funds",
    )
    return p.parse_args()


def _safety_checks(args: argparse.Namespace) -> None:
    if not args.confirm_live:
        print("ERROR: --confirm-live flag required to trade with real funds.")
        print("       Pass --confirm-live only if you understand the risks.")
        sys.exit(1)

    testnet = os.environ.get("BINANCE_TESTNET", "true").lower()
    if testnet != "false":
        print("ERROR: BINANCE_TESTNET must be set to 'false' for live trading.")
        print("       Set BINANCE_TESTNET=false in your .env file.")
        sys.exit(1)

    api_key = os.environ.get("BINANCE_API_KEY", "")
    api_secret = os.environ.get("BINANCE_SECRET", "")
    if not api_key or not api_secret:
        print("ERROR: BINANCE_API_KEY and BINANCE_SECRET must be set in environment.")
        sys.exit(1)

    kill_file = Path("./KILL_SWITCH")
    if kill_file.exists():
        print("ERROR: KILL_SWITCH file exists. Remove it to allow trading.")
        sys.exit(1)


async def run(args: argparse.Namespace) -> None:
    load_dotenv()
    _safety_checks(args)

    risk_cfg = load_risk_config(args.config_dir)
    # Force DEFENSIVE mode for live trading — 0.5x position sizing
    risk_cfg = risk_cfg.model_copy(update={"risk_mode": "defensive"})

    broker_cfg = load_broker_config("binance", args.config_dir)

    strategies = []
    for name in args.strategies:
        cfg = load_strategy_config(name, args.config_dir)
        strategies.append(STRATEGY_MAP[name](cfg))

    broker = BinanceBroker(broker_cfg)

    engine = TradingEngine(
        risk_config=risk_cfg,
        broker_config=broker_cfg,
        broker=broker,
        strategies=strategies,
        execution_mode=ExecutionMode.LIVE,
        prometheus_port=args.prometheus_port,
        status_interval_seconds=args.status_interval,
        enable_brain=not args.no_brain,
        brain_interval_bars=args.brain_interval,
        brain_state_path="reports/brain_state_live.json",
    )

    start_time = datetime.now(timezone.utc)
    print(_BANNER)
    print(f"  Started        : {start_time.strftime('%Y-%m-%d %H:%M:%S UTC')}")
    print(f"  Capital        : ${risk_cfg.capital_usd:,.2f}")
    print(f"  Strategies     : {', '.join(args.strategies)}")
    print(f"  Risk mode      : DEFENSIVE (0.5x sizing)")
    print(f"  Brain          : {'ENABLED' if not args.no_brain else 'DISABLED'}")
    print(f"  Prometheus     : http://localhost:{args.prometheus_port}/metrics")
    print()
    print("  CTRL+C to stop gracefully.")
    print()

    try:
        await engine.run()
    except asyncio.CancelledError:
        pass
    finally:
        equity = engine._portfolio.equity()
        pnl = engine._portfolio.daily_net_pnl()
        trades = len(engine._portfolio.tracker.closed_trades)
        print(f"\nFinal equity: ${equity:,.2f}  |  Day P&L: ${pnl:+,.2f}  |  Trades: {trades}")
        if engine._brain:
            summary = engine._brain.get_summary()
            print(f"Brain regime: {summary['regime']}  |  "
                  f"Decisions: {summary['decisions']['total_decisions']}")


def main() -> None:
    args = parse_args()
    configure_logging(log_level=args.log_level)

    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    task = loop.create_task(run(args))

    def _stop(signum, frame):  # noqa: ARG001
        print(f"\nSignal {signum} — stopping gracefully...")
        task.cancel()

    for sig in (signal.SIGTERM, signal.SIGINT):
        loop.add_signal_handler(sig, lambda s=sig, f=None: _stop(s, f))

    try:
        loop.run_until_complete(task)
    except asyncio.CancelledError:
        pass
    finally:
        loop.close()


if __name__ == "__main__":
    main()
