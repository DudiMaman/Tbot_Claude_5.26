"""
Phase 3 — Binance Testnet paper trading launcher.

Market data: live from wss://testnet.binance.vision/ws (real order book, simulated fills)
Execution:   PaperBroker (slippage + fees, no real API keys needed)
Risk:        Full 11-point gate — R:R, circuit breakers, position sizing

Usage:
  python scripts/run_paper.py
  python scripts/run_paper.py --strategies ema_crossover mean_reversion breakout
  python scripts/run_paper.py --capital 10000 --status-interval 60
  python scripts/run_paper.py --symbols BTCUSDT ETHUSDT --strategies ema_crossover
"""
from __future__ import annotations

import argparse
import asyncio
import os
import signal
import sys
from datetime import datetime, timezone
from pathlib import Path

# Ensure project root is on the path when run directly
sys.path.insert(0, str(Path(__file__).parent.parent))

from dotenv import load_dotenv

from bot.core.config import load_broker_config, load_risk_config, load_strategy_config
from bot.core.engine import TradingEngine
from bot.core.modes import ExecutionMode
from bot.data.feed_synthetic_live import SyntheticLiveFeed
from bot.execution.paper import PaperBroker
from bot.reporting.logger import configure_logging
from bot.strategies.ema_crossover import EMACrossoverStrategy
from bot.strategies.mean_reversion import MeanReversionStrategy
from bot.strategies.breakout import BreakoutStrategy
from bot.strategies.momentum_sniper import MomentumSniperStrategy

STRATEGY_MAP = {
    "ema_crossover": EMACrossoverStrategy,
    "mean_reversion": MeanReversionStrategy,
    "breakout": BreakoutStrategy,
    "momentum_sniper": MomentumSniperStrategy,
}

_BANNER = """
╔══════════════════════════════════════════════════════════════╗
║   PHASE 3 — BINANCE TESTNET PAPER TRADING  (+  THE BRAIN)   ║
║   Market data : Synthetic live feed (GBM)                   ║
║   Execution   : PaperBroker (simulated fills, no real $$)   ║
║   Brain       : Regime detection + per-strategy adaptation  ║
║   Press Ctrl+C to stop and print final stats                ║
╚══════════════════════════════════════════════════════════════╝
"""


def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(description="Phase 3 paper trading on Binance Testnet")
    p.add_argument(
        "--strategies", nargs="+",
        default=["ema_crossover"],
        choices=list(STRATEGY_MAP),
        help="Strategies to run (default: ema_crossover)",
    )
    p.add_argument(
        "--capital", type=float, default=None,
        help="Starting capital in USD (overrides config/base.yaml)",
    )
    p.add_argument(
        "--config-dir", default="config",
        help="Config directory (default: config)",
    )
    p.add_argument(
        "--log-level", default=os.environ.get("LOG_LEVEL", "INFO"),
        choices=["DEBUG", "INFO", "WARNING", "ERROR"],
    )
    p.add_argument(
        "--status-interval", type=int, default=60,
        help="Seconds between equity/position log lines (default: 60)",
    )
    p.add_argument(
        "--prometheus-port", type=int, default=8001,
        help="Prometheus metrics port (default: 8001)",
    )
    p.add_argument(
        "--bar-seconds", type=float, default=5.0,
        help="Real seconds per synthetic bar (default: 5). "
             "Lower = faster paper trading. 3600 = real-time 1h bars.",
    )
    p.add_argument(
        "--no-brain", action="store_true",
        help="Disable the Brain meta-controller (run strategies without adaptation)",
    )
    p.add_argument(
        "--brain-interval", type=int, default=50,
        help="Number of bars between Brain assessment cycles (default: 50)",
    )
    return p.parse_args()


