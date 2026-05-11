"""Schema kết quả phân tích thống nhất (Phase 4).

Các engine (stats, psychometrics, timeseries, orchestrator) đều bám layout này
để frontend `ResultSummary` chỉ phải đọc 1 cấu trúc. Các trường tuỳ chọn cho phép
single-engine response (ví dụ chỉ chạy compare_groups_numeric) vẫn hợp lệ.

Dùng trong tài liệu/lint; backend hiện tại trả dict thuần để giữ tốc độ — Pydantic
chủ yếu dùng cho test parity & openapi.
"""

from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field


class AcademicSummary(BaseModel):
    model_config = ConfigDict(extra="allow")
    data_type: str
    methods: list[str] = Field(default_factory=list)
    rationale: str = ""
    assumptions: list[str] = Field(default_factory=list)
    conclusion: str = ""
    warnings: list[str] = Field(default_factory=list)


class ProvenanceRef(BaseModel):
    model_config = ConfigDict(extra="allow")
    manifest_stored_as: str | None = None
    profiling_engine_version: int | None = None
    started_at: str | None = None
    cleaned_at: str | None = None
    finished_at: str | None = None
    random_seed: int | None = None
    psychometrics_engine: str | None = None
    file_sha256: str | None = None
    pip_lock_sha256: str | None = None
    engine_versions: dict[str, str] | None = None


class CleaningBlock(BaseModel):
    model_config = ConfigDict(extra="allow")
    summary: dict[str, Any] = Field(default_factory=dict)
    log: list[dict[str, Any]] = Field(default_factory=list)
    data_clean_preview: list[dict[str, Any]] = Field(default_factory=list)


class UnifiedAnalysisResult(BaseModel):
    """Shape mục tiêu cho `result_summary` trong Job detail.

    Single-engine response (`compare_groups_numeric`, `regression_ols`, …) có thể
    để trống các khối `academic_summary`/`cleaning`/`provenance_ref`; orchestrator
    `comprehensive_analysis` luôn fill đầy đủ.
    """

    model_config = ConfigDict(extra="allow")
    engine: str
    version: int
    spec: dict[str, Any] = Field(default_factory=dict)

    academic_summary: AcademicSummary | None = None
    hypothesis_table: list[dict[str, Any]] = Field(default_factory=list)
    decision_trace: dict[str, Any] = Field(default_factory=dict)
    diagnostics: dict[str, Any] = Field(default_factory=dict)
    evidence: dict[str, Any] = Field(default_factory=dict)
    charts: list[dict[str, Any]] = Field(default_factory=list)
    results: dict[str, Any] = Field(default_factory=dict)
    cleaning: CleaningBlock | None = None
    provenance_ref: ProvenanceRef | None = None


ResultStatus = Literal["succeeded", "failed", "running", "queued"]
