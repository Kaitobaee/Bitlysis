from __future__ import annotations

import json
import logging
from typing import Any

import pandas as pd

from app.config import Settings
from app.schemas.job import FileAnalysisChatResponse
from app.services.web_analyzer import (
    _call_openai_text,
    _call_openrouter_text,
    _clean_text,
    _strip_chat_markdown,
)

logger = logging.getLogger(__name__)


def _compact_value(value: Any, *, depth: int = 0) -> Any:
    if depth >= 3:
        if isinstance(value, (dict, list)):
            return "..."
        return value
    if isinstance(value, dict):
        out: dict[str, Any] = {}
        for idx, (key, item) in enumerate(value.items()):
            if idx >= 16:
                out["..."] = "truncated"
                break
            out[str(key)] = _compact_value(item, depth=depth + 1)
        return out
    if isinstance(value, list):
        return [_compact_value(item, depth=depth + 1) for item in value[:12]]
    if isinstance(value, float) and pd.isna(value):
        return None
    return value


def _sample_rows(df: pd.DataFrame, limit: int = 12) -> list[dict[str, Any]]:
    sample = df.head(limit).astype(object).where(pd.notna(df.head(limit)), None)
    return sample.to_dict(orient="records")


def _extract_grounding_context(
    raw_job: dict[str, Any],
    dataframe: pd.DataFrame,
) -> dict[str, Any]:
    """Build comprehensive grounding context from all available analysis results.

    Grounding AI: the chatbot should answer ONLY based on evidence in this context,
    not hallucinate. We include hypothesis test results, statistical findings,
    column profiles, and the full AI summary so the model can cite specific numbers.
    """
    result_summary = raw_job.get("result_summary") or {}
    profiling_detail = raw_job.get("profiling_detail") or {}

    # --- Academic / method summary ---
    academic_summary = result_summary.get("academic_summary") or {}
    method_context: dict[str, Any] = {}
    if isinstance(academic_summary, dict):
        method_context = {
            "data_type": academic_summary.get("data_type", ""),
            "methods_used": academic_summary.get("methods", []),
            "rationale": academic_summary.get("rationale", ""),
            "assumptions": academic_summary.get("assumptions", []),
            "conclusion": academic_summary.get("conclusion", ""),
            "warnings": academic_summary.get("warnings", []),
        }

    # --- Hypothesis test table ---
    hypothesis_results: list[dict[str, Any]] = []
    raw_hypotheses = result_summary.get("hypothesis_table")
    if isinstance(raw_hypotheses, list):
        for h in raw_hypotheses[:15]:
            if not isinstance(h, dict):
                continue
            hypothesis_results.append({
                "hypothesis": str(h.get("hypothesis") or h.get("test_name") or ""),
                "verdict": str(h.get("verdict") or h.get("result") or ""),
                "p_value": h.get("p_value"),
                "statistic": h.get("statistic") or h.get("test_statistic"),
                "effect_size": h.get("effect_size") or h.get("cohen_d"),
                "note": str(h.get("note") or h.get("interpretation") or ""),
            })

    # --- Key statistical results ---
    results_block = result_summary.get("results") or {}
    statistical_results: dict[str, Any] = {}
    if isinstance(results_block, dict):
        for key in [
            "summary", "highlights", "findings", "descriptive_stats",
            "correlations", "regression_summary", "group_comparison",
            "key_metrics", "significant_pairs", "factor_loadings",
            "cronbach_alpha", "reliability",
        ]:
            if key in results_block:
                statistical_results[key] = _compact_value(results_block[key], depth=0)

    # --- Evidence block ---
    evidence_block = _compact_value(result_summary.get("evidence"), depth=0) if result_summary.get("evidence") else None

    # --- Charts context (titles only, no raw data) ---
    charts_context: list[dict[str, str]] = []
    raw_charts = result_summary.get("charts")
    if isinstance(raw_charts, list):
        for ch in raw_charts[:10]:
            if isinstance(ch, dict):
                charts_context.append({
                    "title": str(ch.get("title") or ch.get("label") or ""),
                    "type": str(ch.get("type") or ch.get("kind") or ""),
                    "x_label": str(ch.get("x_label") or ""),
                    "y_label": str(ch.get("y_label") or ""),
                })

    # --- Column-level profiling ---
    column_profiles: dict[str, Any] = {}
    col_profiles_raw = profiling_detail.get("column_profiles") or {}
    if isinstance(col_profiles_raw, dict):
        for col_name, col_info in list(col_profiles_raw.items())[:25]:
            if not isinstance(col_info, dict):
                continue
            column_profiles[str(col_name)] = {
                "dtype": col_info.get("dtype", ""),
                "missing_pct": col_info.get("missing_pct"),
                "unique_count": col_info.get("unique_count"),
                "mean": col_info.get("mean"),
                "std": col_info.get("std"),
                "min": col_info.get("min"),
                "max": col_info.get("max"),
                "top_values": (col_info.get("top_values") or [])[:5],
                "skewness": col_info.get("skewness"),
            }

    # --- Top-level text fields ---
    ai_summary = (
        result_summary.get("ai_summary")
        or result_summary.get("summary")
        or ""
    )
    highlights: list[str] = []
    raw_highlights = result_summary.get("highlights")
    if isinstance(raw_highlights, list):
        highlights = [str(h) for h in raw_highlights[:8] if h]
    findings: list[str] = []
    raw_findings = result_summary.get("findings")
    if isinstance(raw_findings, list):
        findings = [str(f) for f in raw_findings[:8] if f]

    return {
        "job_id": raw_job.get("job_id"),
        "filename": raw_job.get("original_filename"),
        "status": raw_job.get("status"),
        "columns": list(dataframe.columns),
        "row_count": int(len(dataframe)),
        "sample_rows": _sample_rows(dataframe, limit=10),
        "ai_summary": ai_summary,
        "highlights": highlights,
        "findings": findings,
        "method_context": method_context if any(method_context.values()) else None,
        "hypothesis_tests": hypothesis_results if hypothesis_results else None,
        "statistical_results": statistical_results if statistical_results else None,
        "evidence": evidence_block,
        "charts_available": charts_context if charts_context else None,
        "column_profiles": column_profiles if column_profiles else None,
    }


