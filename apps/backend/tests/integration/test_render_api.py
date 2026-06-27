from __future__ import annotations

import asyncio

import pytest
from httpx import AsyncClient

from montage_backend.api import deps
from montage_backend.models.domain import utc_now_iso
from montage_backend.models.domain.media import ImportStatus, MediaItem, MediaRole, MediaType, ProcessingStatus, StorageMode
from montage_backend.models.domain.render import RenderJobStatus
from montage_backend.services.render_service import RenderService


async def _create_project(client: AsyncClient, project_root) -> str:
    create = await client.post(
        "/api/v1/projects",
        json={
            "name": "Render Test",
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
async def test_render_presets(client: AsyncClient):
    response = await client.get("/api/v1/projects/demo/render/presets")
    assert response.status_code == 200
    presets = response.json()
    assert any(item["id"] == "h264_1080p60" for item in presets)
    assert all(item["width"] > 0 for item in presets)


@pytest.mark.asyncio
async def test_start_render_queues_job(client: AsyncClient, tmp_path, monkeypatch):
    project_root = tmp_path / "project"
    project_id = await _create_project(client, project_root)

    active = await client.get(f"/api/v1/projects/{project_id}/timelines/active")
    doc = active.json()
    timeline_id = doc["id"]
    track_id = doc["tracks"][0]["id"]
    doc["tracks"][0]["clips"] = [
        {
            "id": "clip-1",
            "media_item_id": "media-1",
            "track_id": track_id,
            "start_ms": 0,
            "end_ms": 1000,
            "source_in_ms": 0,
            "source_out_ms": 1000,
            "speed": 1.0,
            "opacity": 1.0,
        },
    ]
    doc["duration_ms"] = 1000
    save = await client.put(
        f"/api/v1/projects/{project_id}/timelines/{timeline_id}",
        json=doc,
    )
    assert save.status_code == 200

    source = project_root / "media" / "originals" / "media-1.mp4"
    source.parent.mkdir(parents=True, exist_ok=True)
    source.write_bytes(b"fake")

    media_service = deps.get_media_service()

    async def fake_get_media_item(pid: str, media_id: str) -> MediaItem:
        return MediaItem(
            id=media_id,
            project_id=pid,
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
            tags=[],
            is_favorite=False,
            created_at=utc_now_iso(),
            updated_at=utc_now_iso(),
        )

    monkeypatch.setattr(media_service, "get_media_item", fake_get_media_item)

    render_service: RenderService = deps.get_render_service()

    async def fake_run(*args, **kwargs):
        return ""

    monkeypatch.setattr(render_service._runner, "run", fake_run)

    start = await client.post(
        f"/api/v1/projects/{project_id}/render",
        json={"preset_id": "h264_1080p60"},
    )
    assert start.status_code == 202
    body = start.json()
    assert body["status"] in {RenderJobStatus.QUEUED.value, RenderJobStatus.RUNNING.value}

    for _ in range(20):
        detail = await client.get(f"/api/v1/projects/{project_id}/render/jobs/{body['id']}")
        assert detail.status_code == 200
        if detail.json()["status"] == RenderJobStatus.COMPLETED.value:
            break
        await asyncio.sleep(0.05)

    final = await client.get(f"/api/v1/projects/{project_id}/render/jobs/{body['id']}")
    assert final.json()["status"] == RenderJobStatus.COMPLETED.value
    assert final.json()["progress"] == 1.0

    logs = await client.get(f"/api/v1/projects/{project_id}/render/jobs/{body['id']}/logs")
    assert logs.status_code == 200
    assert logs.json()["total_lines"] > 0


@pytest.mark.asyncio
async def test_render_requires_clips(client: AsyncClient, tmp_path):
    project_id = await _create_project(client, tmp_path / "empty")
    response = await client.post(
        f"/api/v1/projects/{project_id}/render",
        json={"preset_id": "h264_1080p60"},
    )
    assert response.status_code == 400
    assert response.json()["error"] == "RENDER_ERROR"
