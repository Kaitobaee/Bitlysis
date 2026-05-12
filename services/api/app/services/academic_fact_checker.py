"""LLM-powered academic fact-checker.

Pipeline:
1. extract_keywords()   — rút ra tất cả keyword quan trọng từ văn bản (không giới hạn số lượng)
2. extract_claims()     — LLM phân tích và liệt kê các luận điểm kiểm chứng được
3. fact_check_all()     — với mỗi claim, LLM so sánh vs abstracts → verdict
4. compute_support_score() — tỷ lệ claim được hỗ trợ
"""
from __future__ import annotations

import json
import logging
import re

import httpx

from app.config import Settings
from app.schemas.academic import AcademicPaper, FactCheckVerdict

logger = logging.getLogger(__name__)


# ── LLM call helpers ─────────────────────────────────────────────────────────

def _call_llm_json(settings: Settings, prompt: str) -> dict | None:
    """Gọi OpenAI/OpenRouter và trả về JSON. Fallback tự động."""
    # Thử OpenAI trước
    if settings.openai_api_key:
        try:
            url = f"{settings.openai_base_url.rstrip('/')}/chat/completions"
            body = {
                "model": settings.openai_model,
                "messages": [
                    {"role": "system", "content": "Trả về đúng JSON hợp lệ theo schema được yêu cầu. Không markdown."},
                    {"role": "user", "content": prompt},
                ],
                "temperature": 0.1,
                "max_tokens": 2000,
                "response_format": {"type": "json_object"},
            }
            with httpx.Client(timeout=httpx.Timeout(settings.llm_timeout_seconds)) as c:
                resp = c.post(url, headers={"Authorization": f"Bearer {settings.openai_api_key}"}, json=body)
                resp.raise_for_status()
            content = resp.json()["choices"][0]["message"]["content"]
            return json.loads(content)
        except Exception as exc:  # noqa: BLE001
            logger.warning("fact_check_openai_failed: %s", exc)

    # Fallback OpenRouter
    if settings.openrouter_api_key:
        try:
            url = f"{settings.openrouter_base_url.rstrip('/')}/chat/completions"
            headers: dict[str, str] = {"Authorization": f"Bearer {settings.openrouter_api_key}"}
            if settings.openrouter_http_referer:
                headers["HTTP-Referer"] = settings.openrouter_http_referer
            if settings.openrouter_app_title:
                headers["X-Title"] = settings.openrouter_app_title
            body = {
                "model": settings.openrouter_model,
                "messages": [
                    {"role": "system", "content": "Trả về đúng JSON hợp lệ theo schema được yêu cầu. Không markdown."},
                    {"role": "user", "content": prompt},
                ],
                "temperature": 0.1,
                "max_tokens": 2000,
                "response_format": {"type": "json_object"},
            }
            with httpx.Client(timeout=httpx.Timeout(settings.llm_timeout_seconds)) as c:
                resp = c.post(url, headers=headers, json=body)
                resp.raise_for_status()
            content = resp.json()["choices"][0]["message"]["content"]
            return json.loads(content)
        except Exception as exc:  # noqa: BLE001
            logger.warning("fact_check_openrouter_failed: %s", exc)

    return None


# ── Step 1: keyword extraction ────────────────────────────────────────────────

def extract_keywords(text: str, settings: Settings) -> list[str]:
    """Trích xuất tất cả keywords học thuật quan trọng từ văn bản.

    Không giới hạn số lượng — LLM tự quyết định dựa trên độ phong phú của văn bản.
    Mỗi keyword phải ngắn gọn (1-4 từ), đủ cụ thể để search academic papers.
    """
    prompt = (
        "Bạn là chuyên gia phân tích văn bản học thuật. "
        "Đọc văn bản dưới đây và trích xuất TẤT CẢ keywords/cụm từ học thuật quan trọng. "
        "Yêu cầu:\n"
        "- Mỗi keyword phải là 1-4 từ, đủ cụ thể để dùng tìm kiếm bài báo khoa học\n"
        "- Không giới hạn số lượng — lấy hết keyword có giá trị\n"
        "- Ưu tiên thuật ngữ khoa học, tên lý thuyết, phương pháp, khái niệm\n"
        "- Bỏ qua từ chung chung: 'nghiên cứu', 'phân tích', 'dữ liệu', etc.\n"
        "- Nếu văn bản tiếng Việt, dịch keyword sang tiếng Anh để search hiệu quả hơn\n"
        "Trả về JSON: {\"keywords\": [\"keyword1\", \"keyword2\", ...]}\n\n"
        f"Văn bản:\n{text[:6000]}"
    )

    result = _call_llm_json(settings, prompt)
    if result and isinstance(result.get("keywords"), list):
        kws = [str(k).strip() for k in result["keywords"] if k and len(str(k).strip()) >= 3]
        logger.info("keywords_extracted: count=%d", len(kws))
        return kws[:40]  # hard cap 40 để tránh abuse

    # Fallback: heuristic extraction nếu LLM unavailable
    return _heuristic_keywords(text)


