#!/usr/bin/env python3
"""
Universe backtest for breakout strategy.

The breakout strategy is bidirectional and adapts to direction:
- Long when price breaks above 20-bar high in a daily uptrend
- Short when price breaks below 20-bar low in a daily downtrend
- Volume confirmation + ATR-based stops
- No fixed TP — 15% trailing stop captures big moves

This is what gets tested before we write any new code. If it fails on
the same 20-pair / 6-month universe, we have evidence that even adaptive
bidirectional strategies don't work in current conditions.
"""
from __future__ import annotations

import asyncio
import sys
from datetime import date, timedelta
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from dotenv import load_dotenv

from bot.core.config import (
    StrategyConfig,
    load_broker_config,
    load_risk_config,
    load_strategy_config,
)
from bot.backtesting.engine import BacktestEngine
from bot.data.historical import HistoricalLoader
from bot.reporting.logger import configure_logging
from bot.strategies.breakout import BreakoutStrategy


UNIVERSE = [
    "XRPUSDT", "ARBUSDT", "OPUSDT",
    "SOLUSDT", "AVAXUSDT", "LINKUSDT", "DOTUSDT", "ATOMUSDT",
    "NEARUSDT", "SUIUSDT", "APTUSDT", "INJUSDT", "TIAUSDT", "SEIUSDT",
    "DOGEUSDT", "PEPEUSDT", "WIFUSDT",
    "UNIUSDT", "AAVEUSDT", "ENAUSDT",
]


async def fetch_pair_data(loader, symbol, start, end):
    try:
        df_4h = await loader.fetch_crypto(symbol, "4h", start, end)
        df_1d = await loader.fetch_crypto(symbol, "1D", start, end)
        if df_4h.empty:
            return None
        bars = {"4h": df_4h}
        if not df_1d.empty:
            bars["1D"] = df_1d
        return bars
    except Exception as e:
        print(f"    fetch error: {e}")
        return None


async def backtest_symbol(symbol, bars):
    risk_cfg = load_risk_config("config")
    broker_cfg = load_broker_config("binance", "config")
    strategy_cfg = load_strategy_config("breakout", "config")
    cfg_data = strategy_cfg.model_dump()
    cfg_data["symbols"] = [symbol]
    strategy_cfg = StrategyConfig(**cfg_data)
    strategy = BreakoutStrategy(strategy_cfg)

    engine = BacktestEngine(
        risk_config=risk_cfg,
        broker_config=broker_cfg,
        strategies=[strategy],
        output_dir=f"reports/breakout_universe/{symbol}",
        enable_brain=False,  # baseline without brain
        brain_interval_bars=50,
    )
    try:
        metrics = await engine.run(bars, primary_tf="4h")
        bnh = (bars["4h"]["close"].iloc[-1] / bars["4h"]["close"].iloc[0] - 1) * 100
        metrics["symbol"] = symbol
        metrics["bnh_pct"] = round(bnh, 1)
        return metrics
    except Exception as e:
        print(f"    backtest error: {e}")
        return None


def composite_score(m):
    trades = m.get("total_trades", 0)
    if trades < 3:
        return 0.0
    ret = m.get("net_return_pct", 0)
    if ret <= 0:
        return ret
    wr = m.get("win_rate", 0)
    pf = min(m.get("profit_factor", 0), 10)
    dd = max(abs(m.get("max_drawdown_pct", 1)), 1)
    return ret * wr * pf / dd


def print_ranked(results):
    if not results:
        print("No results.")
        return
    ranked = sorted(results, key=composite_score, reverse=True)
    print(f"\n{'='*100}")
    print(f"  BREAKOUT (bidirectional) — 6-month backtest (no brain), {len(results)} pairs")
    print(f"{'='*100}")
    print(f"  {'Rank':<5} {'Symbol':<12} {'Bot%':>8} {'B&H%':>8} {'Trades':>7} "
          f"{'WR%':>6} {'PF':>6} {'DD%':>7} {'Score':>8}")
    print("  " + "-" * 96)
    for i, r in enumerate(ranked, 1):
        sym = r["symbol"]
        bot = r.get("net_return_pct", 0)
        bnh = r.get("bnh_pct", 0)
        trades = r.get("total_trades", 0)
        wr = r.get("win_rate", 0) * 100
        pf = r.get("profit_factor", 0)
        dd = r.get("max_drawdown_pct", 0)
        score = composite_score(r)
        pf_str = f"{pf:.2f}" if pf < 99 else ">99"
        marker = " ★" if score > 3 else "  "
        print(f"  {i:<3}{marker} {sym:<12} {bot:>+7.1f}% {bnh:>+7.1f}% {trades:>7} "
              f"{wr:>5.0f}% {pf_str:>6} {dd:>+6.1f}% {score:>8.2f}")
    print("=" * 100)
    candidates = [r for r in ranked if composite_score(r) > 1 and r.get("net_return_pct", 0) > 0]
    if candidates:
        print(f"\n  POSITIVE-RETURN pairs ({len(candidates)}):")
        for r in candidates[:10]:
            print(f"    {r['symbol']:<12}  +{r['net_return_pct']:>5.1f}%  "
                  f"PF={r.get('profit_factor', 0):.2f}  trades={r.get('total_trades', 0)}  "
                  f"WR={r.get('win_rate', 0)*100:.0f}%  DD={r.get('max_drawdown_pct', 0):+.1f}%")
    else:
        print("\n  No pairs with positive returns.")

    # Aggregate summary
    avg_ret = sum(r.get("net_return_pct", 0) for r in results) / len(results)
    avg_bnh = sum(r.get("bnh_pct", 0) for r in results) / len(results)
    positive = sum(1 for r in results if r.get("net_return_pct", 0) > 0)
    print(f"\n  AGGREGATE: {positive}/{len(results)} positive  "
          f"avg strategy: {avg_ret:+.1f}%  avg B&H: {avg_bnh:+.1f}%")


async def main():
    load_dotenv()
    configure_logging(log_level="WARNING")

    today = date.today()
    end = today + timedelta(days=1)
    start = today - timedelta(days=180)
    print(f"Breakout (bidirectional) backtest: {start} → {today} (6 months)\n")

    loader = HistoricalLoader()
    results = []
    for i, symbol in enumerate(UNIVERSE, 1):
        print(f"[{i}/{len(UNIVERSE)}] {symbol}")
        bars = await fetch_pair_data(loader, symbol, start, end)
        if bars is None:
            print("  SKIP\n")
            continue
        print(f"  Got {len(bars['4h'])} 4h bars")
        metrics = await backtest_symbol(symbol, bars)
        if metrics is None:
            print("  SKIP\n")
            continue
        ret = metrics.get("net_return_pct", 0)
        tr = metrics.get("total_trades", 0)
        wr = metrics.get("win_rate", 0) * 100
        pf = metrics.get("profit_factor", 0)
        print(f"  → ret: {ret:+.1f}%  trades: {tr}  WR: {wr:.0f}%  PF: {pf:.2f}\n")
        results.append(metrics)

    print_ranked(results)


if __name__ == "__main__":
    asyncio.run(main())
