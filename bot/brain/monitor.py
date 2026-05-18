"""
PerformanceMonitor — real-time per-strategy metrics aggregator.

Maintains a rolling window of the last N closed trades per strategy
and computes live statistics used by BrainEngine for decisions.
"""
from __future__ import annotations

import statistics
from collections import deque
from dataclasses import dataclass, field
from typing import Optional

from bot.portfolio.tracker import TradeSummary


@dataclass
class StrategyMetrics:
    strategy_id: str
    window: int = 20
    recent_trades: deque[TradeSummary] = field(default_factory=lambda: deque(maxlen=20))

    # Cumulative counters
    total_trades: int = 0
    total_net_pnl: float = 0.0
    total_fees: float = 0.0
    consecutive_losses: int = 0
    consecutive_wins: int = 0
    max_consecutive_losses: int = 0

    def __post_init__(self) -> None:
        self.recent_trades: deque[TradeSummary] = deque(maxlen=self.window)

    # ------------------------------------------------------------------
    # Rolling properties (computed from recent_trades window)
    # ------------------------------------------------------------------

    @property
    def win_rate(self) -> float:
        if not self.recent_trades:
            return 0.0
        return sum(1 for t in self.recent_trades if t.net_pnl > 0) / len(self.recent_trades)

    @property
    def profit_factor(self) -> float:
        gross_profit = sum(t.net_pnl for t in self.recent_trades if t.net_pnl > 0)
        gross_loss = abs(sum(t.net_pnl for t in self.recent_trades if t.net_pnl < 0))
        if gross_loss == 0:
            return 1.0 if gross_profit > 0 else 0.0
        return gross_profit / gross_loss

    @property
    def avg_net_pnl(self) -> float:
        if not self.recent_trades:
            return 0.0
        return sum(t.net_pnl for t in self.recent_trades) / len(self.recent_trades)

    @property
    def rolling_sharpe(self) -> float:
        """Trade-level Sharpe: mean(PnL) / std(PnL) over the rolling window."""
        if len(self.recent_trades) < 3:
            return 0.0
        pnls = [t.net_pnl for t in self.recent_trades]
        mean = statistics.mean(pnls)
        std = statistics.stdev(pnls)
        return mean / std if std > 0 else 0.0

    @property
    def rolling_net_pnl(self) -> float:
        return sum(t.net_pnl for t in self.recent_trades)

    @property
    def avg_trade_duration_hours(self) -> float:
        if not self.recent_trades:
            return 0.0
        return statistics.mean(t.duration_seconds / 3600 for t in self.recent_trades)

    def record_trade(self, trade: TradeSummary) -> None:
        self.recent_trades.append(trade)
        self.total_trades += 1
        self.total_net_pnl += trade.net_pnl
        self.total_fees += trade.fees_paid
        if trade.net_pnl > 0:
            self.consecutive_losses = 0
            self.consecutive_wins += 1
        else:
            self.consecutive_wins = 0
            self.consecutive_losses += 1
            self.max_consecutive_losses = max(
                self.max_consecutive_losses, self.consecutive_losses
            )

    def to_dict(self) -> dict:
        return {
            "total_trades": self.total_trades,
            "window_trades": len(self.recent_trades),
            "win_rate": round(self.win_rate, 3),
            "profit_factor": round(self.profit_factor, 3),
            "avg_net_pnl": round(self.avg_net_pnl, 2),
            "rolling_sharpe": round(self.rolling_sharpe, 3),
            "rolling_net_pnl": round(self.rolling_net_pnl, 2),
            "consecutive_losses": self.consecutive_losses,
            "consecutive_wins": self.consecutive_wins,
            "max_consecutive_losses": self.max_consecutive_losses,
            "total_net_pnl": round(self.total_net_pnl, 2),
            "total_fees": round(self.total_fees, 2),
        }


class PerformanceMonitor:
    """Tracks per-strategy rolling metrics; updated by BrainEngine after each fill."""

    def __init__(self, strategy_ids: list[str], window: int = 20) -> None:
        self._window = window
        self._metrics: dict[str, StrategyMetrics] = {
            sid: StrategyMetrics(strategy_id=sid, window=window)
            for sid in strategy_ids
        }
        # Track how many trades we've already ingested per strategy
        self._ingested_count: dict[str, int] = {sid: 0 for sid in strategy_ids}

    def ingest_new_trades(self, all_closed_trades: list[TradeSummary]) -> int:
        """
        Efficiently ingests only trades that haven't been seen yet.
        Returns count of new trades ingested.
        """
        new_total = 0
        by_strategy: dict[str, list[TradeSummary]] = {}
        for t in all_closed_trades:
            by_strategy.setdefault(t.strategy_id, []).append(t)

        for sid, trades in by_strategy.items():
            if sid not in self._metrics:
                continue
            already_seen = self._ingested_count.get(sid, 0)
            new_trades = trades[already_seen:]
            for trade in new_trades:
                self._metrics[sid].record_trade(trade)
            count = len(new_trades)
            self._ingested_count[sid] = self._ingested_count.get(sid, 0) + count
            new_total += count

        return new_total

    def get_metrics(self, strategy_id: str) -> Optional[StrategyMetrics]:
        return self._metrics.get(strategy_id)

    def all_metrics(self) -> dict[str, StrategyMetrics]:
        return self._metrics.copy()

    def to_dict(self) -> dict:
        return {sid: m.to_dict() for sid, m in self._metrics.items()}
