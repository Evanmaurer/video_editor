from __future__ import annotations

from fastapi import APIRouter, Depends

from montage_backend.api.deps import get_playback_service
from montage_backend.models.domain.playback import (
    PlaybackClientMetrics,
    PlaybackDecodeRequest,
    PlaybackDecodeResponse,
    PlaybackMetricsResponse,
    PlaybackPrefetchRequest,
)
from montage_backend.playback.playback_service import PlaybackService

router = APIRouter(prefix="/projects", tags=["playback"])


@router.post(
    "/{project_id}/playback/decode",
    response_model=PlaybackDecodeResponse,
)
async def decode_playback_frame(
    project_id: str,
    request: PlaybackDecodeRequest,
    service: PlaybackService = Depends(get_playback_service),
) -> PlaybackDecodeResponse:
    result = await service.decode_frame(
        project_id,
        request.media_id,
        request.source_ms,
        request.frame_rate,
        request.quality,
    )
    return PlaybackDecodeResponse.model_validate(result)


@router.post("/{project_id}/playback/prefetch", status_code=202)
async def prefetch_playback_frames(
    project_id: str,
    request: PlaybackPrefetchRequest,
    service: PlaybackService = Depends(get_playback_service),
) -> dict[str, str]:
    await service.prefetch_frames(
        project_id,
        [item.model_dump() for item in request.requests],
        request.frame_rate,
    )
    return {"status": "accepted"}


@router.post("/{project_id}/playback/metrics")
async def report_playback_metrics(
    project_id: str,
    metrics: PlaybackClientMetrics,
    service: PlaybackService = Depends(get_playback_service),
) -> PlaybackMetricsResponse:
    service.update_client_metrics(
        playback_fps=metrics.playback_fps,
        dropped_frames=metrics.dropped_frames,
    )
    return PlaybackMetricsResponse.model_validate(service.get_metrics())


@router.get("/{project_id}/playback/metrics", response_model=PlaybackMetricsResponse)
async def get_playback_metrics(
    project_id: str,
    service: PlaybackService = Depends(get_playback_service),
) -> PlaybackMetricsResponse:
    return PlaybackMetricsResponse.model_validate(service.get_metrics())
