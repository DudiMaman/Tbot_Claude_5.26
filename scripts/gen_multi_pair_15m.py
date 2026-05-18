"""
Generate 15m OHLCV synthetic data for 12 crypto pairs using GBM.
Produces 6 months of 15m bars (~17280 bars per pair).

Output: data/synthetic/{SYMBOL}_15m_6m.parquet
"""
from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path

import numpy as np
import pandas as pd


PAIR_CONFIGS = [
    # symbol,       drift_ann, vol_ann, seed, start_price
    ("BTCUSDT",     0.40,      0.70,    42,   30000.0),
    ("ETHUSDT",     0.35,      0.75,    43,   1800.0),
    ("BNBUSDT",     0.30,      0.80,    44,   250.0),
    ("SOLUSDT",     0.50,      0.90,    45,   20.0),
    ("ADAUSDT",     0.25,      0.85,    46,   0.30),
    ("DOGEUSDT",    0.20,      1.00,    47,   0.07),
    ("AVAXUSDT",    0.35,      0.85,    48,   15.0),
    ("LINKUSDT",    0.30,      0.80,    49,   7.0),
    ("MATICUSDT",   0.25,      0.90,    50,   0.80),
    ("DOTUSDT",     0.20,      0.80,    51,   5.0),
    ("XRPUSDT",     0.25,      0.75,    52,   0.40),
    ("LTCUSDT",     0.25,      0.70,    53,   70.0),
]

# 6 months of 15m bars: 6 months * 30 days * 24 hours * 4 bars/hour
N_BARS = 6 * 30 * 24 * 4  # 17280 bars
START_DATE = "2024-01-01"

# dt = 15 minutes as a fraction of a year (crypto: 365 * 24 * 60 minutes)
DT_YEARS = 15 / (365 * 24 * 60)


def generate_pair(
    symbol: str,
    drift_annual: float,
    vol_annual: float,
    seed: int,
    start_price: float,
    n_bars: int = N_BARS,
) -> pd.DataFrame:
    rng = np.random.default_rng(seed)

    dt = DT_YEARS
    mu = drift_annual - 0.5 * vol_annual ** 2
    sigma = vol_annual * np.sqrt(dt)

    # GBM log-returns
    log_returns = rng.normal(mu * dt, sigma, n_bars)

    # Build close price series
    close_prices = start_price * np.exp(np.cumsum(log_returns))

    # Simulate intrabar OHLC from close prices
    noise = sigma * 0.5
    open_prices = close_prices * np.exp(rng.normal(0, noise * 0.3, n_bars))
    high_prices = np.maximum(close_prices, open_prices) * np.exp(np.abs(rng.normal(0, noise, n_bars)))
    low_prices  = np.minimum(close_prices, open_prices) * np.exp(-np.abs(rng.normal(0, noise, n_bars)))

    # Volume: log-normal, correlated with abs(return) for realism
    # Scale base volume per pair's typical market depth
    base_vol = start_price * 10  # rough market-cap-proportional base
    vol_multiplier = 1 + 3 * np.abs(log_returns) / sigma
    volume = base_vol * np.exp(rng.normal(0, 0.5, n_bars)) * vol_multiplier

    start_dt = datetime.fromisoformat(START_DATE).replace(tzinfo=timezone.utc)
    index = pd.date_range(start=start_dt, periods=n_bars, freq="15min", tz="UTC")

    df = pd.DataFrame(
        {
            "open":   open_prices,
            "high":   high_prices,
            "low":    low_prices,
            "close":  close_prices,
            "volume": volume,
        },
        index=index,
    )
    df.index.name = "timestamp"
    return df


def main() -> None:
    out_dir = Path("data/synthetic")
    out_dir.mkdir(parents=True, exist_ok=True)

    print(f"Generating {N_BARS} bars (6 months of 15m data) for {len(PAIR_CONFIGS)} pairs...")
    print(f"Start date: {START_DATE}  |  Output: {out_dir}/\n")

    for symbol, drift, vol, seed, start_price in PAIR_CONFIGS:
        df = generate_pair(symbol, drift, vol, seed, start_price)
        path = out_dir / f"{symbol}_15m_6m.parquet"
        df.to_parquet(path)
        end_price = df["close"].iloc[-1]
        pct_change = (end_price / start_price - 1) * 100
        print(
            f"  {symbol:<12} bars={len(df):>6}  "
            f"start=${start_price:.4g}  end=${end_price:.4g}  "
            f"change={pct_change:+.1f}%  -> {path.name}"
        )

    print(f"\nDone. {len(PAIR_CONFIGS)} files written to {out_dir}/")


if __name__ == "__main__":
    main()
