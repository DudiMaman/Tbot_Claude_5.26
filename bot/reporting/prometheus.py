"""Prometheus metrics endpoint."""
from __future__ import annotations

from prometheus_client import Counter, Gauge, start_http_server


class TradingMetrics:
    def __init__(self) -> None:
        # Live state
        self.equity = Gauge("trading_equity_usd", "Current portfolio equity", ["mode"])
        self.open_positions = Gauge("trading_open_positions", "Open position count", ["asset_class"])
        self.daily_pnl = Gauge("trading_daily_pnl_usd", "Daily net P&L")
        self.heartbeat = Gauge("trading_heartbeat_timestamp", "Unix timestamp of last bar processed")

        # Activity counters
        self.fills_total = Counter("trading_fills_total", "Total fills", ["side"])
        self.rejections_total = Counter("trading_rejections_total", "Signal rejections", ["reason"])
        self.api_errors_total = Counter("trading_api_errors_total", "API errors", ["broker"])

        # Performance KPIs (gauges, updated on every bar/fill)
        self.total_net_pnl = Gauge("trading_total_net_pnl_usd", "Cumulative net P&L over all closed trades")
        self.total_fees = Gauge("trading_total_fees_usd", "Cumulative fees paid")
        self.win_rate_pct = Gauge("trading_win_rate_pct", "Win rate of closed trades (%)")
        self.profit_factor = Gauge("trading_profit_factor", "Sum wins / |sum losses|")
        self.max_drawdown_pct = Gauge("trading_max_drawdown_pct", "Peak-to-trough drawdown (%)")
        self.closed_trades_total = Gauge("trading_closed_trades_total", "Count of closed trades")
        self.consecutive_losses = Gauge("trading_consecutive_losses", "Current consecutive-loss streak")

        # Safety state (0=normal, 1=defensive, 2=streak_halt, 3=daily_loss_breach)
        self.breaker_state = Gauge("trading_breaker_state", "0=normal,1=defensive,2=streak_halt,3=daily_loss")

    def start_server(self, port: int = 8000) -> None:
        start_http_server(port)
