#!/usr/bin/env python3
"""
Diagnostic: backtest momentum_sniper on a single pair with brain on/off
to isolate whether the brain is destroying the strategy edge.

Usage:
  python scripts/diag_brain_impact.py --symbol XRPUSDT --from 2025-11-27 --to 2026-05-27
"""
from __future__ import annotations

import argparse
import asyncio
import sys
from datetime import date
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


async def run_one(symbol: str, bars: dict, enable_brain: bool) -> dict:
    risk_cfg = load_risk_config("config")
    broker_cfg = load_broker_config("binance", "config")
    strategy_cfg = load_strategy_config("momentum_sniper", "config")

    cfg_data = strategy_cfg.model_dump()
    cfg_data["symbols"] = [symbol]
    strategy_cfg = StrategyConfig(**cfg_data)
    strategy = MomentumSniperStrategy(strategy_cfg)

    suffix = "brain_on" if enable_brain else "brain_off"
    engine = BacktestEngine(
        risk_config=risk_cfg,
        broker_config=broker_cfg,
        strategies=[strategy],
        output_dir=f"reports/diag/{symbol}_{suffix}",
        enable_brain=enable_brain,
        brain_interval_bars=50,
    )
    metrics = await engine.run(bars, primary_tf="15m")
    return metrics


def fmt(m: dict, label: str) -> str:
    return (
        f"{label}:\n"
        f"  Trades:         {m.get('total_trades', 0)}\n"
        f"  Win rate:       {m.get('win_rate', 0)*100:.1f}%\n"
        f"  Net return:     {m.get('net_return_pct', 0):+.2f}%\n"
        f"  Profit factor:  {m.get('profit_factor', 0):.2f}\n"
        f"  Avg win:        ${m.get('avg_win', 0):.2f}\n"
        f"  Avg loss:       ${m.get('avg_loss', 0):.2f}\n"
        f"  Max drawdown:   {m.get('max_drawdown_pct', 0):.1f}%\n"
        f"  Total net P&L:  ${m.get('total_net_pnl', 0):+.2f}\n"
    )


async def main() -> None:
    load_dotenv()
    configure_logging(log_level="WARNING")  # quiet during diagnostic

    parser = argparse.ArgumentParser()
    parser.add_argument("--symbol", default="XRPUSDT")
    parser.add_argument("--from", dest="date_from", required=True)
    parser.add_argument("--to", dest="date_to", required=True)
    args = parser.parse_args()

    start = date.fromisoformat(args.date_from)
    end = date.fromisoformat(args.date_to)

    print(f"Fetching {args.symbol} 15m + 1h + 1D from {start} to {end}...")
    loader = HistoricalLoader()
    df_15m = await loader.fetch_crypto(args.symbol, "15m", start, end)
    df_1h = await loader.fetch_crypto(args.symbol, "1h", start, end)
    df_1d = await loader.fetch_crypto(args.symbol, "1D", start, end)
    if df_15m.empty or df_1h.empty:
        print("Missing required data.")
        sys.exit(1)
    bars = {"15m": df_15m, "1h": df_1h}
    if not df_1d.empty:
        bars["1D"] = df_1d
    print(f"  {len(df_15m)} 15m bars, {len(df_1h)} 1h bars, {len(df_1d)} 1D bars\n")

    print("Running WITH brain enabled...")
    m_on = await run_one(args.symbol, bars, enable_brain=True)
    print("Running WITHOUT brain...")
    m_off = await run_one(args.symbol, bars, enable_brain=False)

    print("\n" + "=" * 60)
    print(f"  {args.symbol}  —  {start} → {end}")
    print("=" * 60)
    print(fmt(m_on, "WITH BRAIN"))
    print(fmt(m_off, "NO BRAIN  "))

    delta_ret = m_off.get("net_return_pct", 0) - m_on.get("net_return_pct", 0)
    delta_wr = (m_off.get("win_rate", 0) - m_on.get("win_rate", 0)) * 100
    delta_pf = m_off.get("profit_factor", 0) - m_on.get("profit_factor", 0)
    print("=" * 60)
    print(f"DELTA (no-brain - with-brain):")
    print(f"  Return:    {delta_ret:+.2f} pp")
    print(f"  Win rate:  {delta_wr:+.2f} pp")
    print(f"  PF:        {delta_pf:+.2f}")
    print("=" * 60)


if __name__ == "__main__":
    asyncio.run(main())
