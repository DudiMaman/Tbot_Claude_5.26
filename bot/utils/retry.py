"""Exponential-backoff retry decorator for API calls."""
from __future__ import annotations

import asyncio
import functools
import logging
import random
from typing import Any, Callable, Type

logger = logging.getLogger(__name__)


def async_retry(
    max_attempts: int = 5,
    base_delay: float = 2.0,
    exceptions: tuple[Type[Exception], ...] = (Exception,),
) -> Callable[..., Any]:
    def decorator(func: Callable[..., Any]) -> Callable[..., Any]:
        @functools.wraps(func)
        async def wrapper(*args: Any, **kwargs: Any) -> Any:
            for attempt in range(1, max_attempts + 1):
                try:
                    return await func(*args, **kwargs)
                except exceptions as exc:
                    if attempt == max_attempts:
                        raise
                    delay = base_delay ** attempt + random.uniform(0, 1)
                    logger.warning(
                        "retry_attempt",
                        extra={
                            "func": func.__name__,
                            "attempt": attempt,
                            "delay_s": round(delay, 2),
                            "error": str(exc),
                        },
                    )
                    await asyncio.sleep(delay)
        return wrapper
    return decorator
