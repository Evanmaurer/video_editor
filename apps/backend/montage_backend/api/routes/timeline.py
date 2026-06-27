from __future__ import annotations

from fastapi import APIRouter, Depends

from montage_backend.api.deps import get_timeline_service
from montage_backend.models.domain.timeline import (
    CreateTimelineRequest,
    SaveTimelineResponse,
    TimelineDocument,
    TimelineSummary,
)
from montage_backend.services.timeline_service import TimelineService

router = APIRouter(prefix="/projects", tags=["timelines"])


@router.get("/{project_id}/timelines", response_model=dict[str, list[TimelineSummary]])
async def list_timelines(
    project_id: str,
    service: TimelineService = Depends(get_timeline_service),
) -> dict[str, list[TimelineSummary]]:
    items = await service.list_timelines(project_id)
    return {"items": items}


@router.get("/{project_id}/timelines/active", response_model=TimelineDocument)
async def get_active_timeline(
    project_id: str,
    service: TimelineService = Depends(get_timeline_service),
) -> TimelineDocument:
    return await service.get_or_create_active(project_id)


@router.post("/{project_id}/timelines", response_model=TimelineDocument, status_code=201)
async def create_timeline(
    project_id: str,
    request: CreateTimelineRequest,
    service: TimelineService = Depends(get_timeline_service),
) -> TimelineDocument:
    return await service.create_timeline(project_id, request)


@router.get("/{project_id}/timelines/{timeline_id}", response_model=TimelineDocument)
async def get_timeline(
    project_id: str,
    timeline_id: str,
    service: TimelineService = Depends(get_timeline_service),
) -> TimelineDocument:
    return await service.get_timeline(project_id, timeline_id)


@router.put("/{project_id}/timelines/{timeline_id}", response_model=SaveTimelineResponse)
async def save_timeline(
    project_id: str,
    timeline_id: str,
    document: TimelineDocument,
    service: TimelineService = Depends(get_timeline_service),
) -> SaveTimelineResponse:
    if document.id != timeline_id:
        document = document.model_copy(update={"id": timeline_id})
    return await service.save_timeline(project_id, document)
