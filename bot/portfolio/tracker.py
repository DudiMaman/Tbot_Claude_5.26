"""Gross vs. net P&L accounting and trade history."""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from typing import List

from bot.portfolio.position import Position


@dataclass
class TradeSummary:
    symbol: str
    strategy_id: str
    side: str
    entry_price: float
    exit_price: float
    qty: float
    gross_pnl: float
    fees_paid: float
    net_pnl: float
    opened_at: datetime
    closed_at: datetime
    duration_seconds: float


class PnLTracker:
    def __init__(self) -> None:
        self._closed_trades: list[TradeSummary] = []
        self._daily_net_pnl: float = 0.0
        self._day_start: datetime | None = None
        self._consecutive_losses: int = 0

    def record_close(self, pos: Position) -> TradeSummary:
        assert pos.closed_at is not None
        assert pos.exit_price is not None

        summary = TradeSummary(
            symbol=pos.symbol,
            strategy_id=pos.strategy_id,
            side=pos.side,
            entry_price=pos.entry_price,
            exit_price=pos.exit_price,
            qty=pos.qty_filled,
            gross_pnl=pos.gross_pnl,
            fees_paid=pos.fees_paid_entry + pos.fees_paid_exit,
            net_pnl=pos.net_pnl,
            opened_at=pos.opened_at,
            closed_at=pos.closed_at,
            duration_seconds=(pos.closed_at - pos.opened_at).total_seconds(),
        )
        self._closed_trades.append(summary)
        self._daily_net_pnl += summary.net_pnl

        if summary.net_pnl < 0:
            self._consecutive_losses += 1
        else:
            self._consecutive_losses = 0

        return summary

    def reset_daily(self) -> None:
        self._daily_net_pnl = 0.0

    @property
    def daily_net_pnl(self) -> float:
        return self._daily_net_pnl

    @property
    def consecutive_losses(self) -> int:
        return self._consecutive_losses

    @property
    def closed_trades(self) -> list[TradeSummary]:
        return list(self._closed_trades)

    def total_net_pnl(self) -> float:
        return sum(t.net_pnl for t in self._closed_trades)

    def win_rate(self) -> float:
        if not self._closed_trades:
            return 0.0
        wins = sum(1 for t in self._closed_trades if t.net_pnl > 0)
        return wins / len(self._closed_trades)

    def total_fees_paid(self) -> float:
        return sum(t.fees_paid for t in self._closed_trades)
