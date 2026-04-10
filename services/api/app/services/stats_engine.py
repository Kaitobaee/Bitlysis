"""Phase 4 — thống kê Python: decision tree, diagnostics, bảng hypothesis chuẩn hóa."""

from __future__ import annotations

import math
from typing import Any, Literal

import numpy as np
import pandas as pd
from scipy import stats as sps
from statsmodels.regression.linear_model import OLS
from statsmodels.stats.diagnostic import het_breuschpagan
from statsmodels.stats.outliers_influence import variance_inflation_factor

from app.schemas.stats import (
    CategoricalAssociationSpec,
    CompareGroupsNumericSpec,
    DecisionTrace,
    DecisionTraceStep,
    HypothesisTableRow,
    RegressionOLSSpec,
)


def build_basic_analysis(df: pd.DataFrame) -> dict[str, Any]:
    """Các output cơ bản luôn có nếu dữ liệu đủ điều kiện."""
    out: dict[str, Any] = {
        "descriptive_stats": [],
        "missing_values": [],
        "outliers": [],
        "correlation_matrix": {},
    }

    if df.empty:
        return out

    numeric_cols = df.select_dtypes(include=[np.number]).columns.tolist()
    numeric_series: dict[str, pd.Series] = {}

    for col in df.columns.tolist():
        s_num = pd.to_numeric(df[col], errors="coerce")
        valid = int(s_num.notna().sum())
        ratio = valid / max(int(len(df)), 1)
        # Nhận diện cột số kể cả khi pandas đọc thành object (CSV/Excel hỗn hợp).
        if valid > 0 and (col in numeric_cols or ratio >= 0.8):
            numeric_series[col] = s_num

    numeric_names = list(numeric_series.keys())

    # Descriptive statistics
    for col in numeric_names:
        s = numeric_series[col]
        if s.notna().sum() == 0:
            continue
        out["descriptive_stats"].append(
            {
                "column": col,
                "count": int(s.notna().sum()),
                "mean": float(s.mean()),
                "std": float(s.std(ddof=1)) if s.notna().sum() > 1 else None,
                "min": float(s.min()),
                "max": float(s.max()),
                "skewness": float(s.skew()) if s.notna().sum() > 2 else None,
                "kurtosis": float(s.kurt()) if s.notna().sum() > 3 else None,
            },
        )

    # Missing values
    n = max(int(len(df)), 1)
    for col in df.columns.tolist():
        miss = int(df[col].isna().sum())
        out["missing_values"].append(
            {
                "column": str(col),
                "missing_count": miss,
                "missing_pct": float(miss / n),
            },
        )

    # Outlier table (IQR rule)
    for col in numeric_names:
        s = numeric_series[col].dropna()
        if s.shape[0] < 4:
            continue
        q1 = float(s.quantile(0.25))
        q3 = float(s.quantile(0.75))
        iqr = q3 - q1
        if iqr <= 0:
            outlier_count = 0
        else:
            lo = q1 - 1.5 * iqr
            hi = q3 + 1.5 * iqr
            outlier_count = int(((s < lo) | (s > hi)).sum())
        out["outliers"].append(
            {
                "column": col,
                "iqr": iqr,
                "outlier_count": outlier_count,
                "outlier_pct": float(outlier_count / max(int(s.shape[0]), 1)),
            },
        )

    # Correlation matrix
    if len(numeric_names) >= 2:
        corr_df = pd.DataFrame({k: numeric_series[k] for k in numeric_names})
        corr = corr_df.corr(numeric_only=True)
        out["correlation_matrix"] = {
            str(r): {str(c): (None if pd.isna(v) else float(v)) for c, v in vals.items()}
            for r, vals in corr.to_dict(orient="index").items()
        }

    return out


def _decision(
    p: float | None,
    alpha: float = 0.05,
) -> Literal["reject_h0", "fail_to_reject_h0", "not_applicable"]:
    if p is None:
        return "not_applicable"
    return "reject_h0" if p < alpha else "fail_to_reject_h0"


