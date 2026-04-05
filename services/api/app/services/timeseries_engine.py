"""Phase 6 — chuỗi thời gian: detect cột ngày (đa locale), ETS/ARIMA/Prophet, MAPE/RMSE, JSON chart."""

from __future__ import annotations

import importlib.util
import math
from typing import Any, Literal

import numpy as np
import pandas as pd
from statsmodels.tsa.arima.model import ARIMA
from statsmodels.tsa.exponential_smoothing.ets import ETSModel

from app.schemas.stats import DecisionTrace, DecisionTraceStep, TimeSeriesSpec

MethodUsed = Literal["ets", "arima", "prophet"]


def _prophet_available() -> bool:
    return importlib.util.find_spec("prophet") is not None


def _parse_dates_multi_locale(s: pd.Series) -> tuple[pd.Series, str]:
    """Trả về (datetime_series, strategy_label) với tỷ lệ parse cao nhất."""
    strategies: list[tuple[str, dict[str, Any]]] = [
        ("iso_utc", {"errors": "coerce", "utc": True}),
        ("dayfirst_true", {"errors": "coerce", "utc": True, "dayfirst": True}),
        ("dayfirst_false", {"errors": "coerce", "utc": True, "dayfirst": False}),
    ]
    best = (pd.Series(pd.NaT, index=s.index, dtype="datetime64[ns, UTC]"), "", -1.0)
    for label, kw in strategies:
        t = pd.to_datetime(s, **kw)
        ratio = float(t.notna().mean())
        if ratio > best[2]:
            best = (t, label, ratio)
    try:
        t_m = pd.to_datetime(s, errors="coerce", utc=True, format="mixed")
        ratio_m = float(t_m.notna().mean())
        if ratio_m > best[2]:
            best = (t_m, "mixed", ratio_m)
    except (ValueError, TypeError):
        pass
    return best[0], best[1]


def _date_column_score(s: pd.Series) -> float:
    parsed, _ = _parse_dates_multi_locale(s)
    return float(parsed.notna().mean())


def detect_date_column(df: pd.DataFrame, hint: str | None) -> tuple[str, pd.Series, str]:
    """
    Chọn cột ngày: hint nếu hợp lệ; không thì cột có ≥70% parse được (ưu tiên tỷ lệ cao nhất).
    """
    if hint is not None:
        if hint not in df.columns:
            msg = f"Không có cột ngày '{hint}' trong dữ liệu."
            raise ValueError(msg)
        parsed, strat = _parse_dates_multi_locale(df[hint])
        if parsed.notna().mean() < 0.5:
            msg = f"Cột '{hint}' không parse được đủ dạng ngày (locale / định dạng)."
            raise ValueError(msg)
        return hint, parsed, strat

    best_col: str | None = None
    best_score = 0.0
    for c in df.columns:
        sc = _date_column_score(df[c])
        if sc > best_score:
            best_score = sc
            best_col = str(c)
    if best_col is None or best_score < 0.5:
        msg = "Không tìm thấy cột ngày tự động — hãy chỉ định date_column."
        raise ValueError(msg)
    parsed, strat = _parse_dates_multi_locale(df[best_col])
    return best_col, parsed, strat


def _coerce_numeric_series(s: pd.Series) -> pd.Series:
    if pd.api.types.is_numeric_dtype(s):
        return pd.to_numeric(s, errors="coerce")
    return pd.to_numeric(s.astype(str).str.replace(",", ".", regex=False), errors="coerce")


