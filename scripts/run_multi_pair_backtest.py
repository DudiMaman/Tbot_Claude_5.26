#!/usr/bin/env python3
"""
Multi-pair, multi-strategy backtest runner.
Runs all strategies across their configured symbol lists and produces
a comparative performance table.

Usage:
  python scripts/run_multi_pair_backtest.py --strategy mean_reversion
  python scripts/run_multi_pair_backtest.py --strategy breakout
  python scripts/run_multi_pair_backtest.py --strategy all
"""
from __future__ import annotations

import argparse
import asyncio
import sys
from pathlib import Path

import pandas as pd

sys.path.insert(0, str(Path(__file__).parent.parent))

from dotenv import load_dotenv
from bot.core.config import load_broker_config, load_risk_config, load_strategy_config, StrategyConfig
from bot.backtesting.engine import BacktestEngine
from bot.strategies.ema_crossover import EMACrossoverStrategy
from bot.strategies.mean_reversion import MeanReversionStrategy
from bot.strategies.breakout import BreakoutStrategy
from bot.strategies.momentum_sniper import MomentumSniperStrategy
from bot.reporting.logger import configure_logging

DATA_DIR = Path("data/real_synthetic")

_STRATEGY_MAP = {
    "ema_crossover": (EMACrossoverStrategy, "1h", "2y"),
    "mean_reversion": (MeanReversionStrategy, "1h", "2y"),
    "breakout": (BreakoutStrategy, "4h", "2y"),
    "momentum_sniper": (MomentumSniperStrategy, "15m", "6m"),
}


def load_bars_for_symbol(symbol: str, primary_tf: str, period: str) -> dict[str, pd.DataFrame] | None:
    """Load primary + daily timeframe data for a symbol."""
    primary_file = DATA_DIR / f"{symbol}_{primary_tf}_{period}.parquet"

    # For 4h: resample from 1h data
    if primary_tf == "4h":
        source_file = DATA_DIR / f"{symbol}_1h_2y.parquet"
        if not source_file.exists():
            print(f"  Missing 1h source for {symbol}, skipping")
            return None
        df_1h = pd.read_parquet(source_file)
        if df_1h.index.tz is None:
            df_1h.index = df_1h.index.tz_localize("UTC")
        df_primary = df_1h.resample("4h").agg(
            {"open": "first", "high": "max", "low": "min", "close": "last", "volume": "sum"}
        ).dropna()
        df_daily = df_1h.resample("1D").agg(
            {"open": "first", "high": "max", "low": "min", "close": "last", "volume": "sum"}
        ).dropna()
        return {"4h": df_primary, "1D": df_daily}

    if not primary_file.exists():
        print(f"  Missing data for {symbol} {primary_tf} {period}, skipping")
        return None

    df_primary = pd.read_parquet(primary_file)
    if df_primary.index.tz is None:
        df_primary.index = df_primary.index.tz_localize("UTC")

    bars = {primary_tf: df_primary}

    # Daily trend filter
    daily_file = DATA_DIR / f"{symbol}_1d_2y.parquet"
    if not daily_file.exists():
        daily_file = DATA_DIR / f"{symbol}_1h_2y.parquet"
        if daily_file.exists():
            df_1h = pd.read_parquet(daily_file)
            if df_1h.index.tz is None:
                df_1h.index = df_1h.index.tz_localize("UTC")
            df_daily = df_1h.resample("1D").agg(
                {"open": "first", "high": "max", "low": "min", "close": "last", "volume": "sum"}
            ).dropna()
            bars["1D"] = df_daily
    else:
        df_daily = pd.read_parquet(daily_file)
        if df_daily.index.tz is None:
            df_daily.index = df_daily.index.tz_localize("UTC")
        bars["1D"] = df_daily

    return bars


async def run_strategy_on_symbol(
    strategy_name: str,
    symbol: str,
    config_dir: str = "config",
    output_dir: str | None = None,
    enable_brain: bool = True,
) -> dict | None:
    strategy_cls, primary_tf, period = _STRATEGY_MAP[strategy_name]

    bars = load_bars_for_symbol(symbol, primary_tf, period)
    if bars is None:
        return None

    primary_df = bars[primary_tf]
    bnh_return = (primary_df["close"].iloc[-1] / primary_df["close"].iloc[0] - 1) * 100

    risk_cfg = load_risk_config(config_dir)
    broker_cfg = load_broker_config("binance", config_dir)
    strategy_cfg = load_strategy_config(strategy_name, config_dir)

    # Override symbols to single symbol
    cfg_data = strategy_cfg.model_dump()
    cfg_data["symbols"] = [symbol]
    strategy_cfg = StrategyConfig(**cfg_data)

    strategy = strategy_cls(strategy_cfg)

    out_dir = output_dir or f"reports/{strategy_name}/{symbol}"
    engine = BacktestEngine(
        risk_config=risk_cfg,
        broker_config=broker_cfg,
        strategies=[strategy],
        output_dir=out_dir,
        enable_brain=enable_brain,
        brain_interval_bars=50,
    )

    try:
        metrics = await engine.run(bars, primary_tf=primary_tf)
        metrics["bnh_pct"] = round(bnh_return, 1)
        metrics["symbol"] = symbol
        metrics["strategy"] = strategy_name
        metrics["primary_tf"] = primary_tf
        metrics["n_bars"] = len(primary_df)
        return metrics
    except Exception as e:
        print(f"  ERROR {symbol}: {e}")
        return None