def _normality_step(
    values: np.ndarray,
    label: str,
) -> tuple[bool, dict[str, Any], list[str]]:
    """Shapiro nếu nhỏ; n lớn → CLT cho so sánh nhóm."""
    warnings: list[str] = []
    n = int(values.shape[0])
    if n < 3:
        return False, {"n": n, "reason": "too_few_for_normality"}, warnings
    if n > 5000:
        warnings.append(
            f"{label}: n>5000 — bỏ qua Shapiro, dựa vào CLT cho so sánh nhóm.",
        )
        return True, {"n": n, "test": "skipped_large_n", "assumed_normal_clt": True}, warnings
    stat, p = sps.shapiro(values)
    ok = bool(p > 0.05)
    return ok, {"n": n, "test": "shapiro", "statistic": float(stat), "p_value": float(p)}, warnings


def _cohens_d(x: np.ndarray, y: np.ndarray) -> float:
    n1, n2 = len(x), len(y)
    if n1 < 2 or n2 < 2:
        return 0.0
    v1, v2 = np.var(x, ddof=1), np.var(y, ddof=1)
    pooled = math.sqrt(((n1 - 1) * v1 + (n2 - 1) * v2) / max(n1 + n2 - 2, 1))
    if pooled == 0:
        return 0.0
    return float((np.mean(x) - np.mean(y)) / pooled)


def _mean_diff_ci(
    x: np.ndarray,
    y: np.ndarray,
    equal_var: bool,
    alpha: float = 0.05,
) -> tuple[float, float] | None:
    m1, m2 = float(np.mean(x)), float(np.mean(y))
    n1, n2 = len(x), len(y)
    v1, v2 = float(np.var(x, ddof=1)), float(np.var(y, ddof=1))
    if n1 < 2 or n2 < 2:
        return None
    if equal_var:
        pooled_var = ((n1 - 1) * v1 + (n2 - 1) * v2) / max(n1 + n2 - 2, 1)
        se = math.sqrt(pooled_var * (1 / n1 + 1 / n2))
        df = n1 + n2 - 2
    else:
        se = math.sqrt(v1 / n1 + v2 / n2)
        df_num = (v1 / n1 + v2 / n2) ** 2
        df_den = (v1 / n1) ** 2 / max(n1 - 1, 1) + (v2 / n2) ** 2 / max(n2 - 1, 1)
        df = max(df_num / df_den if df_den > 0 else 1.0, 1.0)
    tc = float(sps.t.ppf(1 - alpha / 2, df))
    diff = m1 - m2
    return diff - tc * se, diff + tc * se


def _mann_whitney_effect_rbs(u_stat: float, n1: int, n2: int) -> float:
    if n1 <= 0 or n2 <= 0:
        return 0.0
    return float(1.0 - (2.0 * u_stat) / (n1 * n2))


def _eta_squared_oneway(f_stat: float, df_between: int, df_within: int) -> float:
    if f_stat <= 0 or df_within <= 0:
        return 0.0
    return float((f_stat * df_between) / (f_stat * df_between + df_within))