def _prepare_series(
    df: pd.DataFrame,
    date_col: str,
    dates_parsed: pd.Series,
    value_col: str,
) -> tuple[pd.DatetimeIndex, np.ndarray, list[str]]:
    warnings: list[str] = []
    y_raw = _coerce_numeric_series(df[value_col])
    work = pd.DataFrame({"dt": dates_parsed, "y": y_raw})
    work = work.dropna(subset=["dt", "y"])
    if work.empty:
        msg = "Sau khi parse ngày và ép numeric, không còn quan sát hợp lệ."
        raise ValueError(msg)
    work = work.sort_values("dt")
    work = work.groupby("dt", as_index=True)["y"].mean()
    raw_idx = pd.DatetimeIndex(work.index)
    if raw_idx.tz is not None:
        idx = raw_idx.tz_convert("UTC").tz_localize(None)
    else:
        idx = raw_idx
    y = work.to_numpy(dtype=float)
    if len(y) < 10:
        warnings.append(
            "Chuỗi rất ngắn (n<10): MAPE/RMSE và dự báo chỉ mang tính minh họa.",
        )
    elif len(y) < 30:
        warnings.append(
            "Chuỗi ngắn (n<30): độ tin cậy dự báo thấp; nên thu thập thêm dữ liệu.",
        )
    return idx, y, warnings


def _default_holdout(n: int, requested: int | None) -> int:
    if requested is not None:
        return min(requested, max(1, n - 3))
    return min(max(3, int(round(n * 0.15))), 14, max(1, n - 3))


def _infer_step_timedelta(dates: pd.DatetimeIndex) -> pd.Timedelta:
    """Khoảng cách thời gian trung vị giữa các điểm (pandas 2.x không cast TimedeltaIndex → float)."""
    if len(dates) < 2:
        return pd.Timedelta(days=1)
    # Chuẩn hóa int64 ns để tránh .astype(float) trên TimedeltaIndex (TypeError).
    ns = np.diff(np.asarray(dates.asi8, dtype=np.int64))
    med_ns = float(np.median(ns)) if ns.size else 86_400_000_000_000
    if not math.isfinite(med_ns) or med_ns <= 0:
        return pd.Timedelta(days=1)
    return pd.Timedelta(nanoseconds=int(med_ns))


def _mape_rmse(actual: np.ndarray, pred: np.ndarray) -> tuple[float | None, float]:
    err = actual - pred
    rmse = float(np.sqrt(np.mean(err**2)))
    denom = np.where(np.abs(actual) < 1e-12, np.nan, actual)
    pct = np.abs(err / denom) * 100.0
    pct = pct[np.isfinite(pct)]
    if pct.size == 0:
        return None, rmse
    return float(np.mean(pct)), rmse


def _fit_ets(train: np.ndarray) -> Any:
    model = ETSModel(
        train,
        error="add",
        trend="add",
        seasonal=None,
    )
    return model.fit(disp=False)


def _fit_arima(train: np.ndarray) -> Any:
    model = ARIMA(train, order=(1, 1, 1))
    return model.fit()


def _forecast_statsmodels(fit: Any, steps: int) -> np.ndarray:
    return np.asarray(fit.forecast(steps=steps), dtype=float)


def _fitted_statsmodels(fit: Any, n: int) -> np.ndarray:
    fv = getattr(fit, "fittedvalues", None)
    if fv is None:
        return np.full(n, np.nan)
    arr = np.asarray(fv, dtype=float)
    if arr.size >= n:
        return arr[-n:]
    out = np.full(n, np.nan)
    out[-arr.size :] = arr
    return out


def _run_prophet(
    dates: pd.DatetimeIndex,
    y: np.ndarray,
    horizon: int,
    holdout: int,
) -> tuple[np.ndarray, np.ndarray, np.ndarray, list[pd.Timestamp]]:
    from prophet import Prophet  # type: ignore[import-untyped]

    ds = dates.tz_localize(None) if getattr(dates, "tz", None) else dates
    df_p = pd.DataFrame({"ds": ds, "y": y})
    train_df = df_p.iloc[:-holdout].copy()
    m = Prophet(daily_seasonality=False, weekly_seasonality=False, yearly_seasonality=False)
    m.fit(train_df)
    fc_hold = m.predict(m.make_future_dataframe(periods=holdout, include_history=False))[
        "yhat"
    ].to_numpy()[:holdout]
    m_full = Prophet(daily_seasonality=False, weekly_seasonality=False, yearly_seasonality=False)
    m_full.fit(df_p)
    step = _infer_step_timedelta(dates)
    last_ts = pd.Timestamp(dates[-1])
    if last_ts.tzinfo is not None:
        last_ts = last_ts.tz_convert("UTC").tz_localize(None)
    future_rows = pd.DataFrame({"ds": [last_ts + step * (k + 1) for k in range(horizon)]})
    fc_future = m_full.predict(future_rows)["yhat"].to_numpy()
    fitted_full = m_full.predict(df_p[["ds"]])["yhat"].to_numpy()
    fut_dates = [pd.Timestamp(x) for x in future_rows["ds"].tolist()]
    return fc_hold, fc_future, fitted_full, fut_dates