def _heuristic_keywords(text: str) -> list[str]:
    """Fallback keyword extraction khi không có LLM."""
    # Tìm các cụm noun phrase đơn giản bằng regex
    # (không hoàn hảo nhưng đủ để fallback)
    words = re.findall(r"\b[A-Z][a-z]+(?:\s+[A-Z][a-z]+)*\b|\b[a-z]{4,}\b", text)
    stopwords = {
        "that", "this", "with", "from", "have", "been", "their",
        "they", "them", "were", "will", "which", "when", "what",
        "những", "được", "trong", "không", "các", "một",
    }
    seen: set[str] = set()
    result: list[str] = []
    for w in words:
        w = w.lower().strip()
        if w in stopwords or len(w) < 4:
            continue
        if w not in seen:
            seen.add(w)
            result.append(w)
        if len(result) >= 10:
            break
    return result


# ── Step 2: claim extraction ──────────────────────────────────────────────────

def extract_claims(text: str, settings: Settings, language: str = "vi") -> list[str]:
    """Trích xuất các luận điểm có thể kiểm chứng từ văn bản."""
    lang_note = "tiếng Việt" if language == "vi" else "English"
    prompt = (
        f"Bạn là nhà phê bình học thuật. Đọc văn bản {lang_note} dưới đây "
        "và liệt kê CÁC LUẬN ĐIỂM CỤ THỂ có thể kiểm chứng bằng tài liệu khoa học.\n"
        "Yêu cầu:\n"
        "- Mỗi claim phải là 1-2 câu, phát biểu một sự kiện/kết luận cụ thể\n"
        "- Chỉ lấy claim có thể đối chiếu với nghiên cứu khoa học\n"
        "- Bỏ qua các quan điểm chủ quan, ý kiến cá nhân\n"
        f"- Trả về 3-8 claims quan trọng nhất\n"
        "Trả về JSON: {\"claims\": [\"claim1\", \"claim2\", ...]}\n\n"
        f"Văn bản:\n{text[:5000]}"
    )

    result = _call_llm_json(settings, prompt)
    if result and isinstance(result.get("claims"), list):
        claims = [str(c).strip() for c in result["claims"] if c and len(str(c).strip()) > 20]
        logger.info("claims_extracted: count=%d", len(claims))
        return claims[:8]

    return []


# ── Step 3: fact-checking ─────────────────────────────────────────────────────

def _build_abstracts_context(papers: list[AcademicPaper]) -> str:
    """Tổng hợp abstracts từ papers thành context cho LLM."""
    parts: list[str] = []
    for i, p in enumerate(papers[:12], 1):  # tối đa 12 papers để tránh token overflow
        if not p.abstract:
            continue
        authors_str = ", ".join(p.authors[:2]) + (" et al." if len(p.authors) > 2 else "")
        year_str = str(p.year) if p.year else "n.d."
        parts.append(
            f"[Paper {i}] {p.title} ({authors_str}, {year_str}) [{p.quartile}]\n"
            f"Abstract: {p.abstract[:400]}"
        )
    return "\n\n".join(parts)


