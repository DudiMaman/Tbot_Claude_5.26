"""Lightweight JSON API for Grafana Infinity plugin.

Exposes:
  GET /status  — bot health + circuit breaker state
  GET /trades  — full closed trade history
"""
from __future__ import annotations

import asyncio
from datetime import datetime, timezone
from typing import TYPE_CHECKING

from aiohttp import web

if TYPE_CHECKING:
    from bot.portfolio.manager import PortfolioManager
    from bot.risk.manager import RiskManager


_runner: web.AppRunner | None = None


def _build_app(portfolio: "PortfolioManager", risk_mgr: "RiskManager") -> web.Application:
    app = web.Application()

    async def status(request: web.Request) -> web.Response:
        halted = risk_mgr._streak_guard.is_halted
        daily_breached = risk_mgr._daily_breaker.is_triggered
        paused = halted or daily_breached

        return web.json_response({
            "status": "paused" if paused else "live",
            "paused": paused,
            "daily_loss_breached": daily_breached,
            "losing_streak_halted": halted,
            "equity_usd": round(portfolio.equity(), 2),
            "daily_pnl_usd": round(portfolio.daily_net_pnl(), 2),
            "open_positions": portfolio.open_position_count(),
            "consecutive_losses": portfolio.consecutive_losses(),
            "timestamp": datetime.now(timezone.utc).isoformat(),
        })

    async def trades(request: web.Request) -> web.Response:
        rows = []
        for t in portfolio.tracker.closed_trades:
            rows.append({
                "time": t.closed_at.isoformat(),
                "symbol": t.symbol,
                "strategy": t.strategy_id,
                "side": t.side,
                "entry_price": round(t.entry_price, 6),
                "exit_price": round(t.exit_price, 6),
                "qty": round(t.qty, 4),
                "gross_pnl": round(t.gross_pnl, 4),
                "fees": round(t.fees_paid, 4),
                "net_pnl": round(t.net_pnl, 4),
                "duration_min": round(t.duration_seconds / 60, 1),
                "result": "win" if t.net_pnl > 0 else "loss",
            })
        # newest first
        rows.sort(key=lambda r: r["time"], reverse=True)
        return web.json_response(rows)

    app.router.add_get("/status", status)
    app.router.add_get("/trades", trades)
    return app


async def start_api(
    portfolio: "PortfolioManager",
    risk_mgr: "RiskManager",
    port: int = 8001,
) -> None:
    global _runner
    app = _build_app(portfolio, risk_mgr)
    _runner = web.AppRunner(app)
    await _runner.setup()
    site = web.TCPSite(_runner, "0.0.0.0", port)
    await site.start()


async def stop_api() -> None:
    global _runner
    if _runner:
        await _runner.cleanup()
        _runner = None
