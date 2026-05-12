"""Pydantic schemas cho Academic Content Analyzer."""
from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field


class AcademicPaper(BaseModel):
    title: str
    authors: list[str] = []
    year: int | None = None
    doi: str | None = None
    abstract: str = ""
    cited_by_count: int = 0
    quartile: Literal["Q1", "Q2", "Q3", "Q4", "Unknown"] = "Unknown"
    source_name: str = ""  # Tên tạp chí / venue
    open_access: bool = False
    url: str = ""


class FactCheckVerdict(BaseModel):
    claim: str
    verdict: Literal["Supported", "Contradicted", "Partially_supported", "Unverified"]
    confidence: float = Field(ge=0.0, le=1.0)
    reasoning: str
    supporting_papers: list[str] = []   # paper titles
    contradicting_papers: list[str] = []


class AcademicAnalyzeRequest(BaseModel):
    text: str = Field(
        min_length=50,
        max_length=15000,
        description="Văn bản cần phân tích và fact-check",
    )
    language: Literal["vi", "en"] = Field(
        default="vi",
        description="Ngôn ngữ văn bản — dùng để tối ưu prompt LLM",
    )
    max_papers: int = Field(
        default=15,
        ge=5,
        le=30,
        description="Số lượng bài báo tối đa cần fetch",
    )


class AcademicAnalyzeResponse(BaseModel):
    summary: str
    keywords: list[str]
    papers: list[AcademicPaper]
    fact_checks: list[FactCheckVerdict]
    quartile_distribution: dict[str, int]   # {"Q1": 3, "Q2": 5, ...}
    overall_support_score: float            # % claims được hỗ trợ (0.0–1.0)
    search_query: str                       # Query string đã dùng để search
