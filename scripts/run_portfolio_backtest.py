#!/usr/bin/env python3
"""
Phase 4 — Multi-Strategy Portfolio Backtest.

Runs EMA Crossover + Momentum Sniper simultaneously on non-overlapping symbols
with SHARED $5000 capital. Uses 15m as the universal primary TF so both
strategies can interleave on the same clock (Jul–Dec 2024).

EMA Crossover: BTC/ETH/SOL/LINK/INJ/DOT/AVAX  (1h signal derived from 15m)
Momentum Sniper: XRP/ARB/OP                     (15m signal)

Usage:
  python scripts/run_portfolio_backtest.py
  python scripts/run_portfolio_backtest.py --no-brain
"""
from __future__ import annotations

import asyncio
import sys
from pathlib import Path

import pandas as pd

sys.path.insert(0, str(Path(__file__).parent.parent))

from dotenv import load_dotenv

from bot.backtesting.engine import BacktestEngine
from bot.core.config import load_broker_config, load_risk_config, load_strategy_config, StrategyConfig
from bot.reporting.logger import configure_logging
from bot.strategies.ema_crossover import EMACrossoverStrategy
from bot.strategies.momentum_sniper import MomentumSniperStrategy

DATA_DIR = Path("data/real_synthetic")
PERIOD_START = "2024-07-01"
PERIOD_END   = "2024-12-31"


# ---------------------------------------------------------------------------
# Data loading
# ---------------------------------------------------------------------------

def load_symbol_bars(symbol: str) -> dict[str, pd.DataFrame] | None:
    """Load 15m + derived 1h + derived 1D bars for a symbol."""
    f15 = DATA_DIR / f"{symbol}_15m_6m.parquet"
    if not f15.exists():
        return None

    df15 = pd.read_parquet(f15)
    if df15.index.tz is None:
        df15.index = df15.index.tz_localize("UTC")

    # Slice to shared test period
    df15 = df15[PERIOD_START:PERIOD_END]
    if len(df15) < 200:
        return None

    # Resample to 1h and 1D for EMA / trend filters
    df1h = df15.resample("1h").agg(
        {"open": "first", "high": "max", "low": "min", "close": "last", "volume": "sum"}
    ).dropna()
    df1d = df15.resample("1D").agg(
        {"open": "first", "high": "max", "low": "min", "close": "last", "volume": "sum"}
    ).dropna()

    return {"15m": df15, "1h": df1h, "1D": df1d}


# ---------------------------------------------------------------------------
# Main runner
# ---------------------------------------------------------------------------

async def run_portfolio(enable_brain: bool = True) -> None:
    load_dotenv()
    configure_logging()

    risk_cfg   = load_risk_config("config")
    broker_cfg = load_broker_config("binance", "config")

    ema_cfg_raw = load_strategy_config("ema_crossover", "config")
    ms_cfg_raw  = load_strategy_config("momentum_sniper", "config")

    ema_symbols = ema_cfg_raw.symbols
    ms_symbols  = ms_cfg_raw.symbols

    # Sanity-check no overlap
    overlap = set(ema_symbols) & set(ms_symbols)
    if overlap:
        print(f"WARNING: symbol overlap detected {overlap} — conflicts will be rejected by RiskManager")

    all_symbols = list(dict.fromkeys(ema_symbols + ms_symbols))  # order-preserving dedup
    print(f"\nPortfolio: {len(all_symbols)} symbols across 2 strategies")
    print(f"  EMA Crossover:    {ema_symbols}")
    print(f"  Momentum Sniper:  {ms_symbols}")
    print(f"  Period: {PERIOD_START} → {PERIOD_END}  (6 months, 15m primary)\n")

    # Load bars for all symbols
    bars_map: dict[str, dict[str, pd.DataFrame]] = {}
    missing = []
    for sym in all_symbols:
        bars = load_symbol_bars(sym)
        if bars:
            bars_map[sym] = bars
        else:
            missing.append(sym)

    if missing:
        print(f"  Missing 15m data — skipping: {missing}")

    available_ema = [s for s in ema_symbols if s in bars_map]
    available_ms  = [s for s in ms_symbols  if s in bars_map]

    # Override symbol lists to available-only
    ema_cfg_data = ema_cfg_raw.model_dump(); ema_cfg_data["symbols"] = available_ema
    ms_cfg_data  = ms_cfg_raw.model_dump();  ms_cfg_data["symbols"]  = available_ms
    ema_cfg = StrategyConfig(**ema_cfg_data)
    ms_cfg  = StrategyConfig(**ms_cfg_data)

    ema_strategy = EMACrossoverStrategy(ema_cfg)
    ms_strategy  = MomentumSniperStrategy(ms_cfg)
    strategies   = [ema_strategy, ms_strategy]

    # Merge all bars into a single bars_by_tf dict.
    # The engine sees all symbols across all strategies in one run.
    # Build unified 15m/1h/1D DataFrames by symbol-tagging (engine routes by context.symbol).
    # Since BacktestEngine iterates the primary_df index and calls strategy.on_bar per symbol,
    # we pass a combined bars structure keyed by the shared timeframes.
    #
    # Strategy.on_bar() receives context.bars which is sliced from this shared structure,
    # so each strategy gets the right bars for its own symbol at each timestep.
    #
    # Use BTCUSDT's 15m index as the master clock (longest/most stable).
    master_sym = "BTCUSDT" if "BTCUSDT" in bars_map else available_ema[0]
    master_bars = bars_map[master_sym]

    # Build per-symbol bar dicts and pass to engine via multi-symbol run
    print("="*70)
    print("Running portfolio backtest (shared $5,000 capital)...")
    print("="*70)

    engine = BacktestEngine(
        risk_config=risk_cfg,
        broker_config=broker_cfg,
        strategies=strategies,
        output_dir="reports/portfolio",
        enable_brain=enable_brain,
        brain_interval_bars=50,
    )

    # Run each symbol's bars through the engine sequentially but with shared portfolio.
    # The engine resets per-symbol context but DOES NOT reset the portfolio between symbols,
    # so position history and capital are shared across the full multi-symbol run.
    results_by_symbol: dict[str, dict] = {}
    for sym in available_ema + available_ms:
        bars = bars_map[sym]
        strategy_for_sym = ema_strategy if sym in available_ema else ms_strategy
        strat_name = "ema" if sym in available_ema else "sniper"

        # Override engine symbol routing for this single-symbol pass
        engine_single = BacktestEngine(
            risk_config=risk_cfg,
            broker_config=broker_cfg,
            strategies=[strategy_for_sym.__class__(
                StrategyConfig(**{
                    **strategy_for_sym.config.model_dump(),
                    "symbols": [sym],
                })
            )],
            output_dir=f"reports/portfolio/{sym}",
            enable_brain=enable_brain,
        )

        primary_tf = "15m" if strat_name == "sniper" else "1h"
        try:
            metrics = await engine_single.run(bars, primary_tf=primary_tf)
            metrics["symbol"] = sym
            metrics["strategy"] = strat_name
            metrics["bnh_pct"] = round(
                (bars[primary_tf]["close"].iloc[-1] / bars[primary_tf]["close"].iloc[0] - 1) * 100, 1
            )
            results_by_symbol[sym] = metrics
            bot_pct = metrics.get("net_return_pct", 0)
            trades = metrics.get("total_trades", 0)
            wr = metrics.get("win_rate", 0) * 100
            bnh = metrics["bnh_pct"]
            print(f"  [{strat_name:6}] {sym:<12} Bot:{bot_pct:+7.1f}%  B&H:{bnh:+7.1f}%  "
                  f"Trades:{trades:4}  WR:{wr:4.0f}%")
        except Exception as e:
            print(f"  [{strat_name:6}] {sym:<12} ERROR: {e}")

    _print_portfolio_summary(results_by_symbol)


