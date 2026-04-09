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


class RPipelineSpec(BaseModel):
    """Gọi R CLI (Cronbach α, EFA, PLS-SEM có gate). Mỗi phần tử analyses là list gửi thẳng tới R."""

    kind: Literal["r_pipeline"] = "r_pipeline"
    analyses: list[dict[str, Any]] = Field(
        min_length=1,
        description='Ví dụ {"type":"cronbach_alpha","scale_id":"s","items":["x1","x2"]}',
    )


class FullAutoAnalysisSpec(BaseModel):
    """Phân tích tổng quát toàn bộ dữ liệu; ưu tiên R cho khối numeric nếu có Rscript."""

    kind: Literal["full_auto_analysis"] = "full_auto_analysis"
    prefer_r: bool = Field(
        default=True,
        description="Ưu tiên chạy R cho khối numeric nếu Rscript có sẵn",
    )
    max_categorical_pairs: int = Field(default=8, ge=1, le=50)
    max_group_comparisons: int = Field(default=12, ge=1, le=100)


class TimeSeriesSpec(BaseModel):
    """Phase 6 — dự báo chuỗi thời gian (ETS / ARIMA / Prophet tùy chọn), MAPE & RMSE."""

    kind: Literal["timeseries_forecast"] = "timeseries_forecast"
    value_column: str = Field(description="Cột số cần dự báo")
    date_column: str | None = Field(
        default=None,
        description="Cột ngày; null = tự detect (thử dayfirst US/EU + ISO mixed)",
    )
    method: Literal["auto", "ets", "arima", "prophet"] = Field(
        default="auto",
        description="auto: thử ETS rồi ARIMA; prophet nếu cài gói prophet và method/prophet",
    )
    horizon: int = Field(default=7, ge=1, le=366, description="Số bước dự báo tương lai")
    holdout_periods: int | None = Field(
        default=None,
        ge=2,
        description="Số điểm cuối giữ lại để đo MAPE/RMSE; null = tự chọn theo độ dài chuỗi",
    )


AnalyzeRequest = Annotated[
    CompareGroupsNumericSpec
    | RegressionOLSSpec
    | CategoricalAssociationSpec
    | RPipelineSpec
    | FullAutoAnalysisSpec
    | TimeSeriesSpec,
    Field(discriminator="kind"),
]
