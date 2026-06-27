from __future__ import annotations

import json
from pathlib import Path
from unittest.mock import AsyncMock

import pytest
from httpx import AsyncClient

from montage_backend.api import deps
from montage_backend.media.cache import build_cache_paths
from montage_backend.media.processor import MediaProcessor
from montage_backend.services.media_service import MediaService


async def _fake_process_import(video, project_root, media_id, *, ctx=None):
    from montage_backend.media.cache import CacheManifest, save_manifest, source_fingerprint
    from montage_backend.models.domain import utc_now_iso
    from montage_backend.models.domain.media import VideoProbeResult

    paths = build_cache_paths(project_root, media_id, video.suffix)
    for path_str in (
        paths.proxy_path,
        paths.thumbnail_poster_path,
        paths.thumbnail_strip_path,
        paths.waveform_path,
        paths.probe_cache_path,
        paths.scenes_cache_path,
    ):
        p = Path(path_str)
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text("{}")

    probe = VideoProbeResult(
        width=1280,
        height=720,
        frame_rate=30.0,
        codec="h264",
        duration_ms=3000,
        frame_count=90,
        audio_sample_rate=44100,
        bitrate=1_000_000,
        file_size_bytes=video.stat().st_size,
    )
    manifest = CacheManifest(
        media_id=media_id,
        source_fingerprint=source_fingerprint(video),
        source_path=str(video),
        probe=probe,
        paths=paths,
        generated_at=utc_now_iso(),
    )
    save_manifest(Path(paths.manifest_path), manifest)
    return manifest


@pytest.fixture
def sample_clip(tmp_path: Path) -> Path:
    clip = tmp_path / "clip.mp4"
    clip.write_bytes(b"integration-test-video")
    return clip


@pytest.fixture
def media_client(client: AsyncClient, sample_clip: Path):
    processor = MediaProcessor()
    processor.process_import = AsyncMock(side_effect=_fake_process_import)  # type: ignore[method-assign]
    deps._media_service = MediaService(deps.get_project_service(), processor=processor)
    return client, sample_clip


async def _create_project(client: AsyncClient, project_root: Path, name: str) -> str:
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
    assert create.status_code == 201, create.text
    return create.json()["id"]


@pytest.mark.asyncio
async def test_list_media_empty_project(media_client, tmp_path: Path) -> None:
    client, _clip = media_client
    project_id = await _create_project(client, tmp_path / "EmptyMedia", "Empty")

    response = await client.get(f"/api/v1/projects/{project_id}/media")
    assert response.status_code == 200, response.text
    assert response.json() == {"items": []}


@pytest.mark.asyncio
async def test_import_media_async_returns_202(media_client, tmp_path: Path) -> None:
    client, clip = media_client
    project_id = await _create_project(client, tmp_path / "AsyncMediaProject", "Async Media")

    response = await client.post(
        f"/api/v1/projects/{project_id}/media/import",
        json={"paths": [str(clip)], "role": "clip"},
    )
    assert response.status_code == 202, response.text
    body = response.json()
    assert len(body["imported"]) == 1
    assert body["imported"][0]["status"] == "processing"
    assert body["duplicates"] == []


@pytest.mark.asyncio
async def test_import_media_via_api(media_client, tmp_path: Path) -> None:
    client, clip = media_client
    project_root = tmp_path / "ApiMediaProject"
    project_id = await _create_project(client, project_root, "Media API")

    response = await client.post(
        f"/api/v1/projects/{project_id}/media/import?wait=true",
        json={"paths": [str(clip)], "role": "clip"},
    )
    assert response.status_code == 200, response.text
    body = response.json()
    assert len(body["imported"]) == 1
    assert body["imported"][0]["status"] == "ready"
    assert body["imported"][0]["sha256_hash"]
    media_id = body["imported"][0]["media_id"]

    get_resp = await client.get(f"/api/v1/projects/{project_id}/media/{media_id}")
    assert get_resp.status_code == 200
    media = get_resp.json()
    assert media["width"] == 1280
    assert media["height"] == 720
    assert media["codec"] == "h264"
    assert media["frame_count"] == 90
    assert media["audio_sample_rate"] == 44100
    assert media["proxy_path"]
    assert media["waveform_path"]
    assert media["proxy_status"] == "ready"
    assert media["waveform_status"] == "ready"
    assert media["scene_status"] == "ready"

    list_resp = await client.get(f"/api/v1/projects/{project_id}/media")
    assert list_resp.status_code == 200
    assert len(list_resp.json()["items"]) == 1

    manifest_path = project_root / "cache" / "media" / media_id / "manifest.json"
    assert manifest_path.is_file()
    manifest = json.loads(manifest_path.read_text())
    assert manifest["probe"]["width"] == 1280


