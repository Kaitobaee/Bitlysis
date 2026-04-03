from __future__ import annotations

from typing import Annotated, Any, Literal

from pydantic import BaseModel, Field


class HypothesisTableRow(BaseModel):
    """Một dòng bảng giả thuyết (chuẩn hóa output thống kê)."""

    hypothesis_id: str
    method: str
    assumptions_checked: list[str] = Field(default_factory=list)
    statistic: float | None = None
    p_value: float | None = None
    effect_size: float | None = Field(
        default=None,
        description="Hiệu ứng chính (Cohen d, rank-biserial, eta², R², …) khi có",
    )
    effect_size_kind: str | None = Field(
        default=None,
        description="Tên hiệu ứng, ví dụ cohens_d, rank_biserial, eta_squared, r_squared",
    )
    ci: list[float] | None = Field(default=None, description="Khoảng tin cậy [low, high] nếu có")
    decision: Literal["reject_h0", "fail_to_reject_h0", "not_applicable"] = "not_applicable"
    warnings: list[str] = Field(default_factory=list)


class DecisionTraceStep(BaseModel):
    """Một bước trong cây quyết định chọn test."""

    step: str
    detail: str
    evidence: dict[str, Any] = Field(default_factory=dict)


class DecisionTrace(BaseModel):
    """Vì sao chọn test (normality + homogeneity + cỡ mẫu + hạ cấp nếu cần)."""

    steps: list[DecisionTraceStep] = Field(default_factory=list)
    selected_method: str = ""
    parametric_path: bool | None = None
    fallback: str | None = Field(
        default=None,
        description="Lý do hạ cấp Mann-Whitney / Kruskal nếu có",
    )


class CompareGroupsNumericSpec(BaseModel):
    kind: Literal["compare_groups_numeric"] = "compare_groups_numeric"
    outcome: str
    group: str


class RegressionOLSSpec(BaseModel):
    kind: Literal["regression_ols"] = "regression_ols"
    outcome: str
    predictors: list[str] = Field(min_length=1)


class CategoricalAssociationSpec(BaseModel):
    kind: Literal["categorical_association"] = "categorical_association"
    variable_a: str
    variable_b: str


AnalyzeRequest = Annotated[
    CompareGroupsNumericSpec | RegressionOLSSpec | CategoricalAssociationSpec,
    Field(discriminator="kind"),
]
