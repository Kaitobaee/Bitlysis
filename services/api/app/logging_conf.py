"""Logging gợi ý cho Bitlysis (key=value trên một dòng)."""

from __future__ import annotations

import logging
import sys
from typing import Any


def configure_logging(level: int = logging.INFO) -> None:
    root = logging.getLogger()
    if root.handlers:
        return
    handler = logging.StreamHandler(sys.stdout)
    handler.setFormatter(
        logging.Formatter(
            fmt="%(levelname)s %(name)s %(message)s",
        ),
    )
    root.addHandler(handler)
    root.setLevel(level)


def log_event(logger: logging.Logger, event: str, **fields: Any) -> None:
    parts = " ".join(f"{k}={v!r}" for k, v in sorted(fields.items()) if v is not None)
    logger.info("%s %s", event, parts)