@pytest.mark.asyncio
async def test_import_media_folder(media_client, tmp_path: Path) -> None:
    client, _clip = media_client
    folder = tmp_path / "Footage"
    nested = folder / "nested"
    nested.mkdir(parents=True)
    (folder / "root.mp4").write_bytes(b"folder-video")
    (nested / "nested.mp4").write_bytes(b"nested-video")

    project_id = await _create_project(client, tmp_path / "FolderProject", "Folder")

    response = await client.post(
        f"/api/v1/projects/{project_id}/media/import-folder?wait=true",
        json={"path": str(folder), "role": "clip"},
    )
    assert response.status_code == 200, response.text
    body = response.json()
    assert len(body["imported"]) == 2

    list_resp = await client.get(f"/api/v1/projects/{project_id}/media")
    assert len(list_resp.json()["items"]) == 2


@pytest.mark.asyncio
async def test_duplicate_detection_via_sha256(media_client, tmp_path: Path) -> None:
    client, clip = media_client
    project_id = await _create_project(client, tmp_path / "DuplicateProject", "Duplicate")

    first = await client.post(
        f"/api/v1/projects/{project_id}/media/import?wait=true",
        json={"paths": [str(clip)], "role": "clip"},
    )
    assert first.status_code == 200
    media_id = first.json()["imported"][0]["media_id"]
    file_hash = first.json()["imported"][0]["sha256_hash"]

    duplicate_copy = tmp_path / "duplicate-name.mp4"
    duplicate_copy.write_bytes(clip.read_bytes())

    second = await client.post(
        f"/api/v1/projects/{project_id}/media/import?wait=true",
        json={"paths": [str(duplicate_copy)], "role": "clip"},
    )
    assert second.status_code == 200
    body = second.json()
    assert body["imported"] == []
    assert len(body["duplicates"]) == 1
    assert body["duplicates"][0]["media_id"] == media_id
    assert body["duplicates"][0]["status"] == "duplicate"
    assert body["duplicates"][0]["sha256_hash"] == file_hash

    list_resp = await client.get(f"/api/v1/projects/{project_id}/media")
    assert len(list_resp.json()["items"]) == 1


@pytest.mark.asyncio
async def test_update_and_delete_media(media_client, tmp_path: Path) -> None:
    client, clip = media_client
    project_id = await _create_project(client, tmp_path / "DeleteProject", "Delete")

    imported = await client.post(
        f"/api/v1/projects/{project_id}/media/import?wait=true",
        json={"paths": [str(clip)], "role": "clip"},
    )
    media_id = imported.json()["imported"][0]["media_id"]

    patch = await client.patch(
        f"/api/v1/projects/{project_id}/media/{media_id}",
        json={"tags": ["pvp", "highlight"], "is_favorite": True},
    )
    assert patch.status_code == 200
    updated = patch.json()
    assert updated["tags"] == ["highlight", "pvp"]
    assert updated["is_favorite"] is True

    filtered = await client.get(
        f"/api/v1/projects/{project_id}/media",
        params={"favorites_only": "true", "tags": "pvp"},
    )
    assert len(filtered.json()["items"]) == 1

    delete = await client.delete(f"/api/v1/projects/{project_id}/media/{media_id}")
    assert delete.status_code == 204

    missing = await client.get(f"/api/v1/projects/{project_id}/media/{media_id}")
    assert missing.status_code == 404

    list_resp = await client.get(f"/api/v1/projects/{project_id}/media")
    assert list_resp.json()["items"] == []


@pytest.mark.asyncio
async def test_media_endpoints_require_existing_project(client: AsyncClient) -> None:
    missing_id = "00000000-0000-0000-0000-000000000000"
    list_resp = await client.get(f"/api/v1/projects/{missing_id}/media")
    assert list_resp.status_code == 404

    import_resp = await client.post(
        f"/api/v1/projects/{missing_id}/media/import",
        json={"paths": ["/tmp/missing.mp4"]},
    )
    assert import_resp.status_code == 404
