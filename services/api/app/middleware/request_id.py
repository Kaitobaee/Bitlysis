from __future__ import annotations

import uuid
from collections.abc import Callable

from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import Response


class RequestIdMiddleware(BaseHTTPMiddleware):
    """Gắn X-Request-Id (UUID) cho mọi request; echo header trên response."""

    header_name = "X-Request-Id"

    async def dispatch(
        self,
        request: Request,
        call_next: Callable[[Request], Response],
    ) -> Response:
        incoming = request.headers.get(self.header_name)
        rid = incoming.strip() if incoming and incoming.strip() else str(uuid.uuid4())
        request.state.request_id = rid
        response = await call_next(request)
        response.headers[self.header_name] = rid
        return response
