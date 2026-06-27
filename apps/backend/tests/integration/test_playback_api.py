from __future__ import annotations

from unittest.mock import patch

import pytest
from httpx import AsyncClient


async def _create_project(client: AsyncClient, project_root, name: str = "Playback Test") -> str:
    create = await client.post(
        "/api/v1/projects",
        json={
            "name": name,
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
async def test_playback_metrics_roundtrip(client: AsyncClient, tmp_path):
    project_id = await _create_project(client, tmp_path / "playback")

    get_empty = await client.get(f"/api/v1/projects/{project_id}/playback/metrics")
    assert get_empty.status_code == 200
    assert get_empty.json()["playback_fps"] == 0.0

    report = await client.post(
        f"/api/v1/projects/{project_id}/playback/metrics",
        json={"playback_fps": 59.8, "dropped_frames": 2},
    )
    assert report.status_code == 200
    body = report.json()
    assert body["playback_fps"] == 59.8
    assert body["dropped_frames"] == 2


@pytest.mark.asyncio
async def test_playback_decode_returns_cached_frame(client: AsyncClient, tmp_path, monkeypatch):
    project_id = await _create_project(client, tmp_path / "decode")
    project_root = tmp_path / "decode"
    media_dir = project_root / "media"
    media_dir.mkdir(parents=True, exist_ok=True)
    video_path = media_dir / "clip.mp4"
    video_path.write_bytes(b"fake")

    from montage_backend.api import deps

    media_service = deps.get_media_service()

    async def fake_get_media_item(pid: str, media_id: str):
        from montage_backend.models.domain.media import ImportStatus, MediaItem, MediaRole, MediaType

        return MediaItem(
            id=media_id,
            project_id=pid,
            file_path=str(video_path),
            proxy_path=str(video_path),
            file_name="clip.mp4",
            media_type=MediaType.VIDEO,
            role=MediaRole.CLIP,
            duration_ms=5000,
            width=1920,
            height=1080,
            frame_rate=60,
            file_size_bytes=4,
            tags=[],
            import_status=ImportStatus.READY,
            created_at="2026-06-27T00:00:00Z",
            updated_at="2026-06-27T00:00:00Z",
        )

    monkeypatch.setattr(media_service, "get_media_item", fake_get_media_item)

    fake_jpeg = b"\xff\xd8\xff\xd9"
    with patch(
        "montage_backend.playback.playback_service.PlaybackDecoder.decode_jpeg",
        return_value=(fake_jpeg, 12.5),
    ):
        decode = await client.post(
            f"/api/v1/projects/{project_id}/playback/decode",
            json={
                "media_id": "media-1",
                "source_ms": 1000,
                "frame_rate": 60,
                "quality": "proxy",
            },
        )
        assert decode.status_code == 200
        first = decode.json()
        assert first["cache_hit"] is False
        assert first["decode_time_ms"] == 12.5

        cached = await client.post(
            f"/api/v1/projects/{project_id}/playback/decode",
            json={
                "media_id": "media-1",
                "source_ms": 1000,
                "frame_rate": 60,
                "quality": "proxy",
            },
        )
        assert cached.status_code == 200
        second = cached.json()
        assert second["cache_hit"] is True
        assert second["decode_time_ms"] == 0.0


@pytest.mark.asyncio
async def test_playback_prefetch_accepted(client: AsyncClient, tmp_path):
    project_id = await _create_project(client, tmp_path / "prefetch")

    response = await client.post(
        f"/api/v1/projects/{project_id}/playback/prefetch",
        json={
            "frame_rate": 60,
            "requests": [
                {"media_id": "missing", "source_ms": 0, "quality": "proxy"},
            ],
        },
    )
    assert response.status_code == 202
    assert response.json()["status"] == "accepted"
