from __future__ import annotations

from fastapi import Request, Response
from starlette.middleware.base import BaseHTTPMiddleware, RequestResponseEndpoint

from montage_backend.config import settings
from montage_backend.models.domain import MontageError


class AuthMiddleware(BaseHTTPMiddleware):
    async def dispatch(
        self, request: Request, call_next: RequestResponseEndpoint
    ) -> Response:
        if request.url.path in ("/health", "/ready", "/docs", "/openapi.json", "/redoc"):
            return await call_next(request)
        token = request.headers.get("X-Montage-Token")
        if token != settings.auth_token:
            from fastapi.responses import JSONResponse

            return JSONResponse(status_code=401, content={"error": "UNAUTHORIZED"})
        return await call_next(request)


async def montage_error_handler(_request: Request, exc: MontageError) -> Response:
    from fastapi.responses import JSONResponse

    status = 404 if "NOT_FOUND" in exc.code else 400
    return JSONResponse(
        status_code=status,
        content={"error": exc.code, "message": exc.message, "details": exc.details},
    )
