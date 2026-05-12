"""Legacy shim — engine R bridge cũ chuyển sang Python.

Giữ tên `run_r_pipeline_json` cho code/test cũ; nội bộ gọi
`app.services.psychometrics.run_psychometrics`. Trả về tuple
``(parsed, stderr, returncode)`` để các caller (auto_analysis, core/analysis,
routers/v1/run) không cần đổi chữ ký.

Cờ deploy: không còn phụ thuộc Rscript hay package `packages/r-pipeline`.
"""

from __future__ import annotations

import logging
from pathlib import Path
from typing import Any

import pandas as pd

from app.config import Settings
from app.services.psychometrics import ENGINE_ID, run_psychometrics

logger = logging.getLogger(__name__)


def resolve_r_package_root(settings: Settings) -> Path:
    """Backward compat: trỏ tới `packages/r-pipeline` để test cũ vẫn pass.

    Chỉ dùng để định vị fixture (`tests/testthat/fixtures/tiny_pls.csv`).
    """
    if settings.r_package_root is not None:
        return Path(settings.r_package_root).resolve()
    here = Path(__file__).resolve()
    # services/api/app/services/r_pipeline.py → parents[4] = repo root
    repo_root = here.parents[4]
    return (repo_root / "packages" / "r-pipeline").resolve()


def run_r_pipeline_json(
    settings: Settings,
    df: pd.DataFrame,
    analyses: list[dict[str, Any]],
) -> tuple[dict[str, Any], str, int]:
    """Chữ ký tương thích R bridge cũ; trả (parsed_json, stderr, returncode).

    `stderr` luôn rỗng; `returncode` = 0 khi mọi block không raise. Engine Python
    không bao giờ subprocess, nên không có timeout R.
    """
    _ = settings  # placeholder để giữ giao diện
    parsed = run_psychometrics(df, analyses)
    parsed.setdefault("engine", ENGINE_ID)
    rc = 0 if parsed.get("ok") else 1
    return parsed, "", rc
