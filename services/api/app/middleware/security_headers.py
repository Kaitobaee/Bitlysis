"""Security headers — API layer (khác Vercel edge / CDN)."""

from __future__ import annotations

from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import Response

from app.config import Settings


class SecurityHeadersMiddleware(BaseHTTPMiddleware):
    def __init__(self, app, settings: Settings) -> None:
        super().__init__(app)
        self._settings = settings

    async def dispatch(self, request: Request, call_next) -> Response:
        response = await call_next(request)
        response.headers.setdefault("X-Content-Type-Options", "nosniff")
        response.headers.setdefault(
            "Referrer-Policy",
            "strict-origin-when-cross-origin",
        )
        if self._settings.app_environment == "production":
            response.headers.setdefault(
                "Permissions-Policy",
                (
                    "accelerometer=(), camera=(), geolocation=(), gyroscope=(), "
                    "magnetometer=(), microphone=(), payment=(), usb=()"
                ),
            )
            response.headers.setdefault("X-Frame-Options", "DENY")
        return response
