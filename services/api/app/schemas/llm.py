"""Phase 7 — đầu ra LLM (OpenRouter) cho gợi ý giả thuyết; validate Pydantic."""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field


class SuggestedHypothesis(BaseModel):
    hypothesis_id: str = Field(min_length=1, max_length=64)
    statement_vi: str = Field(min_length=1, max_length=2000)
    variables_involved: list[str] = Field(
        default_factory=list,
        description="Tên cột liên quan (không chứa giá trị ô dữ liệu)",
    )
    suggested_test_kind: Literal[
        "compare_groups",
        "regression",
        "correlation",
        "timeseries",
        "categorical",
        "other",
    ] = "other"


class LLMHypothesisResponse(BaseModel):
    """JSON schema cố định mà prompt bắt buộc model trả về."""

    schema_version: Literal[1] = 1
    hypotheses: list[SuggestedHypothesis] = Field(default_factory=list, min_length=1, max_length=15)
    notes: str | None = Field(default=None, max_length=2000)


class HypothesisSuggestionsEnvelope(BaseModel):
    """Payload API sau khi validate / fallback."""

    job_id: str
    source: Literal["openrouter", "openai", "fallback", "disabled_no_key"]
    model: str | None = None
    result: LLMHypothesisResponse
    warning: str | None = None
