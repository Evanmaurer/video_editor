from __future__ import annotations

from pathlib import Path
from unittest.mock import AsyncMock

import pytest
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from montage_backend.media.cache import build_cache_paths
from montage_backend.media.processor import MediaProcessor
from montage_backend.models.domain import CreateProjectRequest
from montage_backend.models.domain.media import (
    ImportStatus,
    MediaListQuery,
    MediaRole,
    StorageMode,
    UpdateMediaRequest,
)
from montage_backend.services.media_service import MediaService
from montage_backend.services.project_service import ProjectService


@pytest.fixture
def sample_video(tmp_path: Path) -> Path:
    clip = tmp_path / "clips" / "gameplay.mp4"
    clip.parent.mkdir(parents=True)
    clip.write_bytes(b"fake gameplay video")
    return clip


@pytest.fixture
async def media_service(test_app_engine, monkeypatch, tmp_path, sample_video: Path) -> MediaService:
    monkeypatch.setattr("montage_backend.config.settings.app_data_dir", tmp_path / "app_data")
    session_factory = async_sessionmaker(test_app_engine, expire_on_commit=False, class_=AsyncSession)
    project_service = ProjectService(session_factory)

    processor = MediaProcessor()
    processor.process_import = AsyncMock(  # type: ignore[method-assign]
        side_effect=_fake_process_import,
    )

    return MediaService(project_service, processor=processor)


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
        width=1920,
        height=1080,
        frame_rate=60.0,
        codec="h264",
        duration_ms=10_000,
        frame_count=600,
        audio_sample_rate=48000,
        bitrate=5_000_000,
        file_size_bytes=video.stat().st_size,
    )
    Path(paths.probe_cache_path).write_text(probe.model_dump_json())
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


@pytest.mark.asyncio
async def test_import_creates_media_record_and_cache(
    media_service: MediaService,
    sample_video: Path,
    tmp_path: Path,
) -> None:
    project_root = tmp_path / "TestProject"
    project = await media_service._project_service.create_project(
        CreateProjectRequest(name="Media Test", root_path=str(project_root)),
    )

    result = await media_service.import_files(
        project.id,
        [str(sample_video)],
        MediaRole.CLIP,
        wait=True,
    )

    assert len(result.imported) == 1
    assert result.imported[0].status == ImportStatus.READY

    media = await media_service.get_media_item(project.id, result.imported[0].media_id)
    assert media.width == 1920
    assert media.height == 1080
    assert media.frame_rate == 60.0
    assert media.codec == "h264"
    assert media.duration_ms == 10_000
    assert media.frame_count == 600
    assert media.audio_sample_rate == 48000
    assert media.bitrate == 5_000_000
    assert media.proxy_path is not None
    assert media.thumbnail_path is not None
    assert media.waveform_path is not None
    assert media.sha256_hash is not None
    assert media.proxy_status.value == "ready"
    assert Path(media.proxy_path).is_file()
    assert Path(media.waveform_path).is_file()


@pytest.mark.asyncio
async def test_import_skips_missing_files(
    media_service: MediaService,
    tmp_path: Path,
) -> None:
    project_root = tmp_path / "SkipTest"
    project = await media_service._project_service.create_project(
        CreateProjectRequest(name="Skip", root_path=str(project_root)),
    )
    result = await media_service.import_files(
        project.id,
        [str(tmp_path / "missing.mp4")],
    )
    assert result.imported == []
    assert len(result.skipped) == 1


@pytest.mark.asyncio
async def test_import_detects_sha256_duplicate(
    media_service: MediaService,
    sample_video: Path,
    tmp_path: Path,
) -> None:
    project_root = tmp_path / "DupProject"
    project = await media_service._project_service.create_project(
        CreateProjectRequest(name="Dup", root_path=str(project_root)),
    )

    first = await media_service.import_files(
        project.id,
        [str(sample_video)],
        wait=True,
    )
    assert len(first.imported) == 1

    alias = tmp_path / "alias.mp4"
    alias.write_bytes(sample_video.read_bytes())

    second = await media_service.import_files(
        project.id,
        [str(alias)],
        wait=True,
    )
    assert second.imported == []
    assert len(second.duplicates) == 1
    assert second.duplicates[0].status == ImportStatus.DUPLICATE
    assert second.duplicates[0].media_id == first.imported[0].media_id


@pytest.mark.asyncio
async def test_reference_storage_keeps_original_path(
    media_service: MediaService,
    sample_video: Path,
    tmp_path: Path,
) -> None:
    project_root = tmp_path / "RefProject"
    project = await media_service._project_service.create_project(
        CreateProjectRequest(name="Ref", root_path=str(project_root)),
    )

    result = await media_service.import_files(
        project.id,
        [str(sample_video)],
        storage_mode=StorageMode.REFERENCE,
        wait=True,
    )
    media = await media_service.get_media_item(project.id, result.imported[0].media_id)
    assert media.storage_mode == StorageMode.REFERENCE
    assert Path(media.file_path).resolve() == sample_video.resolve()
    assert media.source_path == str(sample_video)


@pytest.mark.asyncio
async def test_list_media_search_tags_favorites(
    media_service: MediaService,
    sample_video: Path,
    tmp_path: Path,
) -> None:
    project_root = tmp_path / "ListProject"
    project = await media_service._project_service.create_project(
        CreateProjectRequest(name="List", root_path=str(project_root)),
    )

    imported = await media_service.import_files(
        project.id,
        [str(sample_video)],
        wait=True,
    )
    media_id = imported.imported[0].media_id
    await media_service.update_media(
        project.id,
        media_id,
        UpdateMediaRequest(tags=["pvp"], is_favorite=True),
    )

    all_items = await media_service.list_media(project.id)
    assert len(all_items) == 1

    favorites = await media_service.list_media(
        project.id,
        MediaListQuery(favorites_only=True),
    )
    assert len(favorites) == 1

    tagged = await media_service.list_media(
        project.id,
        MediaListQuery(tags=["pvp"]),
    )
    assert len(tagged) == 1

    search = await media_service.list_media(
        project.id,
        MediaListQuery(search="gameplay"),
    )
    assert len(search) == 1

    no_match = await media_service.list_media(
        project.id,
        MediaListQuery(search="missing-clip-name"),
    )
    assert no_match == []
