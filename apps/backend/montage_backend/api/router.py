from fastapi import APIRouter, Depends

from montage_backend.api.deps import ensure_database_started
from montage_backend.api.routes import projects, settings

api_router = APIRouter(
    prefix="/api/v1",
    dependencies=[Depends(ensure_database_started)],
)
api_router.include_router(projects.router)
api_router.include_router(settings.router)