def analyze_compare_groups_numeric(
    df: pd.DataFrame,
    spec: CompareGroupsNumericSpec,
    *,
    alpha: float = 0.05,
) -> dict[str, Any]:
    outcome, group = spec.outcome, spec.group
    if outcome not in df.columns or group not in df.columns:
        msg = f"Missing columns: need {outcome!r}, {group!r}"
        raise ValueError(msg)

    work = df[[outcome, group]].copy()
    work[outcome] = pd.to_numeric(work[outcome], errors="coerce")
    work = work.dropna()
    if len(work) < 3:
        raise ValueError("Không đủ quan sát hợp lệ sau khi loại NA.")

    groups = [g for g, sub in work.groupby(group, observed=True) if len(sub) >= 1]
    n_groups = len(groups)
    if n_groups < 2:
        raise ValueError("Cần ít nhất 2 nhóm để so sánh.")

    steps: list[DecisionTraceStep] = []
    trace_warnings: list[str] = []
    hypothesis_rows: list[dict[str, Any]] = []

    sub_arrays = [work.loc[work[group] == g, outcome].to_numpy(dtype=float) for g in groups]
    ns = [len(a) for a in sub_arrays]
    min_n = min(ns)
    steps.append(
        DecisionTraceStep(
            step="sample_size",
            detail="Cỡ mẫu mỗi nhóm trước khi chọn parametric vs robust.",
            evidence={"groups": [str(g) for g in groups], "n_per_group": dict(zip(groups, ns))},
        ),
    )

    if n_groups == 2:
        g1, g2 = sub_arrays[0], sub_arrays[1]
        lbl1, lbl2 = str(groups[0]), str(groups[1])
        force_np = min_n < 3
        if force_np:
            steps.append(
                DecisionTraceStep(
                    step="sample_size_gate",
                    detail="min(n) < 3 → không dùng t-test; Mann-Whitney U.",
                    evidence={"min_n": min_n},
                ),
            )

        norm_ok: list[bool] = []
        for arr, lbl in ((g1, lbl1), (g2, lbl2)):
            ok, ev, w = _normality_step(arr, lbl)
            norm_ok.append(ok)
            trace_warnings.extend(w)
            steps.append(
                DecisionTraceStep(
                    step="normality",
                    detail=f"Normality (Shapiro / CLT) cho nhóm {lbl}.",
                    evidence={"group": lbl, **ev, "passed_for_parametric": ok},
                ),
            )

        lev_stat, lev_p = sps.levene(g1, g2, center="median")
        lev_ok = bool(lev_p > alpha)
        steps.append(
            DecisionTraceStep(
                step="homogeneity_of_variance",
                detail="Levene (median) giữa hai nhóm.",
                evidence={"statistic": float(lev_stat), "p_value": float(lev_p), "passed": lev_ok},
            ),
        )

        fallback: str | None = None
        if force_np:
            fallback = "Cỡ mẫu quá nhỏ cho t-test ổn định."
        elif not all(norm_ok):
            fallback = "Normality không đủ → Mann-Whitney."
        elif not lev_ok:
            fallback = "Phương sai không đồng nhất → Welch t-test."

        assumptions_base = ["independent_samples", "ordinal_or_continuous_outcome"]
        row: HypothesisTableRow

        if force_np or not all(norm_ok):
            res = sps.mannwhitneyu(g1, g2, alternative="two-sided")
            u_stat = float(res.statistic)
            p_val = float(res.pvalue)
            es = _mann_whitney_effect_rbs(u_stat, len(g1), len(g2))
            row = HypothesisTableRow(
                hypothesis_id="H_compare_two_groups",
                method="Mann-Whitney U (hai mẫu độc lập)",
                assumptions_checked=assumptions_base
                + (["nonparametric_small_n"] if force_np else ["nonparametric_normality_failed"]),
                statistic=u_stat,
                p_value=p_val,
                effect_size=es,
                effect_size_kind="rank_biserial",
                ci=None,
                decision=_decision(p_val, alpha),
                warnings=trace_warnings.copy(),
            )
            selected = "mann_whitney_u"
            parametric_path = False
            trace_fb = fallback
        elif all(norm_ok) and not lev_ok:
            t_res = sps.ttest_ind(g1, g2, equal_var=False)
            t_stat = float(t_res.statistic)
            p_val = float(t_res.pvalue)
            es = _cohens_d(g1, g2)
            ci = _mean_diff_ci(g1, g2, equal_var=False, alpha=alpha)
            row = HypothesisTableRow(
                hypothesis_id="H_compare_two_groups",
                method="Welch t-test",
                assumptions_checked=assumptions_base
                + ["normality_per_group", "welch_variance_unequal"],
                statistic=t_stat,
                p_value=p_val,
                effect_size=es,
                effect_size_kind="cohens_d",
                ci=list(ci) if ci else None,
                decision=_decision(p_val, alpha),
                warnings=trace_warnings
                + ["Levene p≤0.05 — dùng Welch thay Student pooled."],
            )
            selected = "welch_t_test"
            parametric_path = True
            trace_fb = fallback
        else:
            t_res = sps.ttest_ind(g1, g2, equal_var=True)
            t_stat = float(t_res.statistic)
            p_val = float(t_res.pvalue)
            es = _cohens_d(g1, g2)
            ci = _mean_diff_ci(g1, g2, equal_var=True, alpha=alpha)
            row = HypothesisTableRow(
                hypothesis_id="H_compare_two_groups",
                method="Student t-test (pooled variance)",
                assumptions_checked=assumptions_base
                + ["normality_per_group", "homogeneity_levene"],
                statistic=t_stat,
                p_value=p_val,
                effect_size=es,
                effect_size_kind="cohens_d",
                ci=list(ci) if ci else None,
                decision=_decision(p_val, alpha),
                warnings=trace_warnings.copy(),
            )
            selected = "student_t_test"
            parametric_path = True
            trace_fb = None

        hypothesis_rows.append(row.model_dump())
        trace = DecisionTrace(
            steps=steps,
            selected_method=selected,
            parametric_path=parametric_path,
            fallback=trace_fb,
        )
        return {
            "decision_trace": trace.model_dump(),
            "hypothesis_table": hypothesis_rows,
            "diagnostics": {"alpha": alpha, "n_groups": 2},
        }

    norm_flags: list[bool] = []
    for arr, lbl in zip(sub_arrays, [str(g) for g in groups], strict=True):
        ok, ev, w = _normality_step(arr, lbl)
        norm_flags.append(ok)
        trace_warnings.extend(w)
        steps.append(
            DecisionTraceStep(
                step="normality",
                detail=f"Normality cho nhóm {lbl}.",
                evidence={"group": lbl, **ev, "passed_for_parametric": ok},
            ),
        )

    lev_stat, lev_p = sps.levene(*sub_arrays, center="median")
    lev_ok = bool(lev_p > alpha)
    steps.append(
        DecisionTraceStep(
            step="homogeneity_of_variance",
            detail="Levene trên mọi nhóm.",
            evidence={"statistic": float(lev_stat), "p_value": float(lev_p), "passed": lev_ok},
        ),
    )

    all_normal = all(norm_flags)
    use_anova = all(len(a) >= 2 for a in sub_arrays) and all_normal and lev_ok
    fallback_kw = None if use_anova else "Normality/homogeneity không đủ → Kruskal-Wallis."

    if use_anova:
        f_res = sps.f_oneway(*sub_arrays)
        f_stat = float(f_res.statistic)
        p_val = float(f_res.pvalue)
        df_bw = n_groups - 1
        df_wi = sum(len(a) - 1 for a in sub_arrays)
        eta = _eta_squared_oneway(f_stat, df_bw, df_wi)
        hypothesis_rows.append(
            HypothesisTableRow(
                hypothesis_id="H_compare_k_groups",
                method="One-way ANOVA",
                assumptions_checked=[
                    "normality_per_group",
                    "homogeneity_levene",
                    "independent_groups",
                ],
                statistic=f_stat,
                p_value=p_val,
                effect_size=eta,
                effect_size_kind="eta_squared",
                ci=None,
                decision=_decision(p_val, alpha),
                warnings=trace_warnings.copy(),
            ).model_dump(),
        )
        trace = DecisionTrace(
            steps=steps,
            selected_method="one_way_anova",
            parametric_path=True,
            fallback=None,
        )
    else:
        kw = sps.kruskal(*sub_arrays)
        h_stat = float(kw.statistic)
        p_val = float(kw.pvalue)
        hypothesis_rows.append(
            HypothesisTableRow(
                hypothesis_id="H_compare_k_groups",
                method="Kruskal-Wallis",
                assumptions_checked=["independent_groups", "ordinal_or_continuous_outcome"],
                statistic=h_stat,
                p_value=p_val,
                effect_size=None,
                effect_size_kind=None,
                ci=None,
                decision=_decision(p_val, alpha),
                warnings=trace_warnings + ([fallback_kw] if fallback_kw else []),
            ).model_dump(),
        )
        trace = DecisionTrace(
            steps=steps,
            selected_method="kruskal_wallis",
            parametric_path=False,
            fallback=fallback_kw,
        )

    return {
        "decision_trace": trace.model_dump(),
        "hypothesis_table": hypothesis_rows,
        "diagnostics": {"alpha": alpha, "n_groups": n_groups},
    }


