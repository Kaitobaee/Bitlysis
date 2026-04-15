from __future__ import annotations

from fastapi import APIRouter, HTTPException

from app.config import get_settings
from app.schemas.web_analysis import WebAnalysisChatRequest, WebAnalysisChatResponse, WebAnalyzeRequest, WebAnalyzeResponse
from app.services.web_analyzer import analyze_url_or_text, answer_web_analysis_question

router = APIRouter(tags=["web-analyze"])


@router.post("/web/analyze", response_model=WebAnalyzeResponse)
def analyze_web_content(payload: WebAnalyzeRequest) -> WebAnalyzeResponse:
    try:
        return analyze_url_or_text(payload.input, payload.analysis_mode)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.post("/web/chat", response_model=WebAnalysisChatResponse)
def chat_web_content(payload: WebAnalysisChatRequest) -> WebAnalysisChatResponse:
    try:
        return answer_web_analysis_question(
            get_settings(),
            analysis=payload.analysis,
            question=payload.question,
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
