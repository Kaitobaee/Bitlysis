"""Phase 6 — chuỗi thời gian: detect ngày, ETS/ARIMA, chart JSON, cảnh báo chuỗi ngắn."""

from __future__ import annotations

from pathlib import Path

import numpy as np
import pandas as pd
import pytest

from app.schemas.stats import TimeSeriesSpec
from app.services.timeseries_engine import (
    detect_date_column,
    run_timeseries_analysis,
)

FIXTURES = Path(__file__).resolve().parent / "fixtures"


def test_detect_date_column_auto_prefers_high_parse_ratio():
    rng = np.random.default_rng(42)
    dr = pd.date_range("2024-06-01", periods=30, freq="D")
    df = pd.DataFrame(
        {
            "noise": [f"row{i}" for i in range(30)],
            "when": dr.strftime("%d/%m/%Y"),
            "sales": 50 + np.cumsum(rng.normal(0, 0.5, 30)),
        },
    )
    col, _, strat = detect_date_column(df, None)
    assert col == "when"
    assert strat in {"dayfirst_true", "mixed", "iso_utc", "dayfirst_false"}


def test_detect_date_column_explicit_hint():
    dr = pd.date_range("2023-01-01", periods=20, freq="D")
    df = pd.DataFrame({"d": dr.strftime("%Y-%m-%d"), "v": range(20)})
    col, _, _ = detect_date_column(df, "d")
    assert col == "d"


def test_detect_date_column_bad_hint_raises():
    df = pd.DataFrame({"a": [1, 2, 3]})
    with pytest.raises(ValueError, match="Không có cột ngày"):
        detect_date_column(df, "missing")


def test_run_timeseries_from_fixture_eu_dates():
    df = pd.read_csv(FIXTURES / "timeseries_eu.csv")
    spec = TimeSeriesSpec(
        kind="timeseries_forecast",
        value_column="sales",
        date_column="order_date",
        method="auto",
        horizon=5,
        holdout_periods=8,
    )
    out = run_timeseries_analysis(df, spec)
    assert out["chart"]["kind"] == "timeseries_forecast"
    keys = {s["key"] for s in out["chart"]["series"]}
    assert "actual" in keys
    assert out["meta"]["method_used"] in {"ets", "arima"}
    assert out["meta"]["n_obs"] == len(df)
    assert out["metrics"]["holdout_periods"] == 8
    for s in out["chart"]["series"]:
        assert all("t" in p and "y" in p for p in s["points"])


def test_run_timeseries_short_series_warning():
    rng = np.random.default_rng(1)
    dr = pd.date_range("2024-01-01", periods=25, freq="D")
    df = pd.DataFrame(
        {
            "dt": dr.strftime("%Y-%m-%d"),
            "y": 10 + np.cumsum(rng.normal(0, 0.15, 25)),
        },
    )
    spec = TimeSeriesSpec(
        kind="timeseries_forecast",
        value_column="y",
        date_column="dt",
        method="arima",
        horizon=3,
        holdout_periods=5,
    )
    out = run_timeseries_analysis(df, spec)
    assert any("n<30" in w or "ngắn" in w for w in out["warnings"])


def test_run_timeseries_auto_detect_value_column_name():
    rng = np.random.default_rng(7)
    dr = pd.date_range("2024-03-01", periods=35, freq="D")
    df = pd.DataFrame(
        {
            "dt": dr.strftime("%Y-%m-%d"),
            "revenue": np.maximum(1.0, 20 + np.cumsum(rng.normal(0, 1, 35))),
        },
    )
    spec = TimeSeriesSpec(
        kind="timeseries_forecast",
        value_column="revenue",
        date_column=None,
        method="ets",
        horizon=3,
    )
    out = run_timeseries_analysis(df, spec)
    assert out["meta"]["date_column"] == "dt"
    assert out["meta"]["value_column"] == "revenue"
