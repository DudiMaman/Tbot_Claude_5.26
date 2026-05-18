"""
Generate synthetic OHLCV data using Geometric Brownian Motion.
Produces realistic BTC-like price behavior for offline backtesting.
"""
from __future__ import annotations

import argparse
from datetime import datetime, timezone
from pathlib import Path

import numpy as np
import pandas as pd


def generate_ohlcv(
    start: str,
    end: str,
    timeframe: str = "1h",
    initial_price: float = 16500.0,
    annual_drift: float = 1.50,       # calibrated to match BTC 2023-2024 (~330% over 2 years)
    annual_vol: float = 0.75,         # ~75% annualised volatility (historical BTC)
    seed: int = 137,                  # seed that produces a representative bull run
) -> pd.DataFrame:
    rng = np.random.default_rng(seed)

    tf_hours = {"1m": 1/60, "5m": 5/60, "15m": 15/60, "1h": 1, "4h": 4, "1d": 24}
    hours = tf_hours.get(timeframe, 1)
    dt_years = hours / 8760  # trading hours per year (crypto: all year)

    start_dt = datetime.fromisoformat(start).replace(tzinfo=timezone.utc)
    end_dt = datetime.fromisoformat(end).replace(tzinfo=timezone.utc)
    freq = {"1m": "1min", "5m": "5min", "15m": "15min", "1h": "1h", "4h": "4h", "1d": "1D"}
    index = pd.date_range(start=start_dt, end=end_dt, freq=freq.get(timeframe, "1h"), tz="UTC")
    n = len(index)

    # GBM log-returns
    mu = annual_drift * dt_years
    sigma = annual_vol * np.sqrt(dt_years)
    log_returns = rng.normal(mu - 0.5 * sigma ** 2, sigma, n)

    close_prices = initial_price * np.exp(np.cumsum(log_returns))

    # Simulate O/H/L from close using intrabar noise
    noise = annual_vol * np.sqrt(dt_years) * 0.5
    open_prices = close_prices * np.exp(rng.normal(0, noise * 0.3, n))
    high_prices = np.maximum(close_prices, open_prices) * np.exp(np.abs(rng.normal(0, noise, n)))
    low_prices  = np.minimum(close_prices, open_prices) * np.exp(-np.abs(rng.normal(0, noise, n)))

    # Volume: log-normal, correlated with abs(return) for realism
    base_vol = 500.0  # BTC-equivalent
    vol_multiplier = 1 + 3 * np.abs(log_returns) / sigma
    volume = base_vol * np.exp(rng.normal(0, 0.5, n)) * vol_multiplier

    df = pd.DataFrame({
        "open":   open_prices,
        "high":   high_prices,
        "low":    low_prices,
        "close":  close_prices,
        "volume": volume,
    }, index=index)
    df.index.name = "timestamp"
    return df


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--from", dest="start", default="2023-01-01")
    parser.add_argument("--to", dest="end", default="2024-12-31")
    parser.add_argument("--timeframe", default="1h")
    parser.add_argument("--symbol", default="BTCUSDT")
    parser.add_argument("--output", default="data/synthetic")
    parser.add_argument("--initial-price", type=float, default=16500.0)
    parser.add_argument("--annual-drift", type=float, default=1.50,
                        help="Annual log-return drift (1.50 = 150%% ≈ 2023-2024 BTC bull)")
    parser.add_argument("--annual-vol", type=float, default=0.75)
    parser.add_argument("--seed", type=int, default=137)
    args = parser.parse_args()

    out = Path(args.output)
    out.mkdir(parents=True, exist_ok=True)

    df = generate_ohlcv(
        args.start, args.end, args.timeframe,
        initial_price=args.initial_price,
        annual_drift=args.annual_drift,
        annual_vol=args.annual_vol,
        seed=args.seed,
    )
    path = out / f"{args.symbol}_{args.timeframe}_{args.start}_{args.end}.parquet"
    df.to_parquet(path)
    print(f"Generated {len(df)} bars → {path}")
    print(f"Price range: ${df['close'].min():.0f} – ${df['close'].max():.0f}")
    print(f"Start: ${df['close'].iloc[0]:.0f}  →  End: ${df['close'].iloc[-1]:.0f}")


if __name__ == "__main__":
    main()
