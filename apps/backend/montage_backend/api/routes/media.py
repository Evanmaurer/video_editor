from __future__ import annotations

from pathlib import Path

from fastapi import APIRouter, Depends, HTTPException, Query, Response
from fastapi.responses import FileResponse

from montage_backend.api.deps import get_media_service
from montage_backend.media.paths import expand_import_paths
from montage_backend.models.domain.media import (
    ImportFolderRequest,
    ImportMediaRequest,
    ImportMediaResponse,
    MediaItem,
    MediaListQuery,
    MediaRole,
    MediaSortField,
    MediaSortOrder,
    StorageMode,
    UpdateMediaRequest,
)
from montage_backend.services.media_service import MediaService

router = APIRouter(prefix="/projects", tags=["media"])


@router.get("/{project_id}/media", response_model=dict[str, list[MediaItem]])
async def list_media(
    project_id: str,
    search: str | None = None,
    sort_by: MediaSortField = MediaSortField.CREATED_AT,
    sort_order: MediaSortOrder = MediaSortOrder.DESC,
    tags: list[str] = Query(default=[]),
    favorites_only: bool = False,
    service: MediaService = Depends(get_media_service),
) -> dict[str, list[MediaItem]]:
    query = MediaListQuery(
        search=search,
        sort_by=sort_by,
        sort_order=sort_order,
        tags=tags,
        favorites_only=favorites_only,
    )
    items = await service.list_media(project_id, query)
    return {"items": items}


@router.get("/{project_id}/media/{media_id}", response_model=MediaItem)
async def get_media_item(
    project_id: str,
    media_id: str,
    service: MediaService = Depends(get_media_service),
) -> MediaItem:
    return await service.get_media_item(project_id, media_id)


@router.get("/{project_id}/media/{media_id}/thumbnail")
async def get_media_thumbnail(
    project_id: str,
    media_id: str,
    service: MediaService = Depends(get_media_service),
) -> FileResponse:
    media = await service.get_media_item(project_id, media_id)
    if not media.thumbnail_path:
        raise HTTPException(status_code=404, detail="Thumbnail not available")

    thumbnail = Path(media.thumbnail_path)
    if not thumbnail.is_file():
        raise HTTPException(status_code=404, detail="Thumbnail file missing")

    media_type = "image/jpeg"
    if thumbnail.suffix.lower() == ".png":
        media_type = "image/png"
    elif thumbnail.suffix.lower() == ".webp":
        media_type = "image/webp"

    return FileResponse(thumbnail, media_type=media_type)


@router.post(
    "/{project_id}/media/import",
    response_model=ImportMediaResponse,
    status_code=202,
)
async def import_media(
    project_id: str,
    request: ImportMediaRequest,
    response: Response,
    wait: bool = Query(False, description="Block until all imports finish"),
    service: MediaService = Depends(get_media_service),
) -> ImportMediaResponse:
    result = await service.import_files(
        project_id,
        request.paths,
        request.role,
        request.storage_mode,
        wait=wait,
    )
    if wait:
        response.status_code = 200
    return result


@router.post(
    "/{project_id}/media/import-folder",
    response_model=ImportMediaResponse,
    status_code=202,
)
async def import_media_folder(
    project_id: str,
    request: ImportFolderRequest,
    response: Response,
    wait: bool = Query(False, description="Block until all imports finish"),
    service: MediaService = Depends(get_media_service),
) -> ImportMediaResponse:
    sources = [str(path) for path in expand_import_paths([request.path])]
    result = await service.import_files(
        project_id,
        sources,
        request.role,
        request.storage_mode,
        wait=wait,
    )
    if wait:
        response.status_code = 200
    return result


@router.patch("/{project_id}/media/{media_id}", response_model=MediaItem)
async def update_media_item(
    project_id: str,
    media_id: str,
    request: UpdateMediaRequest,
    service: MediaService = Depends(get_media_service),
) -> MediaItem:
    return await service.update_media(project_id, media_id, request)


@router.delete(
    "/{project_id}/media/{media_id}",
    status_code=204,
    response_class=Response,
)
async def delete_media_item(
    project_id: str,
    media_id: str,
    service: MediaService = Depends(get_media_service),
) -> Response:
    await service.delete_media(project_id, media_id)
    return Response(status_code=204)


@router.post("/{project_id}/media/{media_id}/cancel")
async def cancel_media_import(
    project_id: str,
    media_id: str,
    service: MediaService = Depends(get_media_service),
) -> dict[str, str]:
    await service.get_media_item(project_id, media_id)
    await service.cancel_import(media_id)
    return {"status": "cancelled"}
