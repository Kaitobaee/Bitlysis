"""Giới hạn số request POST /v1/upload theo IP (sliding window)."""

from __future__ import annotations

import time
import uuid
from collections import defaultdict, deque
from collections.abc import Callable

from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import JSONResponse, Response

from app.config import Settings, get_settings

_hist: dict[str, deque[float]] = defaultdict(deque)


def _settings(request: Request) -> Settings:
    s = getattr(request.app.state, "settings", None)
    return s if isinstance(s, Settings) else get_settings()


def _prune(dq: deque[float], now: float, window: float) -> None:
    while dq and dq[0] < now - window:
        dq.popleft()


class UploadRateLimitMiddleware(BaseHTTPMiddleware):
    """Chỉ áp dụng cho POST /v1/upload."""

    async def dispatch(
        self,
        request: Request,
        call_next: Callable[[Request], Response],
    ) -> Response:
        settings = _settings(request)
        if not settings.upload_rate_limit_enabled:
            return await call_next(request)
        if request.method != "POST" or request.url.path != "/v1/upload":
            return await call_next(request)

        now = time.monotonic()
        window = float(settings.upload_rate_limit_window_seconds)
        max_req = settings.upload_rate_limit_max_requests
        client = request.client.host if request.client else "unknown"
        forwarded = request.headers.get("x-forwarded-for")
        if forwarded:
            client = forwarded.split(",")[0].strip() or client

        dq = _hist[client]
        _prune(dq, now, window)
        if len(dq) >= max_req:
            rid = getattr(request.state, "request_id", None) or str(uuid.uuid4())
            return JSONResponse(
                status_code=429,
                content={
                    "code": "rate_limited",
                    "message": "Quá nhiều upload trong khoảng thời gian cho phép",
                    "details": {"window_seconds": window, "max_requests": max_req},
                    "request_id": rid,
                },
                headers={"X-Request-Id": rid},
            )
        dq.append(now)
        return await call_next(request)
