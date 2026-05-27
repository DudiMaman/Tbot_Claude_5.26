#!/usr/bin/env python3
"""
Backtest momentum_sniper on a curated 20-pair universe to identify winners
for live trading expansion.

Fetches 6 months of 15m + 1h klines from Binance REST for each pair, runs
the backtest, and prints a ranked summary sorted by a composite score
(profit_factor * win_rate * net_return_pct / max_drawdown).

Usage (inside the bot container so deps are available):
  docker exec docker-bot-1 python scripts/explore_universe.py
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
from bot.strategies.momentum_sniper import MomentumSniperStrategy


# Mix of L1/L2, DeFi, memes, ecosystem coins — chosen to match the
# high-volatility / retail-driven profile of XRP/ARB/OP (current winners).
UNIVERSE = [
    # Currently live (control group)
    "XRPUSDT", "ARBUSDT", "OPUSDT",
    # Large-cap alts
    "SOLUSDT", "AVAXUSDT", "LINKUSDT", "DOTUSDT", "ATOMUSDT",
    # L1s (newer)
    "NEARUSDT", "SUIUSDT", "APTUSDT", "INJUSDT", "TIAUSDT", "SEIUSDT",
    # Memes (high vol)
    "DOGEUSDT", "PEPEUSDT", "WIFUSDT",
    # DeFi / infra
    "UNIUSDT", "AAVEUSDT", "ENAUSDT",
]


async def fetch_pair_data(
    loader: HistoricalLoader, symbol: str, start: date, end: date
) -> dict | None:
    """Fetch 15m + 1h for a pair. Returns dict of TF -> DataFrame, or None on failure."""
    try:
        df_15m = await loader.fetch_crypto(symbol, "15m", start, end)
        df_1h = await loader.fetch_crypto(symbol, "1h", start, end)
        df_1d = await loader.fetch_crypto(symbol, "1D", start, end)
        if df_15m.empty or df_1h.empty:
            return None
        bars = {"15m": df_15m, "1h": df_1h}
        if not df_1d.empty:
            bars["1D"] = df_1d
        return bars
    except Exception as e:
        print(f"    fetch error: {e}")
        return None


async def backtest_symbol(
    symbol: str,
    bars: dict,
    config_dir: str = "config",
) -> dict | None:
    risk_cfg = load_risk_config(config_dir)
    broker_cfg = load_broker_config("binance", config_dir)
    strategy_cfg = load_strategy_config("momentum_sniper", config_dir)

    cfg_data = strategy_cfg.model_dump()
    cfg_data["symbols"] = [symbol]
    strategy_cfg = StrategyConfig(**cfg_data)
    strategy = MomentumSniperStrategy(strategy_cfg)

    engine = BacktestEngine(
        risk_config=risk_cfg,
        broker_config=broker_cfg,
        strategies=[strategy],
        output_dir=f"reports/universe/{symbol}",
        enable_brain=True,
        brain_interval_bars=50,
    )
    try:
        metrics = await engine.run(bars, primary_tf="15m")
        primary_df = bars["15m"]
        metrics["symbol"] = symbol
        metrics["bnh_pct"] = round(
            (primary_df["close"].iloc[-1] / primary_df["close"].iloc[0] - 1) * 100, 1
        )
        return metrics
    except Exception as e:
        print(f"    backtest error: {e}")
        return None


def composite_score(m: dict) -> float:
    """Single number for ranking. Higher = better.

    Combines return, win rate, profit factor, penalises drawdown.
    Returns 0 if any factor disqualifies (e.g., zero trades).
    """
    trades = m.get("total_trades", 0)
    if trades < 5:  # too few trades to be meaningful
        return 0.0
    ret = m.get("net_return_pct", 0)
    if ret <= 0:
        return ret  # keep negative for sort, but no bonus
    wr = m.get("win_rate", 0)  # 0..1
    pf = min(m.get("profit_factor", 0), 10)  # cap to avoid outliers
    dd = max(abs(m.get("max_drawdown_pct", 1)), 1)  # avoid div-by-0
    return ret * wr * pf / dd


def print_ranked(results: list[dict]) -> None:
    if not results:
        print("No results.")
        return

    ranked = sorted(results, key=composite_score, reverse=True)

    print(f"\n{'='*100}")
    print(f"  MOMENTUM SNIPER — 6-month backtest, {len(results)} pairs")
    print(f"{'='*100}")
    header = (
        f"  {'Rank':<5} {'Symbol':<12} {'Bot%':>8} {'B&H%':>8} {'Trades':>7} "
        f"{'WR%':>6} {'PF':>6} {'DD%':>7} {'Score':>8}"
    )
    print(header)
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
        marker = " ★" if score > 5 else "  "  # highlight strong candidates
        print(
            f"  {i:<3}{marker} {sym:<12} {bot:>+7.1f}% {bnh:>+7.1f}% {trades:>7} "
            f"{wr:>5.0f}% {pf_str:>6} {dd:>+6.1f}% {score:>8.2f}"
        )
    print("=" * 100)

    # Recommendation: top 7 with score > 3 and positive return
    candidates = [r for r in ranked if composite_score(r) > 3 and r.get("net_return_pct", 0) > 0]
    top = candidates[:7]
    if top:
        print(f"\n  RECOMMENDED for live trading ({len(top)} pairs):")
        for r in top:
            print(
                f"    {r['symbol']:<12}  +{r['net_return_pct']:>5.1f}%  "
                f"PF={r.get('profit_factor', 0):.2f}  "
                f"trades={r.get('total_trades', 0)}"
            )
    else:
        print("\n  No pairs cleared the recommendation threshold "
              "(score > 3, positive return).")


async def main() -> None:
    load_dotenv()
    configure_logging()

    today = date.today()
    end = today + timedelta(days=1)
    start = today - timedelta(days=180)
    print(f"Backtest period: {start} → {today} (6 months)")
    print(f"Universe: {len(UNIVERSE)} pairs\n")

    loader = HistoricalLoader()
    results: list[dict] = []

    for i, symbol in enumerate(UNIVERSE, 1):
        print(f"[{i}/{len(UNIVERSE)}] {symbol}")
        print(f"  Fetching 15m + 1h + 1D...")
        bars = await fetch_pair_data(loader, symbol, start, end)
        if bars is None:
            print(f"  SKIP — no data\n")
            continue
        print(f"  Got {len(bars['15m'])} 15m bars, {len(bars['1h'])} 1h bars")
        print(f"  Running backtest...")
        metrics = await backtest_symbol(symbol, bars)
        if metrics is None:
            print(f"  SKIP — backtest failed\n")
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
