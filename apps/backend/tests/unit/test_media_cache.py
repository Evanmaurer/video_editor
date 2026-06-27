from __future__ import annotations

import json
from pathlib import Path

import pytest

from montage_backend.media.cache import (
    CacheManifest,
    build_cache_paths,
    invalidate_cache,
    is_cache_valid,
    load_manifest,
    save_manifest,
    source_fingerprint,
)
from montage_backend.models.domain import utc_now_iso
from montage_backend.models.domain.media import MediaCachePaths, VideoProbeResult


def _sample_probe() -> VideoProbeResult:
    return VideoProbeResult(
        width=1920,
        height=1080,
        frame_rate=30.0,
        codec="h264",
        duration_ms=5000,
        frame_count=150,
        audio_sample_rate=48000,
        bitrate=4_000_000,
        file_size_bytes=1024,
    )


def test_source_fingerprint_changes_when_file_changes(tmp_path: Path) -> None:
    video = tmp_path / "clip.mp4"
    video.write_bytes(b"v1")
    first = source_fingerprint(video)
    video.write_bytes(b"v2-updated")
    second = source_fingerprint(video)
    assert first != second


def test_cache_validity_and_invalidation(tmp_path: Path) -> None:
    project_root = tmp_path / "project"
    project_root.mkdir()
    media_id = "media-1"
    paths = build_cache_paths(project_root, media_id, ".mp4")

    source = project_root / "media" / "originals" / f"{media_id}.mp4"
    source.parent.mkdir(parents=True)
    source.write_bytes(b"video")

    for path_str in (
        paths.proxy_path,
        paths.thumbnail_poster_path,
        paths.thumbnail_strip_path,
        paths.waveform_path,
        paths.probe_cache_path,
        paths.scenes_cache_path,
    ):
        path = Path(path_str)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text("{}")

    manifest = CacheManifest(
        media_id=media_id,
        source_fingerprint=source_fingerprint(source),
        source_path=str(source),
        probe=_sample_probe(),
        paths=paths,
        generated_at=utc_now_iso(),
    )
    save_manifest(Path(paths.manifest_path), manifest)

    loaded = load_manifest(Path(paths.manifest_path))
    assert loaded is not None
    assert is_cache_valid(loaded, source)

    source.write_bytes(b"changed")
    assert not is_cache_valid(loaded, source)

    invalidate_cache(project_root, media_id)
    assert not Path(paths.proxy_path).exists()
    assert not Path(paths.manifest_path).parent.exists()