def fact_check_single_claim(
    claim: str,
    papers: list[AcademicPaper],
    settings: Settings,
) -> FactCheckVerdict:
    """Fact-check 1 claim dựa trên danh sách papers."""
    if not papers:
        return FactCheckVerdict(
            claim=claim,
            verdict="Unverified",
            confidence=0.0,
            reasoning="Không tìm thấy bài báo liên quan để đối chiếu.",
        )

    if not settings.llm_enabled:
        return FactCheckVerdict(
            claim=claim,
            verdict="Unverified",
            confidence=0.0,
            reasoning="LLM chưa được cấu hình (thiếu API key). Cài đặt OPENAI_API_KEY hoặc OPENROUTER_API_KEY.",
        )

    abstracts_ctx = _build_abstracts_context(papers)
    prompt = (
        "Bạn là chuyên gia đánh giá tính chính xác học thuật.\n"
        "Dựa trên các bài báo khoa học được cung cấp, đánh giá tính chính xác của luận điểm sau:\n\n"
        f"LUẬN ĐIỂM: {claim}\n\n"
        f"TÀI LIỆU KHOA HỌC:\n{abstracts_ctx}\n\n"
        "Trả về JSON với schema:\n"
        "{\n"
        '  "verdict": "Supported" | "Contradicted" | "Partially_supported" | "Unverified",\n'
        '  "confidence": <số thực 0.0-1.0>,\n'
        '  "reasoning": "<giải thích ngắn gọn 1-3 câu tại sao verdict này>",\n'
        '  "supporting_papers": ["tên paper 1 nếu có", ...],\n'
        '  "contradicting_papers": ["tên paper nếu mâu thuẫn", ...]\n'
        "}\n"
        "Hướng dẫn verdict:\n"
        "- Supported: tài liệu rõ ràng xác nhận luận điểm\n"
        "- Contradicted: tài liệu phủ nhận hoặc mâu thuẫn\n"
        "- Partially_supported: tài liệu hỗ trợ một phần, có điều kiện\n"
        "- Unverified: không đủ bằng chứng để kết luận\n"
    )

    result = _call_llm_json(settings, prompt)
    if not result:
        return FactCheckVerdict(
            claim=claim,
            verdict="Unverified",
            confidence=0.0,
            reasoning="Không thể kết nối LLM để fact-check.",
        )

    verdict_str = str(result.get("verdict", "Unverified"))
    if verdict_str not in {"Supported", "Contradicted", "Partially_supported", "Unverified"}:
        verdict_str = "Unverified"

    return FactCheckVerdict(
        claim=claim,
        verdict=verdict_str,  # type: ignore[arg-type]
        confidence=float(result.get("confidence") or 0.0),
        reasoning=str(result.get("reasoning") or "")[:500],
        supporting_papers=[str(p) for p in (result.get("supporting_papers") or [])[:5]],
        contradicting_papers=[str(p) for p in (result.get("contradicting_papers") or [])[:5]],
    )


def fact_check_all(
    text: str,
    papers: list[AcademicPaper],
    settings: Settings,
    language: str = "vi",
) -> list[FactCheckVerdict]:
    """Trích xuất claims rồi fact-check từng cái."""
    claims = extract_claims(text, settings, language)
    if not claims:
        logger.warning("fact_check_all: no claims extracted")
        return []

    verdicts: list[FactCheckVerdict] = []
    for claim in claims:
        verdict = fact_check_single_claim(claim, papers, settings)
        verdicts.append(verdict)

    return verdicts


# ── Step 4: summary stats ─────────────────────────────────────────────────────

def compute_support_score(verdicts: list[FactCheckVerdict]) -> float:
    """Tính tỷ lệ claims được hỗ trợ (Supported + Partially_supported)."""
    if not verdicts:
        return 0.0
    supported = sum(
        1 for v in verdicts
        if v.verdict in {"Supported", "Partially_supported"}
    )
    return round(supported / len(verdicts), 3)


def quartile_distribution(papers: list[AcademicPaper]) -> dict[str, int]:
    """Đếm số bài theo quartile."""
    dist: dict[str, int] = {"Q1": 0, "Q2": 0, "Q3": 0, "Q4": 0, "Unknown": 0}
    for p in papers:
        dist[p.quartile] = dist.get(p.quartile, 0) + 1
    return {k: v for k, v in dist.items() if v > 0}


def build_summary(
    text: str,
    keywords: list[str],
    verdicts: list[FactCheckVerdict],
    settings: Settings,
    language: str = "vi",
) -> str:
    """Tạo tóm tắt tổng quan về văn bản và kết quả fact-check."""
    if not settings.llm_enabled:
        supported = sum(1 for v in verdicts if v.verdict in {"Supported", "Partially_supported"})
        return (
            f"Tìm thấy {len(verdicts)} luận điểm cần kiểm chứng. "
            f"{supported}/{len(verdicts)} luận điểm có hỗ trợ từ tài liệu khoa học."
        )

    verdict_summary = "; ".join(
        f"{v.verdict}: {v.claim[:60]}..." for v in verdicts[:4]
    )
    lang_note = "tiếng Việt" if language == "vi" else "English"
    prompt = (
        f"Tóm tắt ({lang_note}) ngắn gọn (2-3 câu) về nội dung văn bản và "
        f"kết quả fact-check. Keywords chính: {', '.join(keywords[:6])}. "
        f"Verdict tóm tắt: {verdict_summary}.\n"
        f"Văn bản (đoạn đầu): {text[:500]}\n"
        'Trả về JSON: {"summary": "<tóm tắt>"}'
    )
    result = _call_llm_json(settings, prompt)
    if result and isinstance(result.get("summary"), str):
        return str(result["summary"])[:600]
    return f"Văn bản có {len(verdicts)} luận điểm được kiểm tra với {len(keywords)} keywords học thuật."
