from __future__ import annotations

from fastapi import APIRouter, Depends, Response

from montage_backend.api.deps import get_metadata_service
from montage_backend.models.domain.metadata import (
    MediaMetadataSummary,
    MetadataFeatureKey,
    MetadataFeatureRecord,
    UpsertMetadataFeatureRequest,
)
from montage_backend.services.metadata_service import MetadataService

router = APIRouter(prefix="/projects", tags=["metadata"])


@router.get("/{project_id}/media/{media_id}/metadata", response_model=MediaMetadataSummary)
async def get_media_metadata(
    project_id: str,
    media_id: str,
    service: MetadataService = Depends(get_metadata_service),
) -> MediaMetadataSummary:
    return await service.get_metadata(project_id, media_id)


@router.get(
    "/{project_id}/media/{media_id}/metadata/{feature_key}",
    response_model=MetadataFeatureRecord,
)
async def get_media_metadata_feature(
    project_id: str,
    media_id: str,
    feature_key: MetadataFeatureKey,
    service: MetadataService = Depends(get_metadata_service),
) -> MetadataFeatureRecord:
    return await service.get_feature(project_id, media_id, feature_key)


@router.post(
    "/{project_id}/media/{media_id}/metadata/analyze",
    response_model=MediaMetadataSummary,
    status_code=202,
)
async def analyze_media_metadata(
    project_id: str,
    media_id: str,
    service: MetadataService = Depends(get_metadata_service),
) -> MediaMetadataSummary:
    await service.enqueue_analysis(project_id, media_id)
    return await service.get_metadata(project_id, media_id)


@router.put(
    "/{project_id}/media/{media_id}/metadata/{feature_key}",
    response_model=MetadataFeatureRecord,
)
async def upsert_media_metadata_feature(
    project_id: str,
    media_id: str,
    feature_key: MetadataFeatureKey,
    request: UpsertMetadataFeatureRequest,
    service: MetadataService = Depends(get_metadata_service),
) -> MetadataFeatureRecord:
    return await service.upsert_feature(project_id, media_id, feature_key, request)


@router.delete(
    "/{project_id}/media/{media_id}/metadata",
    status_code=204,
    response_class=Response,
)
async def invalidate_media_metadata(
    project_id: str,
    media_id: str,
    service: MetadataService = Depends(get_metadata_service),
) -> Response:
    await service.invalidate_metadata(project_id, media_id)
    return Response(status_code=204)
