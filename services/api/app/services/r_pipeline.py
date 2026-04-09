"""Phase 5 — gọi R pipeline (Cronbach, EFA, PLS-SEM) qua Rscript: timeout + stderr."""

from __future__ import annotations

import json
import logging
import os
import shutil
import subprocess
import tempfile
from pathlib import Path
from typing import Any

import pandas as pd

from app.config import Settings

logger = logging.getLogger(__name__)


def _parse_json_from_stdout(stdout: str) -> dict[str, Any] | None:
    text = (stdout or "").strip()
    if not text:
        return None

    # Prefer the last valid JSON line: some scripts print progress metadata
    # and then the final payload as a separate JSON object.
    lines = [ln.strip() for ln in text.splitlines() if ln.strip()]
    for line in reversed(lines):
        if not (line.startswith("{") and line.endswith("}")):
            continue
        try:
            obj = json.loads(line)
            if isinstance(obj, dict):
                return obj
        except json.JSONDecodeError:
            continue

    try:
        return json.loads(text)
    except json.JSONDecodeError:
        pass

    # Some R packages may print messages before/after payload; try to recover
    # by scanning for a JSON object tail in stdout.
    first = text.find("{")
    last = text.rfind("}")
    if first == -1 or last == -1 or last <= first:
        return None

    candidate = text[first : last + 1]
    try:
        return json.loads(candidate)
    except json.JSONDecodeError:
        return None


def _repo_root() -> Path:
    # Bitlysis/services/api/app/services/r_pipeline.py → repo root = parents[4]
    return Path(__file__).resolve().parents[4]


def resolve_r_package_root(settings: Settings) -> Path:
    if settings.r_package_root is not None:
        return Path(settings.r_package_root).resolve()
    return (_repo_root() / "packages" / "r-pipeline").resolve()


def resolve_rscript(settings: Settings) -> str:
    configured = settings.bitlysis_rscript_path
    if configured is not None:
        path = str(configured).strip()
        if path:
            return path

    path = os.environ.get("BITLYSIS_RSCRIPT_PATH") or ""
    if path.strip():
        return path.strip()
    w = shutil.which("Rscript")
    if not w:
        msg = "Không tìm thấy Rscript trên PATH (hoặc đặt BITLYSIS_RSCRIPT_PATH)."
        raise FileNotFoundError(msg)
    return w


def run_r_pipeline_json(
    settings: Settings,
    df: pd.DataFrame,
    analyses: list[dict[str, Any]],
) -> tuple[dict[str, Any], str, int]:
    """
    Xuất DataFrame ra CSV tạm, gọi inst/cli/run_analysis.R.
    Trả về (parsed_stdout_json, stderr_text, returncode).
    """
    r_root = resolve_r_package_root(settings)
    cli = r_root / "inst" / "cli" / "run_analysis.R"
    if not cli.is_file():
        msg = f"Thiếu R CLI: {cli}"
        raise FileNotFoundError(msg)

    rscript = resolve_rscript(settings)
    csv_path: str | None = None
    req_path: str | None = None
    try:
        with tempfile.NamedTemporaryFile(
            mode="w",
            suffix=".csv",
            delete=False,
            encoding="utf-8",
            newline="",
        ) as cf:
            csv_path = cf.name
            df.to_csv(csv_path, index=False)

        payload: dict[str, Any] = {
            "version": 1,
            "csv_path": os.path.abspath(csv_path),
            "analyses": analyses,
        }
        with tempfile.NamedTemporaryFile(
            mode="w",
            suffix=".json",
            delete=False,
            encoding="utf-8",
        ) as jf:
            req_path = jf.name
            json.dump(payload, jf, ensure_ascii=False)

        env = os.environ.copy()
        env["BITLYSIS_R_PKG_ROOT"] = str(r_root)

        try:
            proc = subprocess.run(
                [rscript, str(cli), req_path],
                capture_output=True,
                text=True,
                timeout=settings.r_subprocess_timeout_seconds,
                env=env,
                check=False,
            )
        except subprocess.TimeoutExpired as e:
            err = (e.stderr or "") if e.stderr is not None else ""
            out = (e.stdout or "") if e.stdout is not None else ""
            return (
                {
                    "ok": False,
                    "engine": "bitlysis_r_pipeline",
                    "error": f"R subprocess timeout sau {settings.r_subprocess_timeout_seconds}s",
                    "partial_stdout": out[:4000],
                },
                err,
                -9,
            )

        stderr = proc.stderr or ""
        stdout = proc.stdout or ""
        if proc.stdout:
            parsed_candidate = _parse_json_from_stdout(stdout)
            if parsed_candidate is not None:
                parsed = parsed_candidate
            else:
                parsed = {
                    "ok": False,
                    "engine": "bitlysis_r_pipeline",
                    "error": "R stdout không phải JSON",
                    "raw_stdout": stdout[:8000],
                }
        else:
            parsed = {
                "ok": False,
                "engine": "bitlysis_r_pipeline",
                "error": "R không ghi stdout",
                "stderr": stderr[:8000],
            }

        if stderr.strip():
            logger.warning("R stderr (pipeline): %s", stderr[:2000])
        return parsed, stderr, proc.returncode
    finally:
        if csv_path:
            Path(csv_path).unlink(missing_ok=True)
        if req_path:
            Path(req_path).unlink(missing_ok=True)
