"""Tests cho `app.services.data_cleaning.clean_dataframe`."""

from __future__ import annotations

import numpy as np
import pandas as pd

from app.services.data_cleaning import CleaningOptions, clean_dataframe


def test_report_only_keeps_dataframe_intact():
    df = pd.DataFrame(
        {
            "a": [1, 2, 3, None, 5],
            "b": ["x", "y", "x", "y", "x"],
        }
    )
    out, log, summary = clean_dataframe(df, CleaningOptions(missing_policy="report_only"))
    assert len(out) == len(df)
    actions = [e["action"] for e in log]
    assert "missing_value_report" in actions
    assert summary["rows_before"] == 5
    assert summary["rows_after"] == 5


def test_drop_row_removes_na_rows_and_logs_count():
    df = pd.DataFrame({"a": [1.0, np.nan, 3.0], "b": [4.0, 5.0, np.nan]})
    out, log, summary = clean_dataframe(df, CleaningOptions(missing_policy="drop_row"))
    assert len(out) == 1
    drop_actions = [e for e in log if e["action"] == "drop_rows_any_na"]
    assert drop_actions and drop_actions[0]["evidence"]["rows_after"] == 1
    assert summary["rows_after"] == 1


def test_impute_median_fills_numeric_and_mode_categorical():
    df = pd.DataFrame(
        {
            "score": [10.0, 20.0, np.nan, 30.0],
            "grp": ["A", "B", None, "A"],
        }
    )
    out, log, _ = clean_dataframe(df, CleaningOptions(missing_policy="impute_median"))
    assert out["score"].isna().sum() == 0
    assert out["grp"].isna().sum() == 0
    impute_action = next(e for e in log if e["action"] == "impute_missing")
    cols = impute_action["evidence"]["per_column"]
    assert "score" in cols
    assert "grp" in cols


def test_coerce_dtype_object_to_numeric():
    df = pd.DataFrame({"x": ["1", "2", "3", "4", "5"]})
    out, log, _ = clean_dataframe(df, CleaningOptions())
    assert pd.api.types.is_numeric_dtype(out["x"])
    coerce_actions = [e for e in log if e["action"] == "coerce_dtype_numeric"]
    assert coerce_actions
    assert "x" in coerce_actions[0]["evidence"]["columns"]


def test_winsorize_clips_extreme_outliers():
    values = list(range(1, 21)) + [500]  # 500 là outlier mạnh
    df = pd.DataFrame({"v": values})
    out, log, _ = clean_dataframe(
        df,
        CleaningOptions(outlier_policy="winsorize"),
    )
    assert out["v"].max() < 500
    winsorize_actions = [e for e in log if e["action"] == "winsorize_outliers"]
    assert winsorize_actions


def test_drop_columns_high_missing():
    df = pd.DataFrame({"keep": [1, 2, 3, 4], "mostly_na": [None, None, None, 1]})
    out, log, _ = clean_dataframe(
        df,
        CleaningOptions(
            missing_policy="drop_row",
            missing_drop_column_threshold=0.5,
        ),
    )
    assert "mostly_na" not in out.columns
    drop_actions = [e for e in log if e["action"] == "drop_columns_high_missing"]
    assert drop_actions
    assert "mostly_na" in drop_actions[0]["evidence"]["columns"]


def test_disabled_returns_copy_and_empty_log():
    df = pd.DataFrame({"a": [1, 2, 3]})
    out, log, summary = clean_dataframe(df, CleaningOptions(enabled=False))
    assert log == []
    assert summary == {"enabled": False}
    assert out.equals(df)