def analyze_categorical_association(
    df: pd.DataFrame,
    spec: CategoricalAssociationSpec,
    *,
    alpha: float = 0.05,
) -> dict[str, Any]:
    a, b = spec.variable_a, spec.variable_b
    if a not in df.columns or b not in df.columns:
        msg = f"Missing columns: need {a!r}, {b!r}"
        raise ValueError(msg)
    work = df[[a, b]].astype("string").dropna()
    if len(work) < 4:
        raise ValueError("Không đủ quan sát cho bảng contingency.")

    steps = [
        DecisionTraceStep(
            step="categorical_association",
            detail="Hai biến hạng mục → Chi-square độc lập; Cramér V làm hiệu ứng.",
            evidence={"variable_a": a, "variable_b": b, "n": len(work)},
        ),
    ]

    ct = pd.crosstab(work[a], work[b])
    chi2, p_val, dof, expected = sps.chi2_contingency(ct)
    exp_flat = expected.flatten()
    low_exp = int(np.sum(exp_flat < 5))
    warn: list[str] = []
    if low_exp:
        warn.append(f"{low_exp} ô có kỳ vọng < 5 — p-value chi-square có thể lệch.")

    n = ct.values.sum()
    cramers_v = (
        math.sqrt(chi2 / (n * (min(ct.shape) - 1))) if n > 0 and min(ct.shape) > 1 else None
    )

    hypothesis_rows = [
        HypothesisTableRow(
            hypothesis_id="H_independence",
            method="Chi-square test of independence",
            assumptions_checked=["independent_observations", "expected_frequencies"],
            statistic=float(chi2),
            p_value=float(p_val),
            effect_size=float(cramers_v) if cramers_v is not None else None,
            effect_size_kind="cramers_v",
            ci=None,
            decision=_decision(float(p_val), alpha),
            warnings=warn,
        ).model_dump(),
    ]

    trace = DecisionTrace(
        steps=steps,
        selected_method="chi2_independence",
        parametric_path=False,
        fallback=None,
    )

    row_labels = [str(x) for x in ct.index.tolist()]
    series = []
    for col in ct.columns.tolist():
        values = [int(v) for v in ct[col].to_list()]
        series.append({
            "key": str(col),
            "label": str(col),
            "values": values,
        })

    chart = {
        "kind": "categorical_association",
        "x_key": a,
        "y_key": "count",
        "x_labels": row_labels,
        "series": series,
    }

    return {
        "decision_trace": trace.model_dump(),
        "hypothesis_table": hypothesis_rows,
        "diagnostics": {
            "alpha": alpha,
            "contingency_shape": list(ct.shape),
            "degrees_of_freedom": int(dof),
            "low_expected_count_cells": low_exp,
        },
        "chart": chart,
    }


