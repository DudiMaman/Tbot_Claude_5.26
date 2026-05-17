"""Structured JSON logging setup using structlog."""
from __future__ import annotations

import logging
import os
import sys
from pathlib import Path

import structlog


def configure_logging(log_dir: str = "logs", log_level: str = "INFO") -> None:
    Path(log_dir).mkdir(parents=True, exist_ok=True)
    level = getattr(logging, log_level.upper(), logging.INFO)

    shared_processors = [
        structlog.contextvars.merge_contextvars,
        structlog.stdlib.add_logger_name,
        structlog.stdlib.add_log_level,
        structlog.processors.TimeStamper(fmt="iso"),
        structlog.processors.StackInfoRenderer(),
    ]

    is_tty = sys.stdout.isatty() and os.environ.get("LOG_FORMAT", "json") != "json"
    if is_tty:
        renderer = structlog.dev.ConsoleRenderer()
    else:
        renderer = structlog.processors.JSONRenderer()

    structlog.configure(
        processors=shared_processors + [
            structlog.stdlib.ProcessorFormatter.wrap_for_formatter,
        ],
        wrapper_class=structlog.stdlib.BoundLogger,
        context_class=dict,
        logger_factory=structlog.stdlib.LoggerFactory(),
        cache_logger_on_first_use=True,
    )

    formatter = structlog.stdlib.ProcessorFormatter(
        processor=renderer,
        foreign_pre_chain=shared_processors,
    )

    # Root handler (stdout)
    root_handler = logging.StreamHandler(sys.stdout)
    root_handler.setFormatter(formatter)

    # Trade log
    trade_handler = logging.FileHandler(f"{log_dir}/trade.log")
    trade_handler.setFormatter(formatter)
    trade_logger = logging.getLogger("trade")
    trade_logger.addHandler(trade_handler)

    # Error log
    error_handler = logging.FileHandler(f"{log_dir}/error.log")
    error_handler.setLevel(logging.ERROR)
    error_handler.setFormatter(formatter)

    root = logging.getLogger()
    root.addHandler(root_handler)
    root.addHandler(error_handler)
    root.setLevel(level)
