from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field


class WebAnalyzeRequest(BaseModel):
    input: str = Field(min_length=2, max_length=20000)
    analysis_mode: Literal["academic", "marketing_seo", "business"] = "business"


class WebAnalysisChatRequest(BaseModel):
    analysis: "WebAnalyzeResponse"
    question: str = Field(min_length=2, max_length=2000)


class WebChart(BaseModel):
    kind: str = "bar"
    title: str
    labels: list[str]
    values: list[int]
    total: int


class HeadingNode(BaseModel):
    level: int  # 1, 2, 3
    text: str
    children: list["HeadingNode"] = []


class CTAInfo(BaseModel):
    text: str
    type: str  # "button", "link", "form", "none"
    action_keyword: str  # "Buy", "Subscribe", "Download", "Learn More", etc.


class DataFact(BaseModel):
    label: str
    value: str
    type: str  # "number", "date", "percentage", "currency"


class WebAnalyzeResponse(BaseModel):
    analysis_mode: Literal["academic", "marketing_seo", "business"] = "business"
    source_type: str
    source_label: str
    page_title: str = ""
    summary: str
    findings: list[str]
    highlights: list[str] = []
    recommendations: list[str] = []
    evidence: list[dict[str, str]] = []
    metrics: list[dict[str, str | int]]
    sections: list[dict[str, str]]
    chart: WebChart | None = None
    outline: list[HeadingNode] = []
    cta_detected: CTAInfo | None = None
    related_websites: list[dict[str, str]] = []
    data_facts: list[DataFact] = []
    raw_text_preview: str
    fraud_score: float = 0.0
    website_screenshot: str | None = None


class WebAnalysisChatResponse(BaseModel):
    question: str
    answer: str
    source_label: str
    focus: str


WebAnalysisChatRequest.model_rebuild()
WebAnalysisChatResponse.model_rebuild()
