"""Lightweight JSON API for Grafana Infinity plugin.

Exposes:
  GET /status        — bot health + circuit breaker state
  GET /trades        — full closed trade history
  GET /symbol_stats  — per-symbol aggregates (P&L, win rate, profit factor)

All endpoints return JSON and set CORS headers so a browser-side Grafana
Cloud dashboard can fetch them when the bot is exposed publicly.
"""
from __future__ import annotations

from datetime import datetime, timezone
from typing import TYPE_CHECKING

from aiohttp import web

if TYPE_CHECKING:
    from bot.portfolio.manager import PortfolioManager
    from bot.risk.manager import RiskManager


_runner: web.AppRunner | None = None

_CORS_HEADERS = {
    "Access-Control-Allow-Origin": "*",
    "Access-Control-Allow-Methods": "GET, OPTIONS",
    "Access-Control-Allow-Headers": "*",
}


def _json(payload) -> web.Response:
    return web.json_response(payload, headers=_CORS_HEADERS)


def _build_app(portfolio: "PortfolioManager", risk_mgr: "RiskManager") -> web.Application:
    app = web.Application()

    async def status(request: web.Request) -> web.Response:
        halted = risk_mgr._streak_guard.is_halted
        daily_breached = risk_mgr._daily_breaker.is_triggered
        paused = halted or daily_breached
        tracker = portfolio.tracker

        return _json({
            "status": "paused" if paused else "live",
            "paused": paused,
            "daily_loss_breached": daily_breached,
            "losing_streak_halted": halted,
            "breaker_state": risk_mgr.breaker_state_code(),
            "equity_usd": round(portfolio.equity(), 2),
            "daily_pnl_usd": round(portfolio.daily_net_pnl(), 2),
            "total_net_pnl_usd": round(tracker.total_net_pnl(), 2),
            "open_positions": portfolio.open_position_count(),
            "consecutive_losses": portfolio.consecutive_losses(),
            "closed_trades": len(tracker.closed_trades),
            "win_rate_pct": round(tracker.win_rate() * 100.0, 2),
            "profit_factor": round(tracker.profit_factor(), 2),
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
        rows.sort(key=lambda r: r["time"], reverse=True)
        return _json(rows)

    async def symbol_stats(request: web.Request) -> web.Response:
        return _json(portfolio.tracker.symbol_stats())

    async def options_handler(request: web.Request) -> web.Response:
        return web.Response(headers=_CORS_HEADERS)

    app.router.add_get("/status", status)
    app.router.add_get("/trades", trades)
    app.router.add_get("/symbol_stats", symbol_stats)
    app.router.add_route("OPTIONS", "/{tail:.*}", options_handler)
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