def _build_file_chat_messages(
    *,
    raw_job: dict[str, Any],
    dataframe: pd.DataFrame,
    question: str,
    language: str = "vi",
) -> list[dict[str, str]]:
    context = _extract_grounding_context(raw_job, dataframe)
    if language == "en":
        system_prompt = (
            "You are the Bitlysis data analysis AI chatbot. The grounding data (context) is the "
            "analysis result provided below. Only answer based on hypothesis test results, "
            "statistical metrics, AI summary, column profiling, and sample rows provided — "
            "do NOT add new numbers or results. If the question requires more precise information "
            "than the context provides, say so clearly and suggest the user open the details. "
            "Reply in English clearly, prioritize explaining statistical significance, cite "
            "specific evidence from context. Do not use markdown tables or code blocks."
        )
        user_prompt = (
            "Grounding context (JSON):\n"
            f"{json.dumps(context, ensure_ascii=False)}\n\n"
            "Question:\n"
            f"{question}"
        )
    else:
        system_prompt = (
            "Ban la AI chatbot phan tich du lieu Bitlysis. Du lieu nen tang (grounding) la ket qua "
            "phan tich da thuc hien duoc cung cap ben duoi. Chi tra loi dua tren ket qua kiem dinh gia "
            "thuyet, chi so thong ke, tom tat AI, profiling cot, va sample rows duoc cung cap — "
            "KHONG tu them so lieu hoac ket qua moi. Neu cau hoi can thong tin chinh xac hon context "
            "co, hay noi ro va goi y nguoi dung mo chi tiet. Tra loi bang tieng Viet ro rang, "
            "uu tien giai thich y nghia thong ke, trich dan bang chung cu the tu context. "
            "Khong dung markdown table hoac code block."
        )
        user_prompt = (
            "Grounding context (JSON):\n"
            f"{json.dumps(context, ensure_ascii=False)}\n\n"
            "Cau hoi:\n"
            f"{question}"
        )
    return [
        {"role": "system", "content": system_prompt},
        {"role": "user", "content": user_prompt},
    ]


def _fallback_file_chat_answer(
    raw_job: dict[str, Any],
    dataframe: pd.DataFrame,
    question: str,
    language: str = "vi",
) -> str:
    filename = str(raw_job.get("original_filename") or raw_job.get("stored_as") or "file")
    columns = ", ".join(str(col) for col in list(dataframe.columns)[:8])
    result_summary = raw_job.get("result_summary")
    summary_hint = ""
    if isinstance(result_summary, dict):
        ai_summary = result_summary.get("ai_summary") or result_summary.get("summary")
        if isinstance(ai_summary, str) and ai_summary.strip():
            if language == "en":
                summary_hint = f" Current result notes: {_clean_text(ai_summary)[:360]}"
            else:
                summary_hint = f" Ket qua hien co ghi nhan: {_clean_text(ai_summary)[:360]}"
    if language == "en":
        return (
            f"I am focused on file {filename}. The file has {len(dataframe)} rows and "
            f"{len(dataframe.columns)} columns ({columns}).{summary_hint} "
            "You can ask about columns, unusual values, what results mean, or which chart to create next."
        )
    return (
        f"Toi dang bam theo file {filename}. File hien doc duoc {len(dataframe)} dong va "
        f"{len(dataframe.columns)} cot ({columns}).{summary_hint} "
        "Ban co the hoi ve cot, gia tri bat thuong, y nghia ket qua, hoac nen ve bieu do nao tiep theo."
    )


def answer_file_job_question(
    settings: Settings,
    *,
    raw_job: dict[str, Any],
    dataframe: pd.DataFrame,
    question: str,
    language: str = "vi",
) -> FileAnalysisChatResponse:
    cleaned_question = _clean_text(question)
    if not cleaned_question:
        raise ValueError("Cau hoi khong duoc rong")

    messages = _build_file_chat_messages(
        raw_job=raw_job,
        dataframe=dataframe,
        question=cleaned_question,
        language=language,
    )
    answer: str | None = None

    if settings.llm_enabled:
        try:
            answer = _call_openai_text(settings, messages)
        except Exception as exc:  # noqa: BLE001
            logger.warning("file_chat_openai_fallback: %s", type(exc).__name__)

        if answer is None:
            try:
                answer = _call_openrouter_text(settings, messages)
            except Exception as exc:  # noqa: BLE001
                logger.warning("file_chat_openrouter_fallback: %s", type(exc).__name__)

    if not answer:
        answer = _fallback_file_chat_answer(raw_job, dataframe, cleaned_question, language)
    else:
        answer = _strip_chat_markdown(answer)

    focus = str(raw_job.get("original_filename") or raw_job.get("job_id") or "file")
    return FileAnalysisChatResponse(
        question=cleaned_question,
        answer=answer,
        job_id=str(raw_job.get("job_id") or ""),
        focus=focus,
    )
