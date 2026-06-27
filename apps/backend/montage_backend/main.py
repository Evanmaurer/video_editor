from __future__ import annotations

import json
import socket
from contextlib import asynccontextmanager

import uvicorn
from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware

from sqlalchemy.exc import SQLAlchemyError

from montage_backend import __version__
from montage_backend.api.deps import get_media_service, get_project_service, get_render_service, get_settings_service
from montage_backend.media.ffmpeg_tools import detect_ffmpeg
from montage_backend.api.exception_handlers import (
    montage_error_handler,
    sqlalchemy_error_handler,
    unhandled_exception_handler,
)
from montage_backend.api.middleware import AuthMiddleware
from montage_backend.api.router import api_router
from montage_backend.config import settings
from montage_backend.database import db_manager
from montage_backend.logging import configure_logging, get_logger
from montage_backend.models.domain import MontageError
from montage_backend.services.llm_service import llm_service
from montage_backend.services.project_service import AppSettingsService, ProjectService

logger = get_logger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    configure_logging()
    await db_manager.startup()
    settings_service = AppSettingsService(db_manager.app_session_factory)
    app_settings = await settings_service.get_settings()
    await llm_service.configure(app_settings.llm)
    logger.info("backend_started", version=__version__)

    if _runtime_port > 0:
        ready = {
            "port": _runtime_port,
            "host": settings.host,
            "token": settings.auth_token,
        }
        print(json.dumps(ready), flush=True)

    yield
    from montage_backend.api.deps import get_playback_service, get_render_service

    try:
        await get_playback_service().shutdown()
    except Exception:
        logger.exception("playback_shutdown_failed")
    try:
        await get_render_service().shutdown()
    except Exception:
        logger.exception("render_shutdown_failed")
    await db_manager.shutdown()
    logger.info("backend_stopped")


_runtime_port: int = 0


app = FastAPI(title="MontageAI Backend", version=__version__, lifespan=lifespan)
# Electron dev loads the renderer from http://localhost:<vite-port> while the backend
# binds to http://127.0.0.1:<port>. Without CORS, browser fetch returns "Failed to fetch".
# Production loads file:// (Origin: null). Backend is local-only (127.0.0.1).
app.add_middleware(
    CORSMiddleware,
    allow_origins=["null"],
    allow_origin_regex=r"https?://(localhost|127\.0\.0\.1)(:\d+)?",
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)
app.add_middleware(AuthMiddleware)
app.add_exception_handler(MontageError, montage_error_handler)
app.add_exception_handler(SQLAlchemyError, sqlalchemy_error_handler)
app.add_exception_handler(Exception, unhandled_exception_handler)
app.include_router(api_router)


@app.get("/health")
async def health() -> dict[str, object]:
    settings_service = AppSettingsService(db_manager.app_session_factory)
    project_service = ProjectService(db_manager.app_session_factory)
    app_settings = await settings_service.get_settings()
    gpu = project_service.get_gpu_info(app_settings.gpu_enabled)
    ai_status = await llm_service.get_status()
    media_service = get_media_service()
    render_service = get_render_service()
    ffmpeg = detect_ffmpeg(
        media_service.processor.runner.ffmpeg_bin,
        media_service.processor.runner.ffprobe_bin,
    )
    return {
        "status": "ok",
        "version": __version__,
        "features": ["media_library", "playback", "export", "metadata"],
        "models_loaded": False,
        "queue_depth": media_service.queue.active_count,
        "export_queue_depth": render_service.queue_depth,
        "ffmpeg_available": ffmpeg.available,
        "ffmpeg_note": ffmpeg.message,
        "gpu_available": gpu.available,
        "gpu_name": gpu.name,
        "cpu_only_mode": not gpu.available,
        "performance_note": gpu.cpu_only_warning,
        "ai_chat_enabled": ai_status.chat_enabled,
    }


@app.get("/ready")
async def ready() -> dict[str, str]:
    return {"status": "ready"}


from montage_backend.ws.hub import ws_hub


@app.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket) -> None:
    token = websocket.query_params.get("token")
    if token != settings.auth_token:
        await websocket.close(code=1008)
        return
    await websocket.accept()
    await ws_hub.connect(websocket)
    try:
        while True:
            await websocket.receive_text()
    except WebSocketDisconnect:
        pass
    finally:
        await ws_hub.disconnect(websocket)


def _find_free_port(host: str) -> int:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
        sock.bind((host, 0))
        return sock.getsockname()[1]


def main() -> None:
    global _runtime_port
    configure_logging()
    _runtime_port = settings.port if settings.port > 0 else _find_free_port(settings.host)
    uvicorn.run(app, host=settings.host, port=_runtime_port, log_level=settings.log_level.lower())


if __name__ == "__main__":
    main()
