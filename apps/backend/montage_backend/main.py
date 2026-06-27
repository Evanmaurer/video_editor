from __future__ import annotations

import json
import socket
from contextlib import asynccontextmanager

import uvicorn
from fastapi import FastAPI, WebSocket, WebSocketDisconnect

from montage_backend import __version__
from montage_backend.api.deps import get_project_service, get_settings_service
from montage_backend.api.middleware import AuthMiddleware, montage_error_handler
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
    yield
    await db_manager.shutdown()
    logger.info("backend_stopped")


app = FastAPI(title="MontageAI Backend", version=__version__, lifespan=lifespan)
app.add_middleware(AuthMiddleware)
app.add_exception_handler(MontageError, montage_error_handler)
app.include_router(api_router)


@app.get("/health")
async def health() -> dict[str, object]:
    settings_service = AppSettingsService(db_manager.app_session_factory)
    project_service = ProjectService(db_manager.app_session_factory)
    app_settings = await settings_service.get_settings()
    gpu = project_service.get_gpu_info(app_settings.gpu_enabled)
    ai_status = await llm_service.get_status()
    return {
        "status": "ok",
        "version": __version__,
        "models_loaded": False,
        "queue_depth": 0,
        "gpu_available": gpu.available,
        "gpu_name": gpu.name,
        "cpu_only_mode": not gpu.available,
        "performance_note": gpu.cpu_only_warning,
        "ai_chat_enabled": ai_status.chat_enabled,
    }


@app.get("/ready")
async def ready() -> dict[str, str]:
    return {"status": "ready"}


@app.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket) -> None:
    token = websocket.query_params.get("token")
    if token != settings.auth_token:
        await websocket.close(code=1008)
        return
    await websocket.accept()
    try:
        while True:
            await websocket.receive_text()
    except WebSocketDisconnect:
        pass


def _find_free_port(host: str) -> int:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
        sock.bind((host, 0))
        return sock.getsockname()[1]


def main() -> None:
    configure_logging()
    port = settings.port if settings.port > 0 else _find_free_port(settings.host)
    ready = {"port": port, "token": settings.auth_token}
    print(json.dumps(ready), flush=True)
    uvicorn.run(app, host=settings.host, port=port, log_level=settings.log_level.lower())


if __name__ == "__main__":
    main()