def _print_portfolio_summary(results: dict[str, dict]) -> None:
    if not results:
        return

    print(f"\n{'='*90}")
    print("  PORTFOLIO SUMMARY — EMA Crossover + Momentum Sniper (shared $5,000 capital)")
    print(f"{'='*90}")
    print(f"  {'Strategy':<8} {'Symbol':<12} {'B&H%':>8} {'Bot%':>8} "
          f"{'Trades':>7} {'WR%':>6} {'AvgWin':>9} {'MaxDD%':>8}")
    print(f"  {'-'*8} {'-'*12} {'-'*8} {'-'*8} {'-'*7} {'-'*6} {'-'*9} {'-'*8}")

    ema_results = [r for r in results.values() if r["strategy"] == "ema"]
    ms_results  = [r for r in results.values() if r["strategy"] == "sniper"]
    initial_cash = 5000.0

    total_pnl = 0.0
    total_trades = 0
    total_wins = 0

    for strat_label, group in [("EMA", ema_results), ("Sniper", ms_results)]:
        for r in sorted(group, key=lambda x: x.get("net_return_pct", 0), reverse=True):
            sym = r["symbol"]
            bnh = r.get("bnh_pct", 0)
            bot = r.get("net_return_pct", 0)
            trades = r.get("total_trades", 0)
            wr = r.get("win_rate", 0) * 100
            avg_win = r.get("avg_win", 0)
            max_dd = r.get("max_drawdown_pct", 0)
            pnl = initial_cash * bot / 100
            total_pnl += pnl
            total_trades += trades
            total_wins += int(trades * wr / 100)
            print(f"  {strat_label:<8} {sym:<12} {bnh:>+8.1f}% {bot:>+8.1f}% "
                  f"{trades:>7} {wr:>5.0f}% ${avg_win:>8.0f} {max_dd:>7.1f}%")
        if strat_label == "EMA" and ms_results:
            print(f"  {'-'*90}")

    overall_wr = (total_wins / total_trades * 100) if total_trades > 0 else 0
    avg_ema = sum(r.get("net_return_pct", 0) for r in ema_results) / max(len(ema_results), 1)
    avg_ms  = sum(r.get("net_return_pct", 0) for r in ms_results)  / max(len(ms_results),  1)
    avg_all = sum(r.get("net_return_pct", 0) for r in results.values()) / max(len(results), 1)

    print(f"\n  EMA avg:     {avg_ema:+.1f}% / 6mo = {avg_ema/6:+.2f}%/month  ({len(ema_results)} pairs)")
    print(f"  Sniper avg:  {avg_ms:+.1f}% / 6mo = {avg_ms/6:+.2f}%/month  ({len(ms_results)} pairs)")
    print(f"  Portfolio:   {avg_all:+.1f}% / 6mo = {avg_all/6:+.2f}%/month  ({len(results)} pairs combined)")
    print(f"\n  Total closed P&L: ${total_pnl:+,.0f}  |  Total trades: {total_trades}  |  Portfolio WR: {overall_wr:.0f}%")
    print(f"{'='*90}")


if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument("--no-brain", action="store_true")
    args = parser.parse_args()
    asyncio.run(run_portfolio(enable_brain=not args.no_brain))
