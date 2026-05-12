"""Golden eval Phase 7 — parse JSON LLM + rule-based ổn định; không phụ thuộc model env."""

from __future__ import annotations

import json
from pathlib import Path

import pytest
from pydantic import ValidationError

from app.services.llm_hypotheses import (
    extract_json_object,
    rule_based_hypotheses,
    validate_llm_hypothesis_json,
)

GOLDEN = Path(__file__).resolve().parents[1] / "eval" / "golden" / "hypothesis_llm_golden.json"


def _golden() -> dict:
    return json.loads(GOLDEN.read_text(encoding="utf-8"))


@pytest.mark.parametrize(
    "case_id",
    [c["id"] for c in _golden()["parse_cases"]],
)
def test_golden_parse_cases(case_id: str) -> None:
    data = _golden()
    case = next(c for c in data["parse_cases"] if c["id"] == case_id)
    parsed = validate_llm_hypothesis_json(extract_json_object(case["raw_text"]))
    ids = [h.hypothesis_id for h in parsed.hypotheses]
    assert ids == case["expect_hypothesis_ids"]


def test_golden_rule_based_stable_ids() -> None:
    rb = _golden()["rule_based"]
    out = rule_based_hypotheses(rb["columns"], max_hypotheses=10)
    ids = [h.hypothesis_id for h in out.hypotheses]
    assert ids == rb["expected_hypothesis_ids"]


def test_empty_hypotheses_invalid() -> None:
    with pytest.raises(ValidationError):
        validate_llm_hypothesis_json({"schema_version": 1, "hypotheses": []})


def test_openrouter_model_env_does_not_affect_parse(monkeypatch: pytest.MonkeyPatch) -> None:
    """Golden parse không phụ thuộc OPENROUTER_MODEL (đổi env không cần đổi chuỗi golden)."""
    monkeypatch.setenv("OPENROUTER_MODEL", "vendor/unknown-model-for-eval")
    case = _golden()["parse_cases"][0]
    parsed = validate_llm_hypothesis_json(extract_json_object(case["raw_text"]))
    assert parsed.hypotheses[0].hypothesis_id == "H1"
