"""Equity curve tracking and CSV/JSON output."""
from __future__ import annotations

import csv
import json
import math
from datetime import datetime
from pathlib import Path
from typing import List

from bot.portfolio.tracker import TradeSummary


class EquityCurve:
    def __init__(self) -> None:
        self._snapshots: list[tuple[datetime, float]] = []

    def record(self, timestamp: datetime, equity: float) -> None:
        self._snapshots.append((timestamp, equity))

    def to_csv(self, path: str | Path) -> None:
        Path(path).parent.mkdir(parents=True, exist_ok=True)
        with open(path, "w", newline="") as f:
            writer = csv.writer(f)
            writer.writerow(["timestamp", "equity"])
            for ts, eq in self._snapshots:
                writer.writerow([ts.isoformat(), round(eq, 4)])

    def max_drawdown(self) -> float:
        if not self._snapshots:
            return 0.0
        peak = self._snapshots[0][1]
        max_dd = 0.0
        for _, equity in self._snapshots:
            if equity > peak:
                peak = equity
            dd = (peak - equity) / peak if peak > 0 else 0.0
            max_dd = max(max_dd, dd)
        return max_dd


def compute_metrics(
    trades: list[TradeSummary],
    initial_capital: float,
    equity_curve: list[float],
) -> dict:
    if not trades:
        return {}

    net_pnls = [t.net_pnl for t in trades]
    wins = [p for p in net_pnls if p > 0]
    losses = [p for p in net_pnls if p <= 0]

    win_rate = len(wins) / len(net_pnls) if net_pnls else 0.0
    avg_win = sum(wins) / len(wins) if wins else 0.0
    avg_loss = abs(sum(losses) / len(losses)) if losses else 0.0
    profit_factor = (sum(wins) / abs(sum(losses))) if losses and sum(losses) != 0 else float("inf")

    # Sharpe (daily returns approximation)
    if len(equity_curve) >= 2:
        daily_returns = [
            (equity_curve[i] - equity_curve[i - 1]) / equity_curve[i - 1]
            for i in range(1, len(equity_curve))
            if equity_curve[i - 1] > 0
        ]
        if daily_returns:
            mean_r = sum(daily_returns) / len(daily_returns)
            variance = sum((r - mean_r) ** 2 for r in daily_returns) / len(daily_returns)
            std_r = math.sqrt(variance) if variance > 0 else 1e-10
            sharpe = (mean_r / std_r) * math.sqrt(252)
            downside = [r for r in daily_returns if r < 0]
            down_std = math.sqrt(sum(r ** 2 for r in downside) / len(downside)) if downside else 1e-10
            sortino = (mean_r / down_std) * math.sqrt(252)
        else:
            sharpe = sortino = 0.0
    else:
        sharpe = sortino = 0.0

    max_dd = 0.0
    if equity_curve:
        peak = equity_curve[0]
        for eq in equity_curve:
            if eq > peak:
                peak = eq
            dd = (peak - eq) / peak if peak > 0 else 0.0
            max_dd = max(max_dd, dd)

    # Max consecutive losses
    max_consec = streak = 0
    for t in trades:
        if t.net_pnl < 0:
            streak += 1
            max_consec = max(max_consec, streak)
        else:
            streak = 0

    total_net = sum(net_pnls)
    total_fees = sum(t.fees_paid for t in trades)
    net_return_pct = total_net / initial_capital * 100 if initial_capital > 0 else 0.0
    avg_duration_h = sum(t.duration_seconds for t in trades) / len(trades) / 3600

    return {
        "total_trades": len(trades),
        "win_rate": round(win_rate, 4),
        "profit_factor": round(profit_factor, 4),
        "max_drawdown_pct": round(max_dd * 100, 2),
        "sharpe_ratio": round(sharpe, 4),
        "sortino_ratio": round(sortino, 4),
        "avg_net_pnl_per_trade": round(total_net / len(trades), 4),
        "total_fees_paid": round(total_fees, 4),
        "net_return_pct": round(net_return_pct, 4),
        "max_consecutive_losses": max_consec,
        "avg_trade_duration_hours": round(avg_duration_h, 2),
        "avg_win": round(avg_win, 4),
        "avg_loss": round(avg_loss, 4),
    }


def save_trade_log(trades: list[TradeSummary], path: str | Path) -> None:
    Path(path).parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w", newline="") as f:
        if not trades:
            return
        writer = csv.DictWriter(f, fieldnames=[
            "symbol", "strategy_id", "side", "entry_price", "exit_price",
            "qty", "gross_pnl", "fees_paid", "net_pnl",
            "opened_at", "closed_at", "duration_seconds",
        ])
        writer.writeheader()
        for t in trades:
            writer.writerow({
                "symbol": t.symbol,
                "strategy_id": t.strategy_id,
                "side": t.side,
                "entry_price": round(t.entry_price, 6),
                "exit_price": round(t.exit_price, 6),
                "qty": round(t.qty, 8),
                "gross_pnl": round(t.gross_pnl, 4),
                "fees_paid": round(t.fees_paid, 4),
                "net_pnl": round(t.net_pnl, 4),
                "opened_at": t.opened_at.isoformat(),
                "closed_at": t.closed_at.isoformat(),
                "duration_seconds": round(t.duration_seconds, 1),
            })


def save_summary(metrics: dict, path: str | Path) -> None:
    Path(path).parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w") as f:
        json.dump(metrics, f, indent=2)
