"""Phase 7 — gợi ý giả thuyết qua OpenRouter + fallback."""

from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Body, Depends, HTTPException
from pydantic import BaseModel, Field

from app.config import Settings, get_settings
from app.schemas.llm import HypothesisSuggestionsEnvelope
from app.services import job_store
from app.services.llm_hypotheses import profiling_types_from_job_meta, run_hypothesis_suggestions

router = APIRouter(tags=["hypotheses"])


class HypothesisSuggestionsBody(BaseModel):
    force_fallback: bool = Field(
        default=False,
        description="Bỏ qua LLM, chỉ rule-based (kiểm thử / offline)",
    )


@router.post(
    "/jobs/{job_id}/hypothesis-suggestions",
    response_model=HypothesisSuggestionsEnvelope,
)
def post_hypothesis_suggestions(
    job_id: str,
    body: Annotated[HypothesisSuggestionsBody | None, Body()] = None,
    settings: Settings = Depends(get_settings),
) -> HypothesisSuggestionsEnvelope:
    raw = job_store.read_raw_meta(settings, job_id)
    if raw is None:
        raise HTTPException(status_code=404, detail="Job không tồn tại")
    columns = list(raw.get("columns") or [])
    if not columns:
        raise HTTPException(status_code=400, detail="Job chưa có danh sách cột (upload lại?)")
    prof = profiling_types_from_job_meta(raw)
    force_fb = bool(body.force_fallback) if body else False
    result, source, model, warning = run_hypothesis_suggestions(
        settings,
        columns=columns,
        profiling_types=prof,
        force_fallback=force_fb,
        httpx_client=None,
    )
    return HypothesisSuggestionsEnvelope(
        job_id=job_id,
        source=source,
        model=model,
        result=result,
        warning=warning,
    )
