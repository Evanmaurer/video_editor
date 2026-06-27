from __future__ import annotations

from fastapi import APIRouter, Depends

from montage_backend.api.deps import get_project_service
from montage_backend.models.domain import (
    CreateProjectRequest,
    OpenProjectRequest,
    Project,
    ProjectSummary,
)
from montage_backend.services.project_service import ProjectService

router = APIRouter(prefix="/projects", tags=["projects"])


@router.post("", response_model=Project, status_code=201)
async def create_project(
    request: CreateProjectRequest,
    service: ProjectService = Depends(get_project_service),
) -> Project:
    return await service.create_project(request)


@router.post("/open", response_model=Project)
async def open_project(
    request: OpenProjectRequest,
    service: ProjectService = Depends(get_project_service),
) -> Project:
    return await service.open_project(request.path)


@router.get("/recent", response_model=dict[str, list[ProjectSummary]])
async def list_recent_projects(
    service: ProjectService = Depends(get_project_service),
) -> dict[str, list[ProjectSummary]]:
    items = await service.get_recent_projects()
    return {"items": items}


@router.get("/{project_id}", response_model=Project)
async def get_project(
    project_id: str,
    service: ProjectService = Depends(get_project_service),
) -> Project:
    return await service.get_project(project_id)


@router.put("/{project_id}", response_model=Project)
async def update_project(
    project_id: str,
    project: Project,
    service: ProjectService = Depends(get_project_service),
) -> Project:
    if project.id != project_id:
        from montage_backend.models.domain import InvalidProjectError

        raise InvalidProjectError("Project ID mismatch")
    return await service.save_project(project)


@router.post("/{project_id}/close")
async def close_project(
    project_id: str,
    service: ProjectService = Depends(get_project_service),
) -> dict[str, str]:
    await service.close_project(project_id)
    return {"status": "closed"}
