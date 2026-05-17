"""Prometheus metrics endpoint."""
from __future__ import annotations

import threading
from http.server import HTTPServer

from prometheus_client import Counter, Gauge, MetricsHandler, start_http_server


class TradingMetrics:
    def __init__(self) -> None:
        self.equity = Gauge("trading_equity_usd", "Current portfolio equity", ["mode"])
        self.open_positions = Gauge("trading_open_positions", "Open position count", ["asset_class"])
        self.daily_pnl = Gauge("trading_daily_pnl_usd", "Daily net P&L")
        self.fills_total = Counter("trading_fills_total", "Total fills", ["side"])
        self.rejections_total = Counter("trading_rejections_total", "Signal rejections", ["reason"])
        self.api_errors_total = Counter("trading_api_errors_total", "API errors", ["broker"])

    def start_server(self, port: int = 8000) -> None:
        start_http_server(port)
