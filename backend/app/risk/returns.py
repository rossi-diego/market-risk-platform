"""Return-series builders for the VaR/CVaR engine.

Inputs are pandas DataFrames indexed by observation timestamp with one column
per instrument (e.g. `ZS=F`, `ZC=F`, `USDBRL=X`). All arithmetic is float for
speed (VaR is a statistical estimate; Decimal is reserved for the financial
accounting path).
"""

from __future__ import annotations

from typing import Any, Literal, cast

import numpy as np
import pandas as pd


def compute_returns(
    prices_df: pd.DataFrame, kind: Literal["log", "simple"] = "log"
) -> pd.DataFrame:
    """Return period-over-period returns, dropping the first NaN row."""
    if prices_df.empty:
        return prices_df.copy()
    raw: Any = np.log(prices_df / prices_df.shift(1)) if kind == "log" else prices_df.pct_change()
    rets = cast(pd.DataFrame, raw)
    return rets.iloc[1:]


def align_multi_series(series_by_instrument: dict[str, pd.Series]) -> pd.DataFrame:
    """Outer-join series on timestamp, ffill small gaps, drop leading NaNs."""
    if not series_by_instrument:
        return pd.DataFrame()
    df = pd.DataFrame(series_by_instrument)
    df = df.sort_index()
    # Forward-fill up to one business-day gap, no more.
    df = df.ffill(limit=1)
    return df.dropna(how="any")


def rolling_window(df: pd.DataFrame, days: int = 252) -> pd.DataFrame:
    """Tail the latest `days` rows. Raise if we don't have enough history."""
    if len(df) < days:
        raise ValueError(f"insufficient history: need {days} rows, have {len(df)}")
    return df.iloc[-days:]