def _choose_method(spec: TimeSeriesSpec) -> MethodUsed:
    if spec.method == "prophet":
        if not _prophet_available():
            msg = "method=prophet nhưng gói 'prophet' chưa cài (pip install prophet)."
            raise ValueError(msg)
        return "prophet"
    if spec.method == "ets":
        return "ets"
    if spec.method == "arima":
        return "arima"
    return "ets"


def _build_chart(
    dates: pd.DatetimeIndex,
    y: np.ndarray,
    fitted: np.ndarray,
    future_dates: list[pd.Timestamp],
    future_y: np.ndarray,
) -> dict[str, Any]:
    def points(ts: pd.DatetimeIndex | list[pd.Timestamp], vals: np.ndarray) -> list[dict[str, Any]]:
        out: list[dict[str, Any]] = []
        for i, v in enumerate(vals):
            if i >= len(ts):
                break
            if not math.isfinite(float(v)):
                continue
            t = ts[i]
            if hasattr(t, "isoformat"):
                t_str = t.isoformat()  # type: ignore[union-attr]
            else:
                t_str = str(t)
            out.append({"t": t_str, "y": round(float(v), 6)})
        return out

    series: list[dict[str, Any]] = [
        {
            "key": "actual",
            "label": "Thực tế",
            "points": points(dates, y),
        },
    ]
    if np.any(np.isfinite(fitted)):
        series.append(
            {
                "key": "fitted",
                "label": "Khớp mẫu",
                "points": points(dates, fitted),
            },
        )
    if future_dates and len(future_y) > 0:
        series.append(
            {
                "key": "forecast",
                "label": "Dự báo",
                "points": points(future_dates, future_y),
            },
        )
    return {
        "kind": "timeseries_forecast",
        "x_key": "t",
        "y_key": "y",
        "series": series,
    }


