"""OpenRouter chat → JSON cố định → Pydantic; timeout; fallback rule-based; không log PII production."""

from __future__ import annotations

import json
import logging
import re
from typing import Any, Literal

import httpx
from pydantic import ValidationError

from app.config import Settings
from app.schemas.llm import LLMHypothesisResponse, SuggestedHypothesis

logger = logging.getLogger(__name__)

SourceKind = Literal["openrouter", "fallback", "disabled_no_key"]

_JSON_FENCE = re.compile(r"^\s*```(?:json)?\s*\n?(.*?)\n?```\s*$", re.DOTALL | re.IGNORECASE)

SYSTEM_PROMPT = """Bạn là trợ lý thống kê cho nền tảng phân tích dữ liệu. Chỉ trả về MỘT object JSON hợp lệ, không markdown, không giải thích ngoài JSON.
Schema bắt buộc:
{
  "schema_version": 1,
  "hypotheses": [
    {
      "hypothesis_id": "chuỗi ngắn duy nhất, ví dụ H1",
      "statement_vi": "một giả thuyết nghiên cứu bằng tiếng Việt, không bịa số liệu",
      "variables_involved": ["tên_cột", "..."],
      "suggested_test_kind": "compare_groups | regression | correlation | timeseries | categorical | other"
    }
  ],
  "notes": "tùy chọn, ngắn"
}
Quy tắc:
- Không tạo p-value, hệ số, hay kết luận thống kê; chỉ gợi ý giả thuyết dựa trên tên/khái niệm cột.
- Tối đa 10 phần tử trong hypotheses.
- hypothesis_id phải khác nhau."""


def extract_json_object(text: str) -> dict[str, Any]:
    """Tách JSON từ phản hồi (có thể bọc ```json)."""
    raw = text.strip()
    m = _JSON_FENCE.match(raw)
    if m:
        raw = m.group(1).strip()
    return json.loads(raw)


def validate_llm_hypothesis_json(data: dict[str, Any]) -> LLMHypothesisResponse:
    return LLMHypothesisResponse.model_validate(data)


def rule_based_hypotheses(columns: list[str], *, max_hypotheses: int = 8) -> LLMHypothesisResponse:
    """Gợi ý cố định theo tên cột — không gọi LLM."""
    cols = [str(c).strip() for c in columns if c and str(c).strip()][:24]
    if not cols:
        return LLMHypothesisResponse(
            schema_version=1,
            hypotheses=[
                SuggestedHypothesis(
                    hypothesis_id="H_rule_empty",
                    statement_vi="Chưa có tên cột — tải bảng dữ liệu có header để nhận gợi ý.",
                    variables_involved=[],
                    suggested_test_kind="other",
                )
            ],
            notes="fallback_rule_based",
        )
    out: list[SuggestedHypothesis] = []
    n_take = min(len(cols), max(1, max_hypotheses - 1))
    for i, c in enumerate(cols[:n_take]):
        out.append(
            SuggestedHypothesis(
                hypothesis_id=f"H_rule_{i + 1:02d}",
                statement_vi=(
                    f"Khảo sát phân bố hoặc vai trò của biến «{c}» trong bối cảnh các biến khác của bảng."
                ),
                variables_involved=[c],
                suggested_test_kind="other",
            ),
        )
    if len(cols) >= 2 and len(out) < max_hypotheses:
        out.append(
            SuggestedHypothesis(
                hypothesis_id="H_rule_pair_01",
                statement_vi=(
                    f"Kiểm tra quan hệ hoặc khác biệt giữa «{cols[0]}» và «{cols[1]}» "
                    "(tương quan, hồi quy hoặc so sánh nhóm tùy kiểu dữ liệu)."
                ),
                variables_involved=[cols[0], cols[1]],
                suggested_test_kind="regression",
            ),
        )
    return LLMHypothesisResponse(
        schema_version=1,
        hypotheses=out[:max_hypotheses],
        notes="fallback_rule_based",
    )


def _should_log_prompt_content(settings: Settings) -> bool:
    return bool(settings.llm_log_prompts) and settings.app_environment != "production"


def _build_user_prompt(columns: list[str], profiling_types: dict[str, str] | None) -> str:
    lines = ["Danh sách cột (chỉ tên, không có giá trị ô):"]
    lines.append(json.dumps(columns, ensure_ascii=False))
    if profiling_types:
        lines.append("Gợi ý kiểu (từ profiling, có thể thiếu):")
        lines.append(json.dumps(profiling_types, ensure_ascii=False))
    lines.append(
        "Trả về JSON đúng schema (schema_version=1, hypotheses array). "
        "Không đưa email, tên người, hay dữ liệu cá nhân vào statement.",
    )
    return "\n".join(lines)


