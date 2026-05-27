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
import signal
import sys
from pathlib import Path

from dotenv import load_dotenv

from bot.core.config import load_broker_config, load_risk_config, load_strategy_config
from bot.core.engine import TradingEngine
from bot.core.modes import ExecutionMode
from bot.data.historical import HistoricalLoader
from bot.execution.binance import BinanceBroker
from bot.execution.paper import PaperBroker
from bot.reporting.logger import configure_logging
from bot.data.feed_synthetic_live import SyntheticLiveFeed
from bot.strategies.ema_crossover import EMACrossoverStrategy
from bot.strategies.mean_reversion import MeanReversionStrategy
from bot.strategies.breakout import BreakoutStrategy
from bot.strategies.momentum_sniper import MomentumSniperStrategy


_WARMUP_LOOKBACK_DAYS = {
    "1m": 1, "5m": 2, "15m": 3,
    "1h": 7, "4h": 30, "1D": 200,
}


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
        choices=["ema_crossover", "mean_reversion", "breakout", "momentum_sniper"],
    )
    parser.add_argument(
        "--synthetic-feed", action="store_true",
        help="Use synthetic GBM price feed instead of Binance WebSocket (for testing/demo)",
    )
    parser.add_argument("--log-level", default=os.environ.get("LOG_LEVEL", "INFO"))
    parser.add_argument("--prometheus-port", type=int, default=8000)
    parser.add_argument("--status-interval", type=int, default=300,
                        help="Seconds between equity/position status log lines (default: 300)")
    return parser.parse_args()


def build_strategies(names: list[str], config_dir: str) -> list:
    strategy_map = {
        "ema_crossover": EMACrossoverStrategy,
        "mean_reversion": MeanReversionStrategy,
        "breakout": BreakoutStrategy,
        "momentum_sniper": MomentumSniperStrategy,
    }
    strategies = []
    for name in names:
        cfg = load_strategy_config(name, config_dir)
        cls = strategy_map[name]
        strategies.append(cls(cfg))
    return strategies


def _load_warmup_data(strategies: list, data_dir: str = "data/real_synthetic") -> dict:
    """Load most-recent historical Parquet files for each strategy symbol/timeframe.
    Used to pre-warm indicator buffers so strategies trade from bar 1 of live feed.
    Returns {symbol → {timeframe → DataFrame}} or empty dict if no data found.
    """
    import pandas as pd
    from pathlib import Path

    warmup: dict[str, dict[str, pd.DataFrame]] = {}
    data_path = Path(data_dir)
    if not data_path.exists():
        return warmup

    for strategy in strategies:
        for symbol in strategy.config.symbols:
            for tf in strategy.config.timeframes.values():
                if tf in warmup.get(symbol, {}):
                    continue  # already loaded
                # Try both original case and lowercase (1D vs 1d)
                for tf_variant in {tf, tf.lower()}:
                    candidates = sorted(
                        data_path.glob(f"{symbol}_{tf_variant}_*.parquet"), reverse=True
                    )
                    if candidates:
                        try:
                            df = pd.read_parquet(candidates[0])
                            warmup.setdefault(symbol, {})[tf] = df
                        except Exception:
                            pass
                        break
    return warmup


async def _fetch_warmup_from_rest(strategies: list, already_loaded: dict) -> dict:
    """For each strategy symbol/timeframe NOT already in `already_loaded`, fetch
    recent OHLCV history from Binance REST so the regime classifier (needs 105+ bars)
    and strategy indicators are ready immediately on first live bar.
    Returns dict in same {symbol → {timeframe → DataFrame}} shape with fetched entries.
    """
    from datetime import date, timedelta

    fetched: dict = {}
    loader = HistoricalLoader()
    today = date.today()
    end = today + timedelta(days=1)  # ccxt end is exclusive

    for strategy in strategies:
        for symbol in strategy.config.symbols:
            for tf in strategy.config.timeframes.values():
                if tf in already_loaded.get(symbol, {}) or tf in fetched.get(symbol, {}):
                    continue
                lookback = _WARMUP_LOOKBACK_DAYS.get(tf, 7)
                start = today - timedelta(days=lookback)
                try:
                    df = await loader.fetch_crypto(symbol, tf, start, end)
                    if not df.empty:
                        fetched.setdefault(symbol, {})[tf] = df
                        print(f"  Fetched {len(df)} {tf} bars for {symbol}")
                except Exception as e:
                    print(f"  Failed to fetch {symbol} {tf} from REST: {e}")
    return fetched


async def run_paper_or_live(args: argparse.Namespace) -> None:
    risk_cfg = load_risk_config(args.config_dir)
    broker_cfg = load_broker_config("binance", args.config_dir)
    mode = ExecutionMode(args.mode)
    strategies = build_strategies(args.strategies, args.config_dir)

    if mode == ExecutionMode.LIVE:
        broker = BinanceBroker(broker_cfg)
    else:
        broker = PaperBroker(broker_cfg, initial_cash=risk_cfg.capital_usd)

    data_feed = SyntheticLiveFeed(bar_seconds=5) if args.synthetic_feed else None

    # Pre-warm indicators from cached Parquet data so strategies are ready immediately
    warmup_data = _load_warmup_data(strategies)
    if warmup_data:
        warmed = {sym: list(tfs.keys()) for sym, tfs in warmup_data.items()}
        print(f"Pre-warming from Parquet cache: {warmed}")

    # For any symbol/timeframe still missing, fetch from Binance REST so the brain
    # regime classifier (needs 105 bars) and strategy indicators don't have to wait
    # 26+ hours of live WS data to warm up.
    if not args.synthetic_feed:
        print("Fetching missing warmup bars from Binance REST...")
        rest_data = await _fetch_warmup_from_rest(strategies, warmup_data)
        for sym, tfs in rest_data.items():
            warmup_data.setdefault(sym, {}).update(tfs)

    engine = TradingEngine(
        risk_config=risk_cfg,
        broker_config=broker_cfg,
        broker=broker,
        strategies=strategies,
        execution_mode=mode,
        prometheus_port=args.prometheus_port,
        status_interval_seconds=args.status_interval,
        data_feed=data_feed,
        warmup_data=warmup_data or None,
    )

    await engine.run()


def main() -> None:
    load_dotenv()
    args = parse_args()
    configure_logging(log_level=args.log_level)

    if args.mode == "backtest":
        print("For backtesting, use: python scripts/run_backtest.py --help")
        sys.exit(0)

    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    main_task: asyncio.Task = loop.create_task(run_paper_or_live(args))

    def _request_stop(signum, frame):  # noqa: ARG001
        print(f"\nShutdown signal {signum} received — stopping gracefully...")
        main_task.cancel()

    for sig in (signal.SIGTERM, signal.SIGINT):
        loop.add_signal_handler(sig, lambda s=sig, f=None: _request_stop(s, f))

    try:
        loop.run_until_complete(main_task)
    except asyncio.CancelledError:
        pass
    finally:
        loop.close()


if __name__ == "__main__":
    main()
