from __future__ import annotations

import json
import shutil
from dataclasses import dataclass, field
from pathlib import Path

from montage_backend.models.domain.media import MediaCachePaths, VideoProbeResult


@dataclass
class CacheManifest:
    media_id: str
    source_fingerprint: str
    source_path: str
    probe: VideoProbeResult
    paths: MediaCachePaths
    generated_at: str

    def to_json(self) -> str:
        return json.dumps(
            {
                "media_id": self.media_id,
                "source_fingerprint": self.source_fingerprint,
                "source_path": self.source_path,
                "probe": self.probe.model_dump(),
                "paths": self.paths.model_dump(),
                "generated_at": self.generated_at,
            },
            indent=2,
        )

    @classmethod
    def from_json(cls, raw: str) -> CacheManifest:
        data = json.loads(raw)
        paths_data = normalize_cache_paths_data(data["paths"])
        return cls(
            media_id=data["media_id"],
            source_fingerprint=data["source_fingerprint"],
            source_path=data["source_path"],
            probe=VideoProbeResult.model_validate(data["probe"]),
            paths=MediaCachePaths.model_validate(paths_data),
            generated_at=data["generated_at"],
        )


def source_fingerprint(path: Path) -> str:
    stat = path.stat()
    return f"{stat.st_mtime_ns}:{stat.st_size}"


def media_cache_dir(project_root: Path, media_id: str) -> Path:
    return project_root / "cache" / "media" / media_id


def normalize_cache_paths_data(paths_data: dict) -> dict:
    data = dict(paths_data)
    if "thumbnail_poster_path" not in data:
        strip_path = data.get("thumbnail_strip_path", "")
        if strip_path.endswith("_strip.jpg"):
            data["thumbnail_poster_path"] = strip_path.replace("_strip.jpg", "_poster.jpg")
        else:
            data["thumbnail_poster_path"] = strip_path
    return data


def build_cache_paths(project_root: Path, media_id: str, original_suffix: str) -> MediaCachePaths:
    cache_dir = media_cache_dir(project_root, media_id)
    return MediaCachePaths(
        original_path=str(project_root / "media" / "originals" / f"{media_id}{original_suffix}"),
        proxy_path=str(project_root / "media" / "proxies" / f"{media_id}.mp4"),
        thumbnail_poster_path=str(project_root / "thumbnails" / f"{media_id}_poster.jpg"),
        thumbnail_strip_path=str(project_root / "thumbnails" / f"{media_id}_strip.jpg"),
        waveform_path=str(cache_dir / "waveform.json"),
        probe_cache_path=str(cache_dir / "probe.json"),
        scenes_cache_path=str(cache_dir / "scenes.json"),
        manifest_path=str(cache_dir / "manifest.json"),
    )


def load_manifest(manifest_path: Path) -> CacheManifest | None:
    if not manifest_path.is_file():
        return None
    try:
        return CacheManifest.from_json(manifest_path.read_text())
    except (json.JSONDecodeError, KeyError, ValueError):
        return None


def save_manifest(manifest_path: Path, manifest: CacheManifest) -> None:
    manifest_path.parent.mkdir(parents=True, exist_ok=True)
    manifest_path.write_text(manifest.to_json())


def is_cache_valid(manifest: CacheManifest, source_path: Path) -> bool:
    if not source_path.is_file():
        return False
    if source_fingerprint(source_path) != manifest.source_fingerprint:
        return False
    paths = manifest.paths
    required = [
        paths.proxy_path,
        paths.thumbnail_poster_path,
        paths.thumbnail_strip_path,
        paths.waveform_path,
        paths.probe_cache_path,
        paths.scenes_cache_path,
    ]
    return all(Path(p).is_file() for p in required)


def invalidate_cache(project_root: Path, media_id: str) -> None:
    cache_dir = media_cache_dir(project_root, media_id)
    if cache_dir.exists():
        shutil.rmtree(cache_dir, ignore_errors=True)

    for pattern in (
        project_root / "media" / "proxies" / f"{media_id}.mp4",
        project_root / "thumbnails" / f"{media_id}_poster.jpg",
        project_root / "thumbnails" / f"{media_id}_strip.jpg",
    ):
        if pattern.is_file():
            pattern.unlink()
