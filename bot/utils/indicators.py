"""
Pure pandas/numpy technical indicator implementations.
No external TA library dependency — works on any Python 3.11+ environment.
"""
from __future__ import annotations

import numpy as np
import pandas as pd


def ema(series: pd.Series, length: int) -> pd.Series:
    return series.ewm(span=length, adjust=False).mean()


def sma(series: pd.Series, length: int) -> pd.Series:
    return series.rolling(window=length).mean()


def rsi(series: pd.Series, length: int = 14) -> pd.Series:
    delta = series.diff()
    gain = delta.clip(lower=0)
    loss = -delta.clip(upper=0)
    avg_gain = gain.ewm(com=length - 1, adjust=False).mean()
    avg_loss = loss.ewm(com=length - 1, adjust=False).mean()
    rs = avg_gain / avg_loss.replace(0, np.nan)
    return 100 - (100 / (1 + rs))


def bollinger_bands(series: pd.Series, length: int = 20, std: float = 2.0) -> pd.DataFrame:
    mid = series.rolling(window=length).mean()
    sigma = series.rolling(window=length).std(ddof=0)
    return pd.DataFrame({
        "bb_lower": mid - std * sigma,
        "bb_mid": mid,
        "bb_upper": mid + std * sigma,
    }, index=series.index)


def atr(high: pd.Series, low: pd.Series, close: pd.Series, length: int = 14) -> pd.Series:
    prev_close = close.shift(1)
    tr = pd.concat([
        high - low,
        (high - prev_close).abs(),
        (low - prev_close).abs(),
    ], axis=1).max(axis=1)
    return tr.ewm(com=length - 1, adjust=False).mean()


def adx(high: pd.Series, low: pd.Series, close: pd.Series, length: int = 14) -> pd.Series:
    """Average Directional Index."""
    up_move = high.diff()
    down_move = -low.diff()

    plus_dm = np.where((up_move > down_move) & (up_move > 0), up_move, 0.0)
    minus_dm = np.where((down_move > up_move) & (down_move > 0), down_move, 0.0)

    tr_val = atr(high, low, close, length)
    plus_di = pd.Series(plus_dm, index=high.index).ewm(com=length - 1, adjust=False).mean() / tr_val * 100
    minus_di = pd.Series(minus_dm, index=high.index).ewm(com=length - 1, adjust=False).mean() / tr_val * 100

    dx = ((plus_di - minus_di).abs() / (plus_di + minus_di).replace(0, np.nan)) * 100
    adx_val = dx.ewm(com=length - 1, adjust=False).mean()
    return adx_val
