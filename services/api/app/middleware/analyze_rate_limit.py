"""Rate limiting cho các endpoint analyze tốn kém (LLM calls).

Áp dụng cho:
- POST /v1/web/analyze    → 10 req / 60s / IP
- POST /v1/jobs/{id}/analyze → 5 req / 300s / IP

Cấu hình qua Settings:
    ANALYZE_RATE_LIMIT_ENABLED=true
    WEB_ANALYZE_RATE_LIMIT_MAX_REQUESTS=10
    WEB_ANALYZE_RATE_LIMIT_WINDOW_SECONDS=60
    JOB_ANALYZE_RATE_LIMIT_MAX_REQUESTS=5
    JOB_ANALYZE_RATE_LIMIT_WINDOW_SECONDS=300
"""

from __future__ import annotations

import re
import time
import uuid
from collections import defaultdict, deque
from collections.abc import Callable

from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import JSONResponse, Response

from app.config import Settings, get_settings

_hist: dict[str, deque[float]] = defaultdict(deque)

# Pattern để detect /v1/jobs/{uuid}/analyze
_JOB_ANALYZE_PATTERN = re.compile(r"^/v1/jobs/[^/]+/analyze$")


def _settings(request: Request) -> Settings:
    """Ưu tiên dependency override (test) trước, fallback về app.state, cuối là module-level."""
    # Thử lấy override của get_settings (used in tests via app.dependency_overrides)
    overrides = getattr(request.app, "dependency_overrides", {})
    if get_settings in overrides:
        return overrides[get_settings]()
    s = getattr(request.app.state, "settings", None)
    return s if isinstance(s, Settings) else get_settings()


def _prune(dq: deque[float], now: float, window: float) -> None:
    while dq and dq[0] < now - window:
        dq.popleft()


def _get_client_ip(request: Request) -> str:
    forwarded = request.headers.get("x-forwarded-for")
    if forwarded:
        return forwarded.split(",")[0].strip()
    return request.client.host if request.client else "unknown"


class AnalyzeRateLimitMiddleware(BaseHTTPMiddleware):
    """Rate limiting cho POST /v1/web/analyze và POST /v1/jobs/{id}/analyze."""

    async def dispatch(
        self,
        request: Request,
        call_next: Callable[[Request], Response],
    ) -> Response:
        settings = _settings(request)
        # Bypass trong môi trường testing hoặc khi đã tắt
        if settings.testing or not settings.analyze_rate_limit_enabled:
            return await call_next(request)

        if request.method != "POST":
            return await call_next(request)

        path = request.url.path
        is_web_analyze = path == "/v1/web/analyze"
        is_job_analyze = bool(_JOB_ANALYZE_PATTERN.match(path))

        if not is_web_analyze and not is_job_analyze:
            return await call_next(request)

        now = time.monotonic()
        client_ip = _get_client_ip(request)

        if is_web_analyze:
            window = float(settings.web_analyze_rate_limit_window_seconds)
            max_req = settings.web_analyze_rate_limit_max_requests
            key = f"web_analyze:{client_ip}"
        else:  # job analyze
            window = float(settings.job_analyze_rate_limit_window_seconds)
            max_req = settings.job_analyze_rate_limit_max_requests
            key = f"job_analyze:{client_ip}"

        dq = _hist[key]
        _prune(dq, now, window)
        if len(dq) >= max_req:
            rid = getattr(request.state, "request_id", None) or str(uuid.uuid4())
            return JSONResponse(
                status_code=429,
                content={
                    "code": "analyze_rate_limited",
                    "message": "Quá nhiều yêu cầu phân tích. Vui lòng đợi một lúc rồi thử lại.",
                    "details": {"window_seconds": window, "max_requests": max_req},
                    "request_id": rid,
                },
                headers={"X-Request-Id": rid},
            )
        dq.append(now)
        return await call_next(request)
