"""Unit tests for risk/returns.py."""

from __future__ import annotations

import numpy as np
import pandas as pd
import pytest

from app.risk.returns import align_multi_series, compute_returns, rolling_window


def _price_df() -> pd.DataFrame:
    idx = pd.date_range(end="2026-04-15", periods=5, freq="B")
    return pd.DataFrame(
        {"ZS=F": [100.0, 101.0, 102.0, 101.5, 103.0]},
        index=idx,
    )


def test_compute_returns_log() -> None:
    df = _price_df()
    rets = compute_returns(df, kind="log")
    # First row of original is dropped; 4 returns remain.
    assert len(rets) == 4
    expected = float(np.log(101.0 / 100.0))
    assert abs(float(rets.iloc[0]["ZS=F"]) - expected) < 1e-9


def test_compute_returns_simple() -> None:
    df = _price_df()
    rets = compute_returns(df, kind="simple")
    assert len(rets) == 4
    assert abs(float(rets.iloc[0]["ZS=F"]) - 0.01) < 1e-9


def test_compute_returns_empty_is_empty() -> None:
    out = compute_returns(pd.DataFrame())
    assert out.empty


def test_align_multi_series_inner_join_semantics() -> None:
    idx1 = pd.date_range(end="2026-04-15", periods=5, freq="B")
    idx2 = pd.date_range(end="2026-04-16", periods=5, freq="B")
    s1 = pd.Series([1.0, 2.0, 3.0, 4.0, 5.0], index=idx1)
    s2 = pd.Series([10.0, 20.0, 30.0, 40.0, 50.0], index=idx2)
    merged = align_multi_series({"A": s1, "B": s2})
    # Both series must have values (after forward-fill) — overlap region only.
    assert not merged.empty
    assert list(merged.columns) == ["A", "B"]


def test_align_multi_series_empty() -> None:
    assert align_multi_series({}).empty


def test_rolling_window_tail() -> None:
    idx = pd.date_range(end="2026-04-15", periods=10, freq="B")
    df = pd.DataFrame({"a": range(10)}, index=idx)
    out = rolling_window(df, days=5)
    assert len(out) == 5
    assert out.iloc[0]["a"] == 5


def test_rolling_window_insufficient_raises() -> None:
    idx = pd.date_range(end="2026-04-15", periods=3, freq="B")
    df = pd.DataFrame({"a": [1, 2, 3]}, index=idx)
    with pytest.raises(ValueError, match="insufficient history"):
        rolling_window(df, days=5)