async def run_all_for_strategy(strategy_name: str, config_dir: str = "config") -> list[dict]:
    strategy_cfg = load_strategy_config(strategy_name, config_dir)
    symbols = strategy_cfg.symbols

    print(f"\n{'='*70}")
    print(f"Running {strategy_name.upper()} on {len(symbols)} pairs")
    print(f"{'='*70}")

    results = []
    for sym in symbols:
        print(f"  {sym}...", end=" ", flush=True)
        result = await run_strategy_on_symbol(strategy_name, sym, config_dir)
        if result:
            bot_pct = result.get("net_return_pct", 0)
            trades = result.get("total_trades", 0)
            wr = result.get("win_rate", 0) * 100
            bnh = result.get("bnh_pct", 0)
            print(f"Bot: {bot_pct:+.1f}%  B&H: {bnh:+.1f}%  Trades: {trades}  WR: {wr:.0f}%")
            results.append(result)
        else:
            print("SKIPPED")

    return results


def print_summary_table(results: list[dict], strategy_name: str, initial_cash: float = 5000.0) -> None:
    if not results:
        print("No results to display.")
        return

    print(f"\n{'='*90}")
    print(f"  {strategy_name.upper()} — Multi-Pair Summary")
    print(f"{'='*90}")
    print(f"  {'Symbol':<12} {'B&H%':>8} {'Bot%':>8} {'Trades':>7} {'WR%':>6} "
          f"{'AvgWin':>9} {'AvgLoss':>9} {'PF':>6}")
    print(f"  {'-'*12} {'-'*8} {'-'*8} {'-'*7} {'-'*6} {'-'*9} {'-'*9} {'-'*6}")

    total_pnl = 0.0
    total_trades = 0
    total_wins = 0

    for r in sorted(results, key=lambda x: x.get("net_return_pct", 0), reverse=True):
        sym = r["symbol"]
        bnh = r.get("bnh_pct", 0)
        bot = r.get("net_return_pct", 0)
        trades = r.get("total_trades", 0)
        wr = r.get("win_rate", 0) * 100
        avg_win = r.get("avg_win", 0)
        avg_loss = r.get("avg_loss", 0)
        pf = r.get("profit_factor", 0)

        pnl = initial_cash * bot / 100
        total_pnl += pnl
        total_trades += trades
        total_wins += int(trades * wr / 100)

        pf_str = f"{pf:.2f}" if pf < 99 else ">99"
        print(f"  {sym:<12} {bnh:>+8.1f}% {bot:>+8.1f}% {trades:>7} {wr:>5.0f}% "
              f"${avg_win:>8.0f} ${avg_loss:>8.0f} {pf_str:>6}")

    avg_bot = sum(r.get("net_return_pct", 0) for r in results) / len(results)
    overall_wr = (total_wins / total_trades * 100) if total_trades > 0 else 0

    print(f"  {'-'*90}")
    print(f"  {'AVERAGE':<12} {'':>8} {avg_bot:>+8.1f}% {total_trades:>7} {overall_wr:>5.0f}%")
    print(f"\n  Total closed P&L: ${total_pnl:+,.0f}  |  Total trades: {total_trades}")

    # Monthly breakdown
    period_months = {"2y": 24, "6m": 6}
    _, _, period = _STRATEGY_MAP.get(results[0].get("strategy", ""), (None, None, "24"))
    months = period_months.get(period, 12)
    monthly_avg = avg_bot / months if months else 0
    print(f"  Avg return/pair: {avg_bot:+.1f}% over {months}mo = {monthly_avg:+.2f}%/month")
    print(f"{'='*90}")


async def main() -> None:
    load_dotenv()
    configure_logging()  # suppress noise during batch run

    parser = argparse.ArgumentParser()
    parser.add_argument("--strategy", default="all",
                        choices=["all", "ema_crossover", "mean_reversion", "breakout", "momentum_sniper"])
    parser.add_argument("--config-dir", default="config")
    parser.add_argument("--no-brain", action="store_true")
    args = parser.parse_args()

    strategies = (
        list(_STRATEGY_MAP.keys())
        if args.strategy == "all"
        else [args.strategy]
    )

    all_results: dict[str, list[dict]] = {}
    for strat in strategies:
        results = await run_all_for_strategy(strat, args.config_dir)
        all_results[strat] = results
        if results:
            print_summary_table(results, strat)

    if len(strategies) > 1:
        print("\n" + "="*70)
        print("  STRATEGY COMPARISON OVERVIEW")
        print("="*70)
        print(f"  {'Strategy':<20} {'Pairs':>6} {'AvgBot%':>9} {'Mo%':>7} {'Trades':>8}")
        print(f"  {'-'*20} {'-'*6} {'-'*9} {'-'*7} {'-'*8}")
        for strat, results in all_results.items():
            if not results:
                continue
            _, _, period = _STRATEGY_MAP[strat]
            months = {"2y": 24, "6m": 6}.get(period, 12)
            avg_bot = sum(r.get("net_return_pct", 0) for r in results) / len(results)
            total_trades = sum(r.get("total_trades", 0) for r in results)
            monthly = avg_bot / months
            print(f"  {strat:<20} {len(results):>6} {avg_bot:>+9.1f}% {monthly:>+7.2f}% {total_trades:>8}")
        print("="*70)


if __name__ == "__main__":
    asyncio.run(main())
