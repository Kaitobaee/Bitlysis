"""R Pipeline bridge — gọi Rscript subprocess khi r_enabled=True.

Kiến trúc (ADR 0005 rev2):
- Khi `settings.r_enabled=True` VÀ Rscript tìm thấy trên PATH:
    → Ghi CSV tạm, chạy Rscript inst/cli/run_analysis.R, parse stdout JSON.
- Khi `settings.r_enabled=False` (production) hoặc không có Rscript:
    → Fallback sang Python psychometrics engine (không mất data).
- GitHub Actions cron workflow không gọi hàm này trực tiếp;
    cron tự chạy Rscript độc lập và POST kết quả về /v1/jobs/{id}/r-result.

Interface `run_r_pipeline_json` giữ nguyên để các caller cũ (auto_analysis.py,
tests/) không gãy.
"""

from __future__ import annotations

import json
import logging
import shutil
import subprocess
import tempfile
from pathlib import Path
from typing import Any

import pandas as pd

from app.config import Settings

logger = logging.getLogger(__name__)

# Re-export Python engine as fallback
from app.services.psychometrics import run_psychometrics as _py_psychometrics  # noqa: E402

_FALLBACK_ENGINE = "bitlysis_python_psychometrics_fallback"


def resolve_r_package_root(settings: Settings) -> Path:
    """Tìm thư mục packages/r-pipeline từ config hoặc repo root."""
    if settings.r_package_root is not None:
        return Path(settings.r_package_root).resolve()
    # Tự resolve: services/api → repo root → packages/r-pipeline
    here = Path(__file__).resolve()
    # Đi lên 4 cấp: services/api/app/services → repo root
    for candidate in [
        here.parents[3] / "packages" / "r-pipeline",
        here.parents[4] / "packages" / "r-pipeline",
    ]:
        if candidate.is_dir():
            return candidate
    # Fallback: trả đường dẫn tương đối (test sẽ assert cli file tồn tại)
    return here.parents[3] / "packages" / "r-pipeline"


def _find_rscript(settings: Settings) -> str | None:
    """Tìm Rscript binary; trả None nếu không tìm thấy."""
    if settings.bitlysis_rscript_path is not None:
        p = Path(settings.bitlysis_rscript_path)
        if p.is_file():
            return str(p)
    return shutil.which("Rscript")


def run_r_pipeline_json(
    settings: Settings,
    df: pd.DataFrame,
    analyses: list[dict[str, Any]],
) -> tuple[dict[str, Any], str | None, int]:
    """Chạy phân tích qua R hoặc fallback Python.

    Returns:
        (parsed_result, stderr_text, returncode)
        - returncode=0 → thành công
        - returncode≠0 → lỗi
    """
    # Bước 1: Quyết định dùng R hay Python
    rscript = _find_rscript(settings) if settings.r_enabled else None

    if rscript is None:
        # Fallback: Python engine
        logger.debug(
            "r_pipeline: using Python psychometrics fallback (r_enabled=%s)",
            settings.r_enabled,
        )
        parsed = _py_psychometrics(df, analyses)
        # Ghi đè engine name để caller biết đây là fallback
        parsed["engine"] = _FALLBACK_ENGINE
        ok = bool(parsed.get("ok"))
        return parsed, None, 0 if ok else 1

    # Bước 2: Chạy Rscript thực sự
    pkg_root = resolve_r_package_root(settings)
    cli_script = pkg_root / "inst" / "cli" / "run_analysis.R"
    if not cli_script.is_file():
        logger.error("r_pipeline: CLI script không tìm thấy tại %s", cli_script)
        return (
            {
                "ok": False,
                "engine": "bitlysis_r_pipeline",
                "error": f"CLI script not found: {cli_script}",
                "results": [],
            },
            None,
            1,
        )

    with tempfile.TemporaryDirectory(prefix="bitlysis_r_") as tmpdir:
        tmp = Path(tmpdir)
        csv_path = tmp / "data.csv"
        req_path = tmp / "request.json"

        # Ghi DataFrame ra CSV
        df.to_csv(csv_path, index=False, encoding="utf-8")

        # Ghi request JSON
        request_payload = {
            "csv_path": str(csv_path),
            "analyses": analyses,
        }
        req_path.write_text(json.dumps(request_payload, ensure_ascii=False), encoding="utf-8")

        try:
            result = subprocess.run(
                [rscript, str(cli_script), str(req_path)],
                capture_output=True,
                text=True,
                encoding="utf-8",
                timeout=settings.r_subprocess_timeout_seconds,
                env={
                    **__import__("os").environ,
                    "BITLYSIS_R_PKG_ROOT": str(pkg_root),
                },
            )
        except subprocess.TimeoutExpired:
            logger.error(
                "r_pipeline: Rscript timeout after %ds",
                settings.r_subprocess_timeout_seconds,
            )
            return (
                {
                    "ok": False,
                    "engine": "bitlysis_r_pipeline",
                    "error": "Rscript timeout",
                    "results": [],
                },
                "Timeout",
                1,
            )
        except Exception as exc:  # noqa: BLE001
            logger.exception("r_pipeline: subprocess error")
            return (
                {"ok": False, "engine": "bitlysis_r_pipeline", "error": str(exc), "results": []},
                str(exc),
                1,
            )

        stderr = result.stderr or ""
        stdout = result.stdout or ""
        rc = result.returncode

        try:
            parsed = json.loads(stdout)
        except json.JSONDecodeError:
            logger.error(
                "r_pipeline: Rscript stdout không phải JSON: %s",
                stdout[:500],
            )
            return (
                {
                    "ok": False,
                    "engine": "bitlysis_r_pipeline",
                    "error": "Invalid JSON from Rscript",
                    "results": [],
                },
                stderr,
                1,
            )

        if stderr:
            logger.debug("r_pipeline stderr: %s", stderr[:2000])

        return parsed, stderr if stderr else None, rc


__all__ = [
    "resolve_r_package_root",
    "run_r_pipeline_json",
]
