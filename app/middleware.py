import logging
import secrets
import uuid
from collections.abc import Awaitable, Callable

from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import JSONResponse, Response
from starlette.types import ASGIApp

from app.config import Settings

logger = logging.getLogger(__name__)

PUBLIC_PATHS = frozenset({"/health", "/live", "/ready", "/docs", "/openapi.json", "/redoc"})


class RequestIdMiddleware(BaseHTTPMiddleware):
    async def dispatch(
        self,
        request: Request,
        call_next: Callable[[Request], Awaitable[Response]],
    ) -> Response:
        request_id = request.headers.get("x-request-id") or str(uuid.uuid4())
        request.state.request_id = request_id
        response = await call_next(request)
        response.headers["X-Request-ID"] = request_id
        return response


class ApiKeyMiddleware(BaseHTTPMiddleware):
    """Require X-API-Key when Settings.api_key is configured."""

    def __init__(self, app: ASGIApp, settings: Settings) -> None:
        super().__init__(app)
        self.settings = settings

    async def dispatch(
        self,
        request: Request,
        call_next: Callable[[Request], Awaitable[Response]],
    ) -> Response:
        if not self.settings.auth_enabled:
            return await call_next(request)

        if request.method == "OPTIONS" or request.url.path in PUBLIC_PATHS:
            return await call_next(request)

        provided = request.headers.get("x-api-key", "")
        expected = self.settings.api_key
        # compare_digest requires equal-length inputs; mismatch length ⇒ unauthorized.
        authorized = len(provided) == len(expected) and secrets.compare_digest(
            provided, expected
        )
        if not authorized:
            logger.warning("auth_failed path=%s", request.url.path)
            return JSONResponse(
                status_code=401,
                content={"detail": "Invalid or missing API key"},
            )
        return await call_next(request)
