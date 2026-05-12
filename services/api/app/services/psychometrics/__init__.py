"""Python psychometrics engine (Cronbach, EFA, PLS-SEM).

Thay thế R bridge cũ (`services/api/app/services/r_pipeline.py`). Dispatcher giữ
shape `{"ok", "engine", "results": [...]}` để các caller (auto_analysis,
core/analysis, routers/v1/run) không phải đổi cấu trúc.
"""

from __future__ import annotations

import logging
from typing import Any

import pandas as pd

from app.services.psychometrics.cronbach import run_cronbach
from app.services.psychometrics.efa import run_efa
from app.services.psychometrics.pls_sem import run_pls_sem

logger = logging.getLogger(__name__)

ENGINE_ID = "bitlysis_python_psychometrics"
ENGINE_VERSION = 1

_DISPATCH = {
    "cronbach_alpha": run_cronbach,
    "efa": run_efa,
    "pls_sem": run_pls_sem,
}


def _unknown(block: dict[str, Any]) -> dict[str, Any]:
    typ = block.get("type") or "unknown"
    return {
        "type": typ,
        "ok": False,
        "ran": False,
        "skipped": True,
        "warnings": [f"Unknown analysis type: {typ}"],
        "gates": {},
    }


def run_psychometrics(
    df: pd.DataFrame,
    analyses: list[dict[str, Any]],
    *,
    random_seed: int | None = None,
) -> dict[str, Any]:
    """Chạy danh sách analyses, trả envelope JSON tương thích R cũ.

    `random_seed` được forward xuống PLS bootstrap; các block khác không dùng.
    """
    if not isinstance(analyses, list) or not analyses:
        return {
            "ok": False,
            "engine": ENGINE_ID,
            "version": ENGINE_VERSION,
            "error": "Thiếu analyses[]",
            "results": [],
        }
    results: list[dict[str, Any]] = []
    for block in analyses:
        if not isinstance(block, dict):
            results.append({
                "type": "unknown",
                "ok": False,
                "ran": False,
                "skipped": True,
                "warnings": ["analysis block phải là object JSON"],
                "gates": {},
            })
            continue
        typ = str(block.get("type") or "").strip()
        runner = _DISPATCH.get(typ)
        if runner is None:
            results.append(_unknown(block))
            continue
        try:
            if typ == "pls_sem":
                res = runner(df, block, random_seed=random_seed)
            else:
                res = runner(df, block)
        except Exception as exc:  # noqa: BLE001
            logger.exception("psychometrics block failed: %s", typ)
            res = {
                "type": typ,
                "ok": False,
                "ran": False,
                "skipped": True,
                "warnings": [f"Lỗi engine: {exc}"],
                "gates": {},
            }
        results.append(res)
    return {
        "ok": True,
        "engine": ENGINE_ID,
        "version": ENGINE_VERSION,
        "results": results,
    }


__all__ = [
    "ENGINE_ID",
    "ENGINE_VERSION",
    "run_cronbach",
    "run_efa",
    "run_pls_sem",
    "run_psychometrics",
]
