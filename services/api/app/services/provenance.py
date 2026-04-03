"""run_manifest.json — phiên bản runtime & reproducibility (Phase 3)."""

from __future__ import annotations

import hashlib
import json
import platform
import sys
from datetime import UTC, datetime
from importlib.metadata import PackageNotFoundError, version
from pathlib import Path
from typing import Any


def _pkg_ver(name: str) -> str | None:
    try:
        return version(name)
    except PackageNotFoundError:
        return None


def renv_lock_sha256(repo_root: Path | None) -> str | None:
    if repo_root is None:
        return None
    lock = repo_root / "packages" / "r-pipeline" / "renv.lock"
    if not lock.is_file():
        return None
    h = hashlib.sha256(lock.read_bytes()).hexdigest()
    return f"sha256:{h}"


def infer_repo_root() -> Path | None:
    """Tìm root monorepo Bitlysis (chứa packages/r-pipeline)."""
    here = Path(__file__).resolve()
    for base in (Path.cwd(), *here.parents):
        if (base / "packages" / "r-pipeline").is_dir():
            return base
    return None


def build_run_manifest(
    job_id: str,
    profiling_engine_version: int,
    repo_root: Path | None = None,
) -> dict[str, Any]:
    root = repo_root or infer_repo_root()
    packages = {
        k: v
        for k in ("pandas", "numpy", "openpyxl")
        if (v := _pkg_ver(k)) is not None
    }
    return {
        "job_id": job_id,
        "generated_at": datetime.now(UTC).isoformat(),
        "profiling_engine_version": profiling_engine_version,
        "environment": {
            "python": sys.version.split()[0],
            "platform": platform.platform(),
            "packages": packages,
        },
        "renv_lock_sha256": renv_lock_sha256(root),
    }


def write_manifest(path: Path, data: dict[str, Any]) -> None:
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
