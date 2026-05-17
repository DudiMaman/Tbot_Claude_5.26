#!/usr/bin/env python3
"""
CLI: fetch and cache historical OHLCV data.
Usage:
  python scripts/fetch_history.py --symbol BTCUSDT --timeframe 1h \
      --from 2022-01-01 --to 2024-12-31
"""
from __future__ import annotations

import argparse
import asyncio
import sys
from datetime import date
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from bot.data.historical import HistoricalLoader


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--symbol", required=True)
    parser.add_argument("--timeframe", default="1h")
    parser.add_argument("--from", dest="date_from", required=True)
    parser.add_argument("--to", dest="date_to", required=True)
    parser.add_argument("--market", default="crypto", choices=["crypto", "stocks"])
    return parser.parse_args()


async def main() -> None:
    args = parse_args()
    start = date.fromisoformat(args.date_from)
    end = date.fromisoformat(args.date_to)

    loader = HistoricalLoader()
    print(f"Fetching {args.symbol} {args.timeframe} {start} → {end} ({args.market})...")

    if args.market == "crypto":
        df = await loader.fetch_crypto(args.symbol, args.timeframe, start, end)
    else:
        df = await loader.fetch_stocks(args.symbol, args.timeframe, start, end)

    if df.empty:
        print("No data returned.")
        sys.exit(1)

    print(f"Fetched {len(df)} bars. First: {df.index[0]}  Last: {df.index[-1]}")
    print("Data cached to data_cache/")


if __name__ == "__main__":
    asyncio.run(main())
