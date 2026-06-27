from fastapi import APIRouter, Depends

from montage_backend.api.deps import ensure_database_started
from montage_backend.api.routes import media, metadata, playback, projects, render, settings, timeline

api_router = APIRouter(
    prefix="/api/v1",
    dependencies=[Depends(ensure_database_started)],
)
api_router.include_router(media.router)
api_router.include_router(metadata.router)
api_router.include_router(playback.router)
api_router.include_router(render.router)
api_router.include_router(timeline.router)
api_router.include_router(projects.router)
api_router.include_router(settings.router)
