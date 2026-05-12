"""Academic Content Analyzer router.

POST /v1/academic/analyze
    → tìm kiếm bài báo Q1-Q4 + fact-check luận điểm bằng LLM
"""
from __future__ import annotations

import logging

from fastapi import APIRouter, HTTPException

from app.config import get_settings
from app.schemas.academic import AcademicAnalyzeRequest, AcademicAnalyzeResponse
from app.services.academic_fact_checker import (
    build_summary,
    compute_support_score,
    extract_keywords,
    fact_check_all,
    quartile_distribution,
)
from app.services.academic_search import build_paper_list

logger = logging.getLogger(__name__)

router = APIRouter(tags=["academic"])


@router.post("/academic/analyze", response_model=AcademicAnalyzeResponse)
def analyze_academic_content(payload: AcademicAnalyzeRequest) -> AcademicAnalyzeResponse:
    """Phân tích văn bản: tìm bài báo khoa học Q1-Q4 và fact-check luận điểm."""
    settings = get_settings()

    # 1. Extract keywords (LLM nếu có, heuristic nếu không)
    keywords = extract_keywords(payload.text, settings)
    if not keywords:
        raise HTTPException(
            status_code=422,
            detail="Không trích xuất được keyword từ văn bản. Văn bản quá ngắn hoặc không có nội dung học thuật.",
        )
    logger.info("academic_analyze: keywords=%d text_len=%d", len(keywords), len(payload.text))

    # 2. Tìm kiếm bài báo
    papers, search_query = build_paper_list(
        keywords,
        max_papers=payload.max_papers,
        settings=settings,
    )
    logger.info("academic_analyze: papers_found=%d", len(papers))

    # 3. Fact-check
    verdicts = fact_check_all(payload.text, papers, settings, payload.language)

    # 4. Stats
    support_score = compute_support_score(verdicts)
    q_dist = quartile_distribution(papers)

    # 5. Summary
    summary = build_summary(payload.text, keywords, verdicts, settings, payload.language)

    return AcademicAnalyzeResponse(
        summary=summary,
        keywords=keywords,
        papers=papers,
        fact_checks=verdicts,
        quartile_distribution=q_dist,
        overall_support_score=support_score,
        search_query=search_query,
    )
