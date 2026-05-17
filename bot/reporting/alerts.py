"""Telegram daily P&L alerts."""
from __future__ import annotations

import logging
import os

logger = logging.getLogger(__name__)


async def send_telegram(message: str) -> None:
    token = os.environ.get("TELEGRAM_BOT_TOKEN", "")
    chat_id = os.environ.get("TELEGRAM_CHAT_ID", "")
    if not token or not chat_id:
        logger.debug("Telegram not configured; skipping alert")
        return
    try:
        import aiohttp
        url = f"https://api.telegram.org/bot{token}/sendMessage"
        async with aiohttp.ClientSession() as session:
            await session.post(url, json={"chat_id": chat_id, "text": message, "parse_mode": "Markdown"})
    except Exception as e:
        logger.warning(f"Telegram alert failed: {e}")


async def send_daily_summary(
    equity: float,
    daily_pnl: float,
    open_positions: int,
    win_rate_today: float,
    mode: str,
) -> None:
    pnl_icon = "🟢" if daily_pnl >= 0 else "🔴"
    msg = (
        f"*Daily Trading Summary*\n"
        f"Mode: `{mode}`\n"
        f"Equity: `${equity:,.2f}`\n"
        f"{pnl_icon} Day P&L: `${daily_pnl:+,.2f}`\n"
        f"Open positions: `{open_positions}`\n"
        f"Today win rate: `{win_rate_today:.0%}`"
    )
    await send_telegram(msg)


async def send_fill_alert(symbol: str, side: str, qty: float, price: float, fee: float) -> None:
    await send_telegram(
        f"*Fill* `{side.upper()} {qty} {symbol}` @ `{price:,.4f}`\nFee: `${fee:.4f}`"
    )


async def send_circuit_breaker_alert(reason: str, value: float) -> None:
    await send_telegram(f"⚠️ *Circuit Breaker*: `{reason}` (value: `{value:.4f}`)")