def analyze_regression_ols(
    df: pd.DataFrame,
    spec: RegressionOLSSpec,
    *,
    alpha: float = 0.05,
    max_qq_points: int = 40,
) -> dict[str, Any]:
    y_col = spec.outcome
    preds = list(spec.predictors)
    cols = [y_col, *preds]
    for c in cols:
        if c not in df.columns:
            msg = f"Missing column: {c!r}"
            raise ValueError(msg)

    work = df[cols].apply(pd.to_numeric, errors="coerce").dropna()
    if len(work) < len(preds) + 3:
        raise ValueError("Không đủ quan sát cho OLS.")

    y = work[y_col].to_numpy(dtype=float)
    X_raw = work[preds]
    X = np.column_stack([np.ones(len(work)), X_raw.to_numpy(dtype=float)])

    steps: list[DecisionTraceStep] = [
        DecisionTraceStep(
            step="regression_setup",
            detail="OLS: kiểm tra residual / QQ (phạm vi hẹp), VIF khi đa biến.",
            evidence={"n": len(work), "p_predictors": len(preds)},
        ),
    ]

    model = OLS(y, X).fit()
    f_stat = float(model.fvalue) if model.fvalue is not None else float("nan")
    f_p = float(model.f_pvalue) if model.f_pvalue is not None else None

    hypothesis_rows: list[dict[str, Any]] = [
        HypothesisTableRow(
            hypothesis_id="H_model_f",
            method="OLS F-test (global)",
            assumptions_checked=["linearity", "independent_errors"],
            statistic=f_stat,
            p_value=f_p,
            effect_size=float(model.rsquared),
            effect_size_kind="r_squared",
            ci=None,
            decision=_decision(f_p, alpha),
            warnings=[],
        ).model_dump(),
    ]

    pred_names = ["const", *preds]
    ci_mat = np.asarray(model.conf_int(alpha=alpha), dtype=float)
    for i, name in enumerate(pred_names):
        if name == "const":
            continue
        pv = model.pvalues[i]
        hypothesis_rows.append(
            HypothesisTableRow(
                hypothesis_id=f"H_coef_{name}",
                method=f"OLS t-test for {name}",
                assumptions_checked=["linearity", "exogeneity_weak"],
                statistic=float(model.tvalues[i]),
                p_value=float(pv),
                effect_size=float(model.params[i]),
                effect_size_kind="partial_slope",
                ci=[float(ci_mat[i, 0]), float(ci_mat[i, 1])],
                decision=_decision(float(pv), alpha),
                warnings=[],
            ).model_dump(),
        )

    resid = np.asarray(model.resid, dtype=float)
    fitted = np.asarray(model.fittedvalues, dtype=float)
    resid_diag: dict[str, Any] = {}
    qq_pairs: dict[str, list[float]] = {"theoretical": [], "sample": []}
    if len(resid) <= 5000:
        sh_stat, sh_p = sps.shapiro(resid)
        resid_diag["residual_shapiro_statistic"] = float(sh_stat)
        resid_diag["residual_shapiro_p"] = float(sh_p)
        steps.append(
            DecisionTraceStep(
                step="residual_normality",
                detail="Shapiro trên residual (n≤5000).",
                evidence={
                    "statistic": float(sh_stat),
                    "p_value": float(sh_p),
                    "passed_for_gaussian_residuals": bool(sh_p > alpha),
                },
            ),
        )
    else:
        steps.append(
            DecisionTraceStep(
                step="residual_normality",
                detail="n>5000 — bỏ qua Shapiro residual.",
                evidence={"n_residuals": len(resid)},
            ),
        )

    try:
        bp_stat, bp_p, _, _ = het_breuschpagan(resid, X)
        resid_diag["breusch_pagan_statistic"] = float(bp_stat)
        resid_diag["breusch_pagan_p"] = float(bp_p)
        steps.append(
            DecisionTraceStep(
                step="heteroskedasticity",
                detail="Breusch-Pagan trên residual.",
                evidence={"statistic": float(bp_stat), "p_value": float(bp_p)},
            ),
        )
    except Exception:  # noqa: BLE001
        resid_diag["breusch_pagan"] = "unavailable"

    osm, osr = sps.probplot(resid, dist="norm", fit=False)
    theo = np.asarray(osm, dtype=float).ravel()
    samp = np.asarray(osr, dtype=float).ravel()
    nq = int(theo.size)
    k = min(max_qq_points, nq)
    if k > 0:
        idx = np.linspace(0, nq - 1, num=k, dtype=int)
        qq_pairs["theoretical"] = [float(theo[j]) for j in idx]
        qq_pairs["sample"] = [float(samp[j]) for j in idx]

    vif_rows: list[dict[str, Any]] = []
    vif_warn: list[str] = []
    if len(preds) > 1:
        Xdf = X_raw.astype(float).copy()
        for j, col in enumerate(preds):
            try:
                v = float(variance_inflation_factor(Xdf.to_numpy(dtype=float), j))
            except Exception:  # noqa: BLE001
                v = float("nan")
            vif_rows.append({"predictor": col, "vif": v})
            if not math.isnan(v) and v > 10:
                vif_warn.append(f"VIF>10 cho {col} — đa cộng tuyến mạnh.")
    else:
        vif_rows.append({"predictor": preds[0], "vif": 1.0})

    trace = DecisionTrace(
        steps=steps,
        selected_method="ols",
        parametric_path=True,
        fallback=None,
    )

    out_diag: dict[str, Any] = {
        "alpha": alpha,
        "vif": vif_rows,
        "residual": resid_diag,
        "qq_plot": qq_pairs,
        "fitted_range": [float(np.min(fitted)), float(np.max(fitted))],
    }
    if vif_warn:
        out_diag["multicollinearity_warnings"] = vif_warn

    return {
        "decision_trace": trace.model_dump(),
        "hypothesis_table": hypothesis_rows,
        "diagnostics": out_diag,
    }


def run_stats_analysis(
    df: pd.DataFrame,
    spec: CompareGroupsNumericSpec | RegressionOLSSpec | CategoricalAssociationSpec,
    *,
    alpha: float = 0.05,
) -> dict[str, Any]:
    if isinstance(spec, CompareGroupsNumericSpec):
        return analyze_compare_groups_numeric(df, spec, alpha=alpha)
    if isinstance(spec, RegressionOLSSpec):
        return analyze_regression_ols(df, spec, alpha=alpha)
    if isinstance(spec, CategoricalAssociationSpec):
        return analyze_categorical_association(df, spec, alpha=alpha)
    msg = f"Unknown spec: {type(spec)}"
    raise TypeError(msg)
