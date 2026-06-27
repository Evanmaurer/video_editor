from __future__ import annotations

import asyncio

import pytest
from httpx import AsyncClient

from montage_backend.api import deps
from montage_backend.models.domain import utc_now_iso
from montage_backend.models.domain.media import (
    ImportStatus,
    MediaItem,
    MediaRole,
    MediaType,
    ProcessingStatus,
    StorageMode,
)
from montage_backend.models.domain.metadata import MetadataFeatureKey, UpsertMetadataFeatureRequest
from montage_backend.services.metadata_service import MetadataService


async def _create_project(client: AsyncClient, project_root) -> str:
    create = await client.post(
        "/api/v1/projects",
        json={
            "name": "Metadata Test",
            "root_path": str(project_root),
            "width": 1920,
            "height": 1080,
            "frame_rate": 60,
            "target_game": "albion",
        },
    )
    assert create.status_code == 201
    return create.json()["id"]


@pytest.mark.asyncio
async def test_metadata_analyze_and_read(client: AsyncClient, tmp_path, monkeypatch):
    project_root = tmp_path / "metadata-project"
    project_id = await _create_project(client, project_root)

    source = project_root / "media" / "originals" / "media-1.mp4"
    source.parent.mkdir(parents=True, exist_ok=True)
    source.write_bytes(b"fake")

    media_service = deps.get_media_service()
    media = MediaItem(
        id="media-1",
        project_id=project_id,
        file_path=str(source),
        file_name="media-1.mp4",
        source_path=str(source),
        media_type=MediaType.VIDEO,
        role=MediaRole.CLIP,
        storage_mode=StorageMode.COPY,
        import_status=ImportStatus.READY,
        proxy_status=ProcessingStatus.READY,
        waveform_status=ProcessingStatus.READY,
        scene_status=ProcessingStatus.READY,
        metadata_status=ProcessingStatus.PENDING,
        duration_ms=5000,
        tags=[],
        is_favorite=False,
        created_at=utc_now_iso(),
        updated_at=utc_now_iso(),
    )

    session_factory = await media_service._project_service._ensure_project_db(project_root)
    async with session_factory() as session:
        await media_service._repo.create(session, media)

    metadata_service: MetadataService = deps.get_metadata_service()

    async def fake_analyze_full(project_id: str, media_id: str) -> None:
        await metadata_service.upsert_feature(
            project_id,
            media_id,
            MetadataFeatureKey.VISUAL,
            UpsertMetadataFeatureRequest(
                payload={
                    "scenes": [{"timestamp_ms": 1000, "score": 0.4}],
                    "motion_score": 0.42,
                    "camera_movement": {
                        "label": "slow",
                        "pan": 0.2,
                        "zoom": 0.1,
                        "shake": 0.05,
                    },
                    "brightness": {"mean": 120, "min": 20, "max": 220, "std": 15},
                    "color_histogram": {
                        "bins": 16,
                        "r": [0.0625] * 16,
                        "g": [0.0625] * 16,
                        "b": [0.0625] * 16,
                    },
                    "blur_score": 0.2,
                    "sharpness": 0.8,
                    "keyframes": [{"timestamp_ms": 0}],
                },
                confidence=0.9,
                reasoning="test",
            ),
        )
        await metadata_service.upsert_feature(
            project_id,
            media_id,
            MetadataFeatureKey.AUDIO,
            UpsertMetadataFeatureRequest(
                payload={
                    "loudness_lufs": -18.0,
                    "mean_volume_db": -18.0,
                    "max_volume_db": -3.0,
                    "peaks": [0.1, 0.8, 0.2],
                    "silence_regions": [],
                    "beat_markers": [{"timestamp_ms": 500, "strength": 0.7}],
                    "speech": {"has_speech": True, "speech_ratio": 0.8, "confidence": 0.7},
                },
            ),
        )
        await metadata_service.upsert_feature(
            project_id,
            media_id,
            MetadataFeatureKey.AI_CACHE,
            UpsertMetadataFeatureRequest(
                payload=metadata_service._extractor.empty_ai_cache().model_dump(),
            ),
        )

    async def fake_enqueue(project_id: str, media_id: str) -> None:
        await fake_analyze_full(project_id, media_id)

    monkeypatch.setattr(metadata_service, "enqueue_analysis", fake_enqueue)

    analyze = await client.post(f"/api/v1/projects/{project_id}/media/media-1/metadata/analyze")
    assert analyze.status_code == 202
    body = analyze.json()
    assert body["visual"]["motion_score"] == 0.42
    assert body["audio"]["speech"]["has_speech"] is True
    assert body["ai_cache"]["ocr_text"] is None

    feature = await client.get(
        f"/api/v1/projects/{project_id}/media/media-1/metadata/visual",
    )
    assert feature.status_code == 200
    assert feature.json()["feature_key"] == "visual"


@pytest.mark.asyncio
async def test_metadata_not_found(client: AsyncClient, tmp_path):
    project_id = await _create_project(client, tmp_path / "invalidate")
    missing = await client.get(f"/api/v1/projects/{project_id}/media/missing/metadata")
    assert missing.status_code == 404
