from __future__ import annotations

from fastapi import APIRouter, Depends

from montage_backend.api.deps import get_render_service
from montage_backend.models.domain.render import (
    RenderJobDetail,
    RenderJobSummary,
    RenderLogResponse,
    RenderPresetInfo,
    StartRenderRequest,
)
from montage_backend.services.render_service import RenderService

router = APIRouter(prefix="/projects", tags=["render"])


@router.get("/{project_id}/render/presets", response_model=list[RenderPresetInfo])
async def list_render_presets(
    project_id: str,
    service: RenderService = Depends(get_render_service),
) -> list[RenderPresetInfo]:
    _ = project_id
    return await service.list_presets()


@router.post("/{project_id}/render", response_model=RenderJobSummary, status_code=202)
async def start_render(
    project_id: str,
    request: StartRenderRequest,
    service: RenderService = Depends(get_render_service),
) -> RenderJobSummary:
    return await service.start_render(project_id, request)


@router.get("/{project_id}/render/jobs", response_model=list[RenderJobSummary])
async def list_render_jobs(
    project_id: str,
    service: RenderService = Depends(get_render_service),
) -> list[RenderJobSummary]:
    return await service.list_jobs(project_id)


@router.get("/{project_id}/render/jobs/{job_id}", response_model=RenderJobDetail)
async def get_render_job(
    project_id: str,
    job_id: str,
    service: RenderService = Depends(get_render_service),
) -> RenderJobDetail:
    return await service.get_job(project_id, job_id)


@router.get("/{project_id}/render/jobs/{job_id}/logs", response_model=RenderLogResponse)
async def get_render_logs(
    project_id: str,
    job_id: str,
    service: RenderService = Depends(get_render_service),
) -> RenderLogResponse:
    return await service.get_logs(project_id, job_id)


@router.post("/{project_id}/render/jobs/{job_id}/pause", response_model=RenderJobSummary)
async def pause_render_job(
    project_id: str,
    job_id: str,
    service: RenderService = Depends(get_render_service),
) -> RenderJobSummary:
    return await service.pause_job(project_id, job_id)


@router.post("/{project_id}/render/jobs/{job_id}/resume", response_model=RenderJobSummary)
async def resume_render_job(
    project_id: str,
    job_id: str,
    service: RenderService = Depends(get_render_service),
) -> RenderJobSummary:
    return await service.resume_job(project_id, job_id)


@router.post("/{project_id}/render/jobs/{job_id}/cancel", response_model=RenderJobSummary)
async def cancel_render_job(
    project_id: str,
    job_id: str,
    service: RenderService = Depends(get_render_service),
) -> RenderJobSummary:
    return await service.cancel_job(project_id, job_id)