def call_openrouter_chat(
    settings: Settings,
    *,
    user_prompt: str,
    client: httpx.Client | None = None,
) -> tuple[str, str]:
    """
    Gọi OpenRouter chat completions.
    Trả về (assistant_content, model_id_used).
    """
    if not settings.openrouter_api_key:
        msg = "Thiếu OPENROUTER_API_KEY"
        raise RuntimeError(msg)
    url = f"{settings.openrouter_base_url.rstrip('/')}/chat/completions"
    headers = {
        "Authorization": f"Bearer {settings.openrouter_api_key}",
        "Content-Type": "application/json",
    }
    if settings.openrouter_http_referer:
        headers["HTTP-Referer"] = settings.openrouter_http_referer
    if settings.openrouter_app_title:
        headers["X-Title"] = settings.openrouter_app_title
    body: dict[str, Any] = {
        "model": settings.openrouter_model,
        "messages": [
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": user_prompt},
        ],
        "temperature": 0.2,
        "max_tokens": 2048,
    }
    if settings.openrouter_json_mode:
        body["response_format"] = {"type": "json_object"}
    timeout = httpx.Timeout(settings.llm_timeout_seconds)
    own_client = client is None
    hc = client or httpx.Client(timeout=timeout)
    try:
        r = hc.post(url, headers=headers, json=body)
        r.raise_for_status()
        payload = r.json()
        choices = payload.get("choices")
        if not isinstance(choices, list) or len(choices) < 1:
            msg = "OpenRouter: response không có choices"
            raise ValueError(msg)
        choice0 = choices[0]
        msg = (choice0.get("message") or {})
        content = msg.get("content") or ""
        if not isinstance(content, str):
            content = str(content)
        if not content.strip():
            msg = "OpenRouter: completion rỗng"
            raise ValueError(msg)
        model_used = str(payload.get("model") or settings.openrouter_model)
        return content, model_used
    finally:
        if own_client:
            hc.close()


def profiling_types_from_job_meta(raw: dict[str, Any]) -> dict[str, str] | None:
    """Lấy map cột → pandas_dtype từ profiling_detail nếu có."""
    detail = raw.get("profiling_detail")
    if not isinstance(detail, dict):
        return None
    profiles = detail.get("column_profiles")
    if not isinstance(profiles, list):
        return None
    out: dict[str, str] = {}
    for row in profiles:
        if isinstance(row, dict) and row.get("name"):
            out[str(row["name"])] = str(row.get("pandas_dtype", ""))
    return out or None


def run_hypothesis_suggestions(
    settings: Settings,
    *,
    columns: list[str],
    profiling_types: dict[str, str] | None = None,
    force_fallback: bool = False,
    httpx_client: httpx.Client | None = None,
) -> tuple[LLMHypothesisResponse, SourceKind, str | None, str | None]:
    """
    Trả về (result, source, model_or_none, warning_or_none).
    source: openrouter | fallback | disabled_no_key
    """
    max_h = max(1, min(15, settings.llm_max_hypotheses))
    if force_fallback:
        fb = rule_based_hypotheses(columns, max_hypotheses=max_h)
        return fb, "fallback", None, None

    if not settings.openrouter_api_key or not settings.llm_enabled:
        fb = rule_based_hypotheses(columns, max_hypotheses=max_h)
        return fb, "disabled_no_key", None, None

    user_prompt = _build_user_prompt(columns, profiling_types)
    if _should_log_prompt_content(settings):
        logger.info(
            "llm_hypotheses_prompt_excerpt",
            extra={
                "prompt_chars": len(user_prompt),
                "columns_n": len(columns),
                "excerpt": user_prompt[:400],
            },
        )
    else:
        logger.info(
            "llm_hypotheses_request",
            extra={
                "prompt_chars": len(user_prompt),
                "columns_n": len(columns),
                "environment": settings.app_environment,
            },
        )

    try:
        content, model_used = call_openrouter_chat(
            settings,
            user_prompt=user_prompt,
            client=httpx_client,
        )
        data = extract_json_object(content)
        parsed = validate_llm_hypothesis_json(data)
        # cắt theo cấu hình
        parsed = LLMHypothesisResponse(
            schema_version=1,
            hypotheses=parsed.hypotheses[:max_h],
            notes=parsed.notes,
        )
        return parsed, "openrouter", model_used, None
    except (
        httpx.TimeoutException,
        httpx.HTTPError,
        json.JSONDecodeError,
        ValidationError,
        ValueError,
    ) as e:
        logger.warning("llm_hypotheses_fallback: %s", type(e).__name__)
        fb = rule_based_hypotheses(columns, max_hypotheses=max_h)
        return fb, "fallback", None, str(e)[:500]
    except Exception as e:  # noqa: BLE001
        logger.exception("llm_hypotheses_unexpected_fallback")
        fb = rule_based_hypotheses(columns, max_hypotheses=max_h)
        return fb, "fallback", None, str(e)[:500]