def run_timeseries_analysis(df: pd.DataFrame, spec: TimeSeriesSpec) -> dict[str, Any]:
    steps: list[DecisionTraceStep] = []
    date_col, dates_parsed, strat = detect_date_column(df, spec.date_column)
    steps.append(
        DecisionTraceStep(
            step="date_column",
            detail=f"Cột ngày: {date_col} (chiến lược parse: {strat})",
            evidence={"hint": spec.date_column, "strategy": strat},
        ),
    )
    if spec.value_column not in df.columns:
        msg = f"Không có cột giá trị '{spec.value_column}'."
        raise ValueError(msg)

    dates, y, warn_short = _prepare_series(df, date_col, dates_parsed, spec.value_column)
    n = len(y)
    holdout = _default_holdout(n, spec.holdout_periods)
    if holdout >= n - 1:
        holdout = max(2, min(5, n // 2))
    if n - holdout < 4:
        msg = f"Không đủ điểm huấn luyện sau holdout (n={n}, holdout={holdout})."
        raise ValueError(msg)

    method_used: MethodUsed = _choose_method(spec) if spec.method != "auto" else "ets"

    if spec.method == "auto" and method_used == "ets":
        # thử ETS trên tập train; nếu lỗi → ARIMA
        train_try = y[:-holdout]
        try:
            _fit_ets(train_try)
        except Exception:  # noqa: BLE001
            method_used = "arima"

    steps.append(
        DecisionTraceStep(
            step="model",
            detail=f"Mô hình: {method_used}, holdout={holdout}, horizon={spec.horizon}",
            evidence={"n": n, "method": method_used},
        ),
    )

    warnings = list(warn_short)
    train = y[:-holdout]
    test_actual = y[-holdout:]

    mape_v: float | None = None
    rmse_v = float("nan")

    fitted_full = np.full(n, np.nan)
    future_y = np.array([], dtype=float)
    future_dates: list[pd.Timestamp] = []

    if method_used == "prophet":
        fc_hold, future_y, fitted_full, future_dates = _run_prophet(
            dates,
            y,
            spec.horizon,
            holdout,
        )
        mape_v, rmse_v = _mape_rmse(test_actual, fc_hold)
    else:
        try:
            if method_used == "ets":
                fit_tr = _fit_ets(train)
            else:
                fit_tr = _fit_arima(train)
            fc_hold = _forecast_statsmodels(fit_tr, holdout)
            mape_v, rmse_v = _mape_rmse(test_actual, fc_hold)
        except Exception as e:  # noqa: BLE001
            if method_used == "ets":
                warnings.append(f"ETS trên tập train lỗi ({e!s}) — thử ARIMA.")
                method_used = "arima"
                fit_tr = _fit_arima(train)
                fc_hold = _forecast_statsmodels(fit_tr, holdout)
                mape_v, rmse_v = _mape_rmse(test_actual, fc_hold)
            else:
                raise
        # full series fit cho biểu đồ
        try:
            if method_used == "arima":
                fit_full_m = _fit_arima(y)
            else:
                fit_full_m = _fit_ets(y)
            fitted_full = _fitted_statsmodels(fit_full_m, n)
            future_y = _forecast_statsmodels(fit_full_m, spec.horizon)
        except Exception as e2:  # noqa: BLE001
            warnings.append(f"Khớp lại trên toàn chuỗi lỗi ({e2!s}) — chỉ hiển thị metrics holdout.")
            fitted_full = np.full(n, np.nan)
            future_y = np.array([], dtype=float)

    if method_used != "prophet":
        step_td = _infer_step_timedelta(dates)
        last = dates[-1]
        last_ts = pd.Timestamp(last)
        if last_ts.tzinfo is not None:
            last_ts = last_ts.tz_convert("UTC").tz_localize(None)
        future_dates = [last_ts + step_td * (k + 1) for k in range(spec.horizon)]

    if mape_v is not None and mape_v > 50:
        warnings.append("MAPE trên holdout > 50% — mô hình có thể không phù hợp chuỗi này.")
    if not math.isfinite(rmse_v):
        rmse_v = float("nan")

    if mape_v is None and np.any(np.abs(test_actual) < 1e-12):
        warnings.append("MAPE không tính được (giá trị thực tế ~0 trên holdout).")

    chart = _build_chart(dates, y, fitted_full, future_dates, future_y)

    trace = DecisionTrace(
        steps=steps,
        selected_method=method_used,
        parametric_path=None,
        fallback=None,
    )

    metrics: dict[str, Any] = {
        "mape": round(mape_v, 4) if mape_v is not None else None,
        "rmse": round(rmse_v, 6) if math.isfinite(rmse_v) else None,
        "holdout_periods": holdout,
    }

    meta = {
        "date_column": date_col,
        "value_column": spec.value_column,
        "n_obs": n,
        "method_used": method_used,
        "parse_strategy": strat,
        "horizon": spec.horizon,
    }

    return {
        "decision_trace": trace.model_dump(),
        "hypothesis_table": [],
        "diagnostics": {
            "timeseries_meta": meta,
            "timeseries_metrics": metrics,
            "timeseries_warnings": warnings,
        },
        "chart": chart,
        "metrics": metrics,
        "warnings": warnings,
        "meta": meta,
    }
