"""Smoke tests cho render_docx_report mới."""

from __future__ import annotations

from pathlib import Path

import pytest


def test_docx_report_contains_academic_sections(tmp_path: Path):
    docx = pytest.importorskip("docx")
    Document = docx.Document  # noqa: N806

    from app.services.export_renderers import render_docx_report

    result_summary = {
        "engine": "bitlysis_comprehensive_analysis",
        "version": 1,
        "academic_summary": {
            "data_type": "5 biến Likert, 2 biến phân loại",
            "methods": ["cronbach_alpha", "efa", "chi_square"],
            "rationale": "Đủ Likert để chạy Cronbach + EFA.",
            "assumptions": ["Quan sát độc lập", "Thang đo đơn hướng"],
            "conclusion": "Đã chạy 5 kiểm định (2 bác bỏ, 3 không đủ bằng chứng).",
            "warnings": [],
        },
        "hypothesis_table": [
            {
                "hypothesis_id": "H1",
                "method": "Chi-square",
                "statistic": 12.3,
                "p_value": 0.002,
                "effect_size": 0.42,
                "effect_size_kind": "cramers_v",
                "decision": "reject_h0",
            },
            {
                "hypothesis_id": "H2",
                "method": "Welch t-test",
                "statistic": 1.8,
                "p_value": 0.09,
                "effect_size": 0.3,
                "effect_size_kind": "cohens_d",
                "decision": "fail_to_reject_h0",
            },
        ],
        "cleaning": {
            "summary": {
                "rows_before": 100,
                "rows_after": 95,
                "missing_policy": "drop_row",
                "outlier_policy": "report_only",
            },
            "log": [
                {"action": "missing_value_report", "detail": "5 dòng còn missing", "evidence": {}},
            ],
        },
        "provenance_ref": {
            "psychometrics_engine": "bitlysis_python_psychometrics",
            "file_sha256": "sha256:abc",
            "pip_lock_sha256": "sha256:def",
            "random_seed": 42,
            "started_at": "2026-01-01T00:00:00+00:00",
            "engine_versions": {"pandas": "3.0.0"},
        },
    }

    out_path = tmp_path / "report.docx"
    render_docx_report(
        job_id="job-123",
        original_filename="survey.csv",
        columns=["q1", "q2", "q3", "q4", "q5", "gender", "group"],
        result_summary=result_summary,
        out_path=out_path,
        template_path=None,
    )
    assert out_path.is_file()

    doc = Document(str(out_path))
    text = "\n".join(p.text for p in doc.paragraphs)
    assert "Bitlysis" in text
    assert "Tóm tắt học thuật" in text
    assert "Bảng giả thuyết" in text
    assert "Làm sạch dữ liệu" in text
    assert "Minh bạch học thuật" in text
    # Bảng giả thuyết tồn tại.
    assert len(doc.tables) >= 1
    # Provenance số liệu xuất hiện.
    assert "sha256:abc" in text
    assert "sha256:def" in text
