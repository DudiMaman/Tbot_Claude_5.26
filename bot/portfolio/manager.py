"""
PortfolioManager — tracks all open positions, cash, unrealized P&L.
The single source of truth for current portfolio state.
"""
from __future__ import annotations

import structlog
from datetime import datetime, timezone
from typing import Optional

from bot.core.events import FillEvent, OHLCVBar, Signal
from bot.portfolio.position import Position
from bot.portfolio.tracker import PnLTracker

logger = structlog.get_logger(__name__)


class PortfolioManager:
    def __init__(self, initial_cash: float, asset_class_map: dict[str, str] | None = None) -> None:
        self._cash = initial_cash
        self._initial_cash = initial_cash
        self._positions: dict[str, Position] = {}       # symbol → open position
        self._idempotency_keys: set[str] = set()
        self._tracker = PnLTracker()
        self._asset_class_map: dict[str, str] = asset_class_map or {}  # symbol → "crypto"|"stocks"

    # ------------------------------------------------------------------
    # Position lifecycle
    # ------------------------------------------------------------------

    def has_position(self, symbol: str) -> bool:
        return symbol in self._positions

    def is_duplicate(self, idempotency_key: str) -> bool:
        return idempotency_key in self._idempotency_keys

    def open_position(self, fill: FillEvent, signal: Signal) -> Position:
        if fill.idempotency_key:
            self._idempotency_keys.add(fill.idempotency_key)

        side = "long" if fill.side == "buy" else "short"
        pos = Position(
            symbol=fill.symbol,
            side=side,
            entry_price=fill.avg_price,
            qty=fill.qty_filled,
            qty_filled=fill.qty_filled,
            stop_loss=signal.stop_loss,
            take_profit=signal.take_profit,
            strategy_id=signal.strategy_id,
            idempotency_key=fill.idempotency_key,
            opened_at=fill.timestamp,
            trailing_stop_pct=signal.metadata.get("trailing_stop_pct") if signal.metadata else None,
            trailing_stop_high=fill.avg_price,
            fees_paid_entry=fill.fee_paid,
        )
        self._positions[fill.symbol] = pos
        if side == "long":
            self._cash -= fill.qty_filled * fill.avg_price + fill.fee_paid
        else:
            # Short open: we receive proceeds from selling
            self._cash += fill.qty_filled * fill.avg_price - fill.fee_paid
        logger.info(
            "position_opened",
            symbol=fill.symbol,
            side=pos.side,
            entry=fill.avg_price,
            qty=fill.qty_filled,
            sl=signal.stop_loss,
            tp=signal.take_profit,
        )
        return pos

    def close_position(self, fill: FillEvent) -> Optional[Position]:
        pos = self._positions.pop(fill.symbol, None)
        if pos is None:
            return None

        if pos.side == "long":
            # Sell to close long: receive proceeds
            self._cash += fill.qty_filled * fill.avg_price - fill.fee_paid
        else:
            # Buy to close short: pay to buy back
            self._cash -= fill.qty_filled * fill.avg_price + fill.fee_paid
        pos.close(fill.avg_price, fill.fee_paid, fill.timestamp)
        summary = self._tracker.record_close(pos)
        logger.info(
            "position_closed",
            symbol=fill.symbol,
            net_pnl=round(summary.net_pnl, 4),
            gross_pnl=round(summary.gross_pnl, 4),
            fees=round(summary.fees_paid, 4),
        )
        return pos

    def update_on_bar(self, bar: OHLCVBar) -> None:
        """Update trailing stops on each new bar."""
        pos = self._positions.get(bar.symbol)
        if pos is None:
            return
        new_sl = pos.update_trailing_stop(bar.close)
        if new_sl is not None:
            logger.debug("trailing_stop_updated", symbol=bar.symbol, new_sl=round(new_sl, 6))

    # ------------------------------------------------------------------
    # Portfolio view (read-only for strategies)
    # ------------------------------------------------------------------

    @property
    def cash(self) -> float:
        return self._cash

    @property
    def open_positions(self) -> dict[str, Position]:
        return dict(self._positions)

    def equity(self, prices: dict[str, float] | None = None) -> float:
        unrealized = 0.0
        if prices:
            for sym, pos in self._positions.items():
                price = prices.get(sym, pos.entry_price)
                if pos.side == "long":
                    unrealized += (price - pos.entry_price) * pos.qty_filled
                else:
                    unrealized += (pos.entry_price - price) * pos.qty_filled
        return self._cash + unrealized

    def open_position_count(self) -> int:
        return len(self._positions)

    def notional_by_asset_class(self, prices: dict[str, float] | None = None) -> dict[str, float]:
        result: dict[str, float] = {"crypto": 0.0, "stocks": 0.0, "unknown": 0.0}
        for sym, pos in self._positions.items():
            price = (prices or {}).get(sym, pos.entry_price)
            notional = pos.qty_filled * price
            cls = self._asset_class_map.get(sym, "unknown")
            result[cls] = result.get(cls, 0.0) + notional
        return result

    def daily_net_pnl(self) -> float:
        return self._tracker.daily_net_pnl

    def consecutive_losses(self) -> int:
        return self._tracker.consecutive_losses

    def reset_daily_pnl(self) -> None:
        self._tracker.reset_daily()

    @property
    def tracker(self) -> PnLTracker:
        return self._tracker
