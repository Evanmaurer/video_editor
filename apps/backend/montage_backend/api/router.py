from fastapi import APIRouter

from montage_backend.api.routes import projects, settings

api_router = APIRouter(prefix="/api/v1")
api_router.include_router(projects.router)
api_router.include_router(settings.router)