def _print_final_stats(portfolio, start_time: datetime, brain=None) -> None:
    elapsed = (datetime.now(timezone.utc) - start_time).total_seconds()
    equity = portfolio.equity()
    pnl = portfolio.daily_net_pnl()
    closed = portfolio.tracker.closed_trades
    n_closed = len(closed)
    win_rate = portfolio.tracker.win_rate()
    print("\n" + "=" * 60)
    print("PAPER TRADING SESSION COMPLETE")
    print(f"  Runtime        : {elapsed/60:.1f} minutes")
    print(f"  Final equity   : ${equity:,.2f}")
    print(f"  Session P&L    : ${pnl:+,.2f}")
    print(f"  Trades closed  : {n_closed}")
    if n_closed > 0:
        print(f"  Win rate       : {win_rate:.1%}")
    print(f"  Open positions : {portfolio.open_position_count()}")
    if brain is not None:
        summary = brain.get_summary()
        print()
        print("BRAIN SUMMARY")
        print(f"  Market regime  : {summary['regime']}")
        print(f"  Decisions made : {summary['decisions']['total_decisions']}")
        if summary["decisions"]["action_counts"]:
            for action, count in summary["decisions"]["action_counts"].items():
                print(f"    {action:<28} {count}")
        if summary["metrics"]:
            print()
            print("  Strategy performance (rolling window):")
            for sid, m in summary["metrics"].items():
                status = "ON " if summary["enabled_strategies"].get(sid) else "OFF"
                mode = summary["risk_modes"].get(sid, "normal")
                print(f"    [{status}] [{mode:>9}] {sid}: "
                      f"WR={m['win_rate']:.0%}  PF={m['profit_factor']:.2f}  "
                      f"Sharpe={m['rolling_sharpe']:+.2f}  "
                      f"NetPnL=${m['total_net_pnl']:+.2f}")
    print("=" * 60)


async def run(args: argparse.Namespace) -> None:
    load_dotenv()
    # Force testnet + paper mode
    os.environ.setdefault("BINANCE_TESTNET", "true")
    os.environ["EXECUTION_MODE"] = "paper"

    risk_cfg = load_risk_config(args.config_dir)
    if args.capital is not None:
        risk_cfg = risk_cfg.model_copy(update={"capital_usd": args.capital})

    broker_cfg = load_broker_config("binance", args.config_dir)

    strategies = []
    for name in args.strategies:
        cfg = load_strategy_config(name, args.config_dir)
        strategies.append(STRATEGY_MAP[name](cfg))

    broker = PaperBroker(broker_cfg, initial_cash=risk_cfg.capital_usd)
    feed = SyntheticLiveFeed(bar_seconds=args.bar_seconds)

    engine = TradingEngine(
        risk_config=risk_cfg,
        broker_config=broker_cfg,
        broker=broker,
        strategies=strategies,
        execution_mode=ExecutionMode.PAPER,
        prometheus_port=args.prometheus_port,
        status_interval_seconds=args.status_interval,
        data_feed=feed,
        enable_brain=not args.no_brain,
        brain_interval_bars=args.brain_interval,
    )

    start_time = datetime.now(timezone.utc)
    print(_BANNER)
    print(f"  Started        : {start_time.strftime('%Y-%m-%d %H:%M:%S UTC')}")
    print(f"  Capital        : ${risk_cfg.capital_usd:,.2f}")
    print(f"  Strategies     : {', '.join(args.strategies)}")
    print(f"  Bar speed      : {args.bar_seconds}s / bar (synthetic live feed)")
    print(f"  Status every   : {args.status_interval}s")
    print(f"  Brain          : {'ENABLED (interval=' + str(args.brain_interval) + ' bars)' if not args.no_brain else 'DISABLED'}")
    print()

    try:
        await engine.run()
    except asyncio.CancelledError:
        pass
    finally:
        _print_final_stats(engine._portfolio, start_time, brain=engine._brain)


def main() -> None:
    args = parse_args()
    configure_logging(log_level=args.log_level)

    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    task = loop.create_task(run(args))

    def _stop(signum, frame):  # noqa: ARG001
        print(f"\nSignal {signum} — stopping...")
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
