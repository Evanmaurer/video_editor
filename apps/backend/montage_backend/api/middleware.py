from __future__ import annotations

from fastapi import Request, Response
from starlette.middleware.base import BaseHTTPMiddleware, RequestResponseEndpoint

from montage_backend.config import settings


class AuthMiddleware(BaseHTTPMiddleware):
    async def dispatch(
        self, request: Request, call_next: RequestResponseEndpoint
    ) -> Response:
        if request.method == "OPTIONS":
            return await call_next(request)
        if request.url.path in ("/health", "/ready", "/docs", "/openapi.json", "/redoc"):
            return await call_next(request)
        token = request.headers.get("X-Montage-Token")
        if token != settings.auth_token:
            from fastapi.responses import JSONResponse

            return JSONResponse(status_code=401, content={"error": "UNAUTHORIZED"})
        return await call_next(request)
