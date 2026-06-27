from __future__ import annotations

import traceback

from fastapi import Request
from fastapi.responses import JSONResponse
from sqlalchemy.exc import SQLAlchemyError

from montage_backend.logging import get_logger
from montage_backend.models.domain import MontageError

logger = get_logger(__name__)


async def montage_error_handler(_request: Request, exc: MontageError) -> JSONResponse:
    if "NOT_FOUND" in exc.code:
        status = 404
    elif exc.code == "PROJECT_ALREADY_EXISTS":
        status = 409
    elif exc.code == "PROCESSING_CANCELLED":
        status = 409
    else:
        status = 400
    return JSONResponse(
        status_code=status,
        content={"error": exc.code, "message": exc.message, "details": exc.details},
    )


async def sqlalchemy_error_handler(_request: Request, exc: SQLAlchemyError) -> JSONResponse:
    logger.error(
        "database_error",
        error_type=type(exc).__name__,
        message=str(exc),
        traceback=traceback.format_exc(),
    )
    return JSONResponse(
        status_code=500,
        content={
            "error": "DATABASE_ERROR",
            "message": str(exc),
            "details": {"type": type(exc).__name__},
        },
    )


async def unhandled_exception_handler(request: Request, exc: Exception) -> JSONResponse:
    tb = traceback.format_exc()
    logger.error(
        "unhandled_exception",
        error_type=type(exc).__name__,
        message=str(exc),
        path=request.url.path,
        method=request.method,
        traceback=tb,
    )
    return JSONResponse(
        status_code=500,
        content={
            "error": "INTERNAL_SERVER_ERROR",
            "message": str(exc),
            "details": {
                "type": type(exc).__name__,
                "path": request.url.path,
            },
        },
    )
