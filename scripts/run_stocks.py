#!/usr/bin/env python3
"""
Phase 6 — Stock paper / live trading via Alpaca.

Paper mode (default): uses PaperBroker + StockFeed (Alpaca WebSocket / polling).
Live mode: uses AlpacaBroker + StockFeed with real Alpaca paper/live account.

Market hours: 09:30–16:00 ET.  The feed will pause outside market hours.
Strategies use daily timeframe to avoid PDT rule violations on <$25k accounts.

Usage:
  # Paper mode (simulated fills):
  python scripts/run_stocks.py --strategies ema_crossover

  # Live paper-account mode (real Alpaca paper account, no real $):
  python scripts/run_stocks.py --strategies ema_crossover --live-paper

  # Real Alpaca live account (CAUTION — real funds):
  python scripts/run_stocks.py --strategies ema_crossover --confirm-live
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
from bot.core.modes import ExecutionMode
from bot.data.feed_stocks import StockFeed
from bot.execution.alpaca import AlpacaBroker
from bot.execution.paper import PaperBroker
from bot.reporting.logger import configure_logging
from bot.strategies.ema_crossover import EMACrossoverStrategy
from bot.strategies.mean_reversion import MeanReversionStrategy
from bot.strategies.breakout import BreakoutStrategy

STRATEGY_MAP = {
    "ema_crossover": EMACrossoverStrategy,
    "mean_reversion": MeanReversionStrategy,
    "breakout": BreakoutStrategy,
}

# Stock-specific config variants (daily TF)
STOCKS_CONFIG_MAP = {
    "ema_crossover": "ema_crossover_stocks",
    "mean_reversion": "mean_reversion",     # reuses crypto config (RSI works on daily bars)
    "breakout": "breakout_stocks",
}

_BANNER = """
╔══════════════════════════════════════════════════════════════╗
║           PHASE 6 — ALPACA STOCK TRADING                    ║
║   Strategy TF : Daily (avoids PDT rule on <$25k accounts)  ║
║   Exposure cap: 40%% of equity in stocks                    ║
║   Brain       : Regime detection + per-strategy adaptation  ║
╚══════════════════════════════════════════════════════════════╝
"""


def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(description="Phase 6 — Alpaca stock trading")
    p.add_argument(
        "--strategies", nargs="+",
        default=["ema_crossover"],
        choices=list(STRATEGY_MAP),
    )
    p.add_argument(
        "--symbols", nargs="+", default=None,
        help="Override symbols (default: from strategy config)",
    )
    p.add_argument("--capital", type=float, default=None)
    p.add_argument("--config-dir", default="config")
    p.add_argument("--log-level", default="INFO", choices=["DEBUG", "INFO", "WARNING", "ERROR"])
    p.add_argument("--status-interval", type=int, default=300)
    p.add_argument("--prometheus-port", type=int, default=8002)
    p.add_argument("--no-brain", action="store_true")
    p.add_argument("--brain-interval", type=int, default=20,
                   help="Bars between Brain assessments; daily TF → lower default (20)")
    p.add_argument(
        "--live-paper", action="store_true",
        help="Use Alpaca paper account (real API calls, simulated fills, no real $)",
    )
    p.add_argument(
        "--confirm-live", action="store_true",
        help="Trade on Alpaca LIVE account (REAL FUNDS — use with extreme caution)",
    )
    return p.parse_args()


def _build_strategies(args: argparse.Namespace) -> list:
    strategies = []
    from bot.core.config import StrategyConfig
    for name in args.strategies:
        config_name = STOCKS_CONFIG_MAP.get(name, name)
        cfg = load_strategy_config(config_name, args.config_dir)
        if args.symbols:
            cfg_data = cfg.model_dump()
            cfg_data["symbols"] = args.symbols
            cfg = StrategyConfig(**cfg_data)
        strategies.append(STRATEGY_MAP[name](cfg))
    return strategies


def _build_broker(args: argparse.Namespace, broker_cfg, risk_cfg) -> tuple:
    api_key = os.environ.get("ALPACA_API_KEY", "")
    api_secret = os.environ.get("ALPACA_SECRET", "")

    if args.confirm_live:
        if not api_key or not api_secret:
            print("ERROR: ALPACA_API_KEY and ALPACA_SECRET must be set for live trading.")
            sys.exit(1)
        broker = AlpacaBroker(broker_cfg)
        mode = ExecutionMode.LIVE
        print("  Mode: LIVE Alpaca account (real funds)")
    elif args.live_paper:
        if not api_key or not api_secret:
            print("ERROR: ALPACA_API_KEY and ALPACA_SECRET must be set for live-paper mode.")
            sys.exit(1)
        os.environ.setdefault("ALPACA_BASE_URL", "https://paper-api.alpaca.markets")
        broker = AlpacaBroker(broker_cfg)
        mode = ExecutionMode.PAPER
        print("  Mode: Alpaca PAPER account (real API, simulated fills)")
    else:
        broker = PaperBroker(broker_cfg, initial_cash=risk_cfg.capital_usd)
        mode = ExecutionMode.PAPER
        print("  Mode: Local PaperBroker (fully simulated, no Alpaca API needed)")

    return broker, mode


async def run(args: argparse.Namespace) -> None:
    load_dotenv()

    risk_cfg = load_risk_config(args.config_dir)
    if args.capital is not None:
        risk_cfg = risk_cfg.model_copy(update={"capital_usd": args.capital})

    broker_cfg = load_broker_config("alpaca", args.config_dir)
    strategies = _build_strategies(args)
    broker, mode = _build_broker(args, broker_cfg, risk_cfg)

    api_key = os.environ.get("ALPACA_API_KEY", "")
    api_secret = os.environ.get("ALPACA_SECRET", "")
    feed = StockFeed(api_key=api_key, api_secret=api_secret, paper=not args.confirm_live)

    if isinstance(broker, PaperBroker):
        broker.register_fill_callback(None)  # will be wired by TradingEngine

    engine = TradingEngine(
        risk_config=risk_cfg,
        broker_config=broker_cfg,
        broker=broker,
        strategies=strategies,
        execution_mode=mode,
        prometheus_port=args.prometheus_port,
        status_interval_seconds=args.status_interval,
        data_feed=feed,
        enable_brain=not args.no_brain,
        brain_interval_bars=args.brain_interval,
        brain_state_path="reports/brain_state_stocks.json",
    )

    start_time = datetime.now(timezone.utc)
    print(_BANNER)
    print(f"  Started        : {start_time.strftime('%Y-%m-%d %H:%M:%S UTC')}")
    print(f"  Capital        : ${risk_cfg.capital_usd:,.2f}")
    print(f"  Strategies     : {', '.join(args.strategies)}")
    symbols = [s for strat in strategies for s in strat.config.symbols]
    print(f"  Symbols        : {', '.join(set(symbols))}")
    print(f"  Brain          : {'ENABLED (interval=' + str(args.brain_interval) + ' bars)' if not args.no_brain else 'DISABLED'}")
    print(f"  Prometheus     : http://localhost:{args.prometheus_port}/metrics")
    print()

    try:
        await engine.run()
    except asyncio.CancelledError:
        pass
    finally:
        elapsed = (datetime.now(timezone.utc) - start_time).total_seconds()
        equity = engine._portfolio.equity()
        pnl = engine._portfolio.daily_net_pnl()
        trades = len(engine._portfolio.tracker.closed_trades)
        print(f"\nRuntime: {elapsed/60:.1f}m  |  Final equity: ${equity:,.2f}  |  "
              f"Day P&L: ${pnl:+,.2f}  |  Trades: {trades}")
        if engine._brain:
            summary = engine._brain.get_summary()
            print(f"Brain: regime={summary['regime']}  "
                  f"decisions={summary['decisions']['total_decisions']}")


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
