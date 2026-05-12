"""Phase 5 — đường dẫn R package; integration skip nếu không có Rscript."""

from __future__ import annotations

import shutil

import pandas as pd
import pytest

from app.config import Settings
from app.services.r_pipeline import resolve_r_package_root, run_r_pipeline_json


def test_resolve_r_package_root_contains_cli():
    settings = Settings()
    root = resolve_r_package_root(settings)
    cli = root / "inst" / "cli" / "run_analysis.R"
    assert cli.is_file(), f"Expected R CLI at {cli}"


@pytest.mark.skipif(not shutil.which("Rscript"), reason="Rscript not on PATH")
def test_run_r_pipeline_integration_fixture():
    root = resolve_r_package_root(Settings())
    csv = root / "tests" / "testthat" / "fixtures" / "tiny_pls.csv"
    assert csv.is_file()
    df = pd.read_csv(csv)
    analyses = [
        {"type": "cronbach_alpha", "scale_id": "t", "items": ["x1", "x2", "x3"]},
        {
            "type": "pls_sem",
            "min_n": 30,
            "min_items_per_construct": 2,
            "min_constructs": 2,
            "constructs": [
                {"name": "ETA", "mode": "reflective", "indicators": ["x1", "x2", "x3"]},
                {"name": "KSI", "mode": "reflective", "indicators": ["y1", "y2", "y3"]},
            ],
            "paths": [{"from": "KSI", "to": "ETA"}],
        },
    ]
    parsed, stderr, rc = run_r_pipeline_json(Settings(), df, analyses)
    assert rc == 0, (stderr, parsed)
    assert parsed.get("ok") is True
    assert len(parsed.get("results", [])) == 2
