"""Phase 4 — unit tests: 2 nhóm, >2 nhóm, categorical association, OLS + VIF."""

import numpy as np
import pandas as pd

from app.schemas.stats import (
    CategoricalAssociationSpec,
    CompareGroupsNumericSpec,
    RegressionOLSSpec,
)
from app.services.stats_engine import (
    analyze_categorical_association,
    analyze_compare_groups_numeric,
    analyze_regression_ols,
)


def test_two_groups_parametric_path_student_or_welch():
    rng = np.random.default_rng(42)
    g1 = rng.normal(5.0, 1.0, 40)
    g2 = rng.normal(5.8, 1.0, 40)
    df = pd.DataFrame(
        {
            "group": ["A"] * 40 + ["B"] * 40,
            "y": np.concatenate([g1, g2]),
        },
    )
    out = analyze_compare_groups_numeric(
        df,
        CompareGroupsNumericSpec(kind="compare_groups_numeric", outcome="y", group="group"),
    )
    trace = out["decision_trace"]
    method = trace["selected_method"]
    assert method in {"student_t_test", "welch_t_test"}
    assert trace["parametric_path"] is True
    row = out["hypothesis_table"][0]
    assert row["hypothesis_id"] == "H_compare_two_groups"
    assert row["p_value"] is not None
    assert row["effect_size_kind"] == "cohens_d"
    assert row["method"]


def test_two_groups_nonnormal_uses_mann_whitney():
    rng = np.random.default_rng(7)
    g1 = rng.exponential(1.0, 35)
    g2 = rng.exponential(2.5, 35)
    df = pd.DataFrame(
        {
            "group": ["Low"] * 35 + ["High"] * 35,
            "score": np.concatenate([g1, g2]),
        },
    )
    out = analyze_compare_groups_numeric(
        df,
        CompareGroupsNumericSpec(kind="compare_groups_numeric", outcome="score", group="group"),
    )
    assert out["decision_trace"]["selected_method"] == "mann_whitney_u"
    assert out["decision_trace"]["parametric_path"] is False
    row = out["hypothesis_table"][0]
    assert row["effect_size_kind"] == "rank_biserial"
    assert row["p_value"] is not None


def test_three_groups_anova_or_kruskal():
    rng = np.random.default_rng(99)
    df = pd.DataFrame(
        {
            "arm": ["A"] * 30 + ["B"] * 30 + ["C"] * 30,
            "resp": np.concatenate(
                [
                    rng.normal(0.0, 1.0, 30),
                    rng.normal(0.3, 1.0, 30),
                    rng.normal(0.6, 1.0, 30),
                ],
            ),
        },
    )
    out = analyze_compare_groups_numeric(
        df,
        CompareGroupsNumericSpec(kind="compare_groups_numeric", outcome="resp", group="arm"),
    )
    sel = out["decision_trace"]["selected_method"]
    assert sel in {"one_way_anova", "kruskal_wallis"}
    row = out["hypothesis_table"][0]
    assert row["hypothesis_id"] == "H_compare_k_groups"
    if sel == "one_way_anova":
        assert row["effect_size_kind"] == "eta_squared"
    assert row["p_value"] is not None


def test_categorical_association_chi_square():
    df = pd.DataFrame(
        {
            "region": ["N", "N", "N", "S", "S", "S"] * 10,
            "tier": ["P", "Q", "P", "P", "Q", "Q"] * 10,
        },
    )
    out = analyze_categorical_association(
        df,
        CategoricalAssociationSpec(
            kind="categorical_association",
            variable_a="region",
            variable_b="tier",
        ),
    )
    row = out["hypothesis_table"][0]
    assert row["method"].startswith("Chi-square")
    assert row["effect_size_kind"] == "cramers_v"
    assert row["statistic"] is not None
    assert row["p_value"] is not None
    assert "contingency_shape" in out["diagnostics"]


def test_regression_ols_vif_and_qq():
    rng = np.random.default_rng(3)
    n = 80
    x1 = rng.normal(0, 1, n)
    x2 = x1 * 0.85 + rng.normal(0, 0.3, n)
    err = rng.normal(0, 0.5, n)
    y = 2.0 + 1.2 * x1 - 0.4 * x2 + err
    df = pd.DataFrame({"y": y, "x1": x1, "x2": x2})
    out = analyze_regression_ols(
        df,
        RegressionOLSSpec(kind="regression_ols", outcome="y", predictors=["x1", "x2"]),
    )
    ids = {r["hypothesis_id"] for r in out["hypothesis_table"]}
    assert "H_model_f" in ids
    assert "H_coef_x1" in ids
    assert "H_coef_x2" in ids
    vifs = out["diagnostics"]["vif"]
    assert len(vifs) == 2
    assert all("vif" in v for v in vifs)
    qq = out["diagnostics"]["qq_plot"]
    assert qq["theoretical"] and qq["sample"]
    assert "residual" in out["diagnostics"]
