from __future__ import annotations

import asyncio
import base64
import platform
import sys
import threading
import time
from collections import OrderedDict
from dataclasses import dataclass, field
from pathlib import Path

from montage_backend.config import settings
from montage_backend.logging import get_logger
from montage_backend.media.ffmpeg_tools import detect_ffmpeg, require_ffmpeg
from montage_backend.models.domain.media import MediaNotFoundError, MediaProcessingError
from montage_backend.services.media_service import MediaService
from montage_backend.services.project_service import ProjectService

logger = get_logger(__name__)


@dataclass
class FrameCacheEntry:
    jpeg_bytes: bytes
    created_at: float
    size_bytes: int


class FrameCache:
    """Thread-safe LRU cache for decoded preview frames."""

    def __init__(self, max_entries: int = 120, max_bytes: int = 256 * 1024 * 1024) -> None:
        self._entries: OrderedDict[str, FrameCacheEntry] = OrderedDict()
        self._max_entries = max_entries
        self._max_bytes = max_bytes
        self._total_bytes = 0
        self._lock = threading.Lock()
        self.hits = 0
        self.misses = 0

    def _evict(self) -> None:
        while self._entries and (
            len(self._entries) > self._max_entries or self._total_bytes > self._max_bytes
        ):
            _, entry = self._entries.popitem(last=False)
            self._total_bytes -= entry.size_bytes

    def contains(self, key: str) -> bool:
        with self._lock:
            return key in self._entries

    def get(self, key: str) -> bytes | None:
        with self._lock:
            entry = self._entries.get(key)
            if entry is None:
                self.misses += 1
                return None
            self._entries.move_to_end(key)
            self.hits += 1
            return entry.jpeg_bytes

    def put(self, key: str, jpeg_bytes: bytes) -> None:
        with self._lock:
            existing = self._entries.pop(key, None)
            if existing is not None:
                self._total_bytes -= existing.size_bytes
            entry = FrameCacheEntry(
                jpeg_bytes=jpeg_bytes,
                created_at=time.time(),
                size_bytes=len(jpeg_bytes),
            )
            self._entries[key] = entry
            self._total_bytes += entry.size_bytes
            self._evict()

    @property
    def memory_usage_mb(self) -> float:
        with self._lock:
            return self._total_bytes / (1024 * 1024)

    @property
    def cache_hit_rate(self) -> float:
        total = self.hits + self.misses
        if total == 0:
            return 0.0
        return self.hits / total


@dataclass
class DecodeMetrics:
    last_decode_time_ms: float = 0.0
    gpu_accelerated: bool = False
    dropped_frames: int = 0
    playback_fps: float = 0.0


@dataclass
class PrefetchJob:
    cache_key: str
    video_path: Path
    source_ms: int
    frame_rate: float


class PlaybackDecoder:
    """Decode single frames via FFmpeg (optionally GPU-accelerated)."""

    def __init__(self) -> None:
        self._ffmpeg = settings.ffmpeg_bin
        self._gpu_available = self._detect_gpu_accel()

    def _detect_gpu_accel(self) -> bool:
        if not settings.gpu_enabled:
            return False
        if platform.system() != "Darwin":
            return False
        info = detect_ffmpeg(self._ffmpeg, settings.ffprobe_bin)
        return info.available

    @property
    def gpu_accelerated(self) -> bool:
        return self._gpu_available

    def decode_jpeg(
        self,
        video_path: Path,
        source_ms: int,
        frame_rate: float,
    ) -> tuple[bytes, float]:
        require_ffmpeg(self._ffmpeg, settings.ffprobe_bin)
        if not video_path.is_file():
            raise MediaProcessingError(f"Video file missing: {video_path}")

        frame_ms = round(source_ms / (1000.0 / frame_rate)) * (1000.0 / frame_rate)
        seek_s = max(0.0, frame_ms / 1000.0)

        args = [self._ffmpeg, "-hide_banner", "-loglevel", "error", "-y"]
        if self._gpu_available:
            args.extend(["-hwaccel", "videotoolbox"])
        args.extend(
            [
                "-ss",
                f"{seek_s:.6f}",
                "-i",
                str(video_path),
                "-frames:v",
                "1",
                "-f",
                "image2pipe",
                "-vcodec",
                "mjpeg",
                "-q:v",
                "3",
                "pipe:1",
            ],
        )

        started = time.perf_counter()
        import subprocess

        try:
            result = subprocess.run(
                args,
                check=True,
                capture_output=True,
                timeout=30,
            )
        except subprocess.CalledProcessError as exc:
            stderr = exc.stderr.decode("utf-8", errors="replace")
            raise MediaProcessingError(f"Frame decode failed: {stderr}") from exc
        except subprocess.TimeoutExpired as exc:
            raise MediaProcessingError("Frame decode timed out") from exc

        decode_ms = (time.perf_counter() - started) * 1000.0
        if not result.stdout:
            raise MediaProcessingError("Frame decode returned empty output")
        return result.stdout, decode_ms


class PlaybackService:
    def __init__(
        self,
        project_service: ProjectService,
        media_service: MediaService,
        *,
        worker_count: int = 2,
    ) -> None:
        self._project_service = project_service
        self._media_service = media_service
        self._decoder = PlaybackDecoder()
        self._cache = FrameCache()
        self._metrics = DecodeMetrics(gpu_accelerated=self._decoder.gpu_accelerated)
        self._prefetch_queue: asyncio.Queue[PrefetchJob | None] | None = None
        self._workers: list[asyncio.Task[None]] = []
        self._worker_count = worker_count

    def _cache_key(self, video_path: Path, source_ms: int, quality: str) -> str:
        frame_ms = int(source_ms)
        return f"{quality}:{video_path}:{frame_ms}"

    async def _resolve_video_path(
        self,
        project_id: str,
        media_id: str,
        quality: str,
    ) -> Path:
        media = await self._media_service.get_media_item(project_id, media_id)
        if quality == "full":
            path = Path(media.file_path)
        else:
            path = Path(media.proxy_path) if media.proxy_path else Path(media.file_path)
        if not path.is_file():
            raise MediaProcessingError(f"Playback source missing for media {media_id}: {path}")
        return path

    async def decode_frame(
        self,
        project_id: str,
        media_id: str,
        source_ms: int,
        frame_rate: float,
        quality: str = "proxy",
    ) -> dict:
        video_path = await self._resolve_video_path(project_id, media_id, quality)
        cache_key = self._cache_key(video_path, source_ms, quality)

        cached = self._cache.get(cache_key)
        if cached is not None:
            self._metrics.last_decode_time_ms = 0.0
            return {
                "image_base64": base64.b64encode(cached).decode("ascii"),
                "decode_time_ms": 0.0,
                "cache_hit": True,
                "gpu_accelerated": self._decoder.gpu_accelerated,
            }

        loop = asyncio.get_running_loop()
        jpeg_bytes, decode_ms = await loop.run_in_executor(
            None,
            self._decoder.decode_jpeg,
            video_path,
            source_ms,
            frame_rate,
        )
        self._cache.put(cache_key, jpeg_bytes)
        self._metrics.last_decode_time_ms = decode_ms

        return {
            "image_base64": base64.b64encode(jpeg_bytes).decode("ascii"),
            "decode_time_ms": decode_ms,
            "cache_hit": False,
            "gpu_accelerated": self._decoder.gpu_accelerated,
        }

    async def prefetch_frames(
        self,
        project_id: str,
        requests: list[dict],
        frame_rate: float,
    ) -> None:
        self._ensure_workers()
        for item in requests:
            media_id = item["media_id"]
            source_ms = int(item["source_ms"])
            quality = item.get("quality", "proxy")
            try:
                video_path = await self._resolve_video_path(project_id, media_id, quality)
            except (MediaNotFoundError, MediaProcessingError):
                continue
            cache_key = self._cache_key(video_path, source_ms, quality)
            if self._cache.contains(cache_key):
                continue
            await self._prefetch_queue.put(
                PrefetchJob(
                    cache_key=cache_key,
                    video_path=video_path,
                    source_ms=source_ms,
                    frame_rate=frame_rate,
                ),
            )

    def _ensure_workers(self) -> None:
        if self._prefetch_queue is not None:
            return
        self._prefetch_queue = asyncio.Queue(maxsize=256)
        for _ in range(self._worker_count):
            self._workers.append(asyncio.create_task(self._prefetch_worker()))

    async def _prefetch_worker(self) -> None:
        assert self._prefetch_queue is not None
        loop = asyncio.get_running_loop()
        while True:
            job = await self._prefetch_queue.get()
            if job is None:
                break
            if self._cache.get(job.cache_key) is not None:
                continue
            try:
                jpeg_bytes, _ = await loop.run_in_executor(
                    None,
                    self._decoder.decode_jpeg,
                    job.video_path,
                    job.source_ms,
                    job.frame_rate,
                )
                self._cache.put(job.cache_key, jpeg_bytes)
            except MediaProcessingError as exc:
                logger.warning("prefetch_failed", error=exc.message)

    def update_client_metrics(
        self,
        *,
        playback_fps: float,
        dropped_frames: int,
    ) -> None:
        self._metrics.playback_fps = playback_fps
        self._metrics.dropped_frames = dropped_frames

    def get_metrics(self) -> dict:
        process_mb = 0.0
        try:
            import resource

            usage = resource.getrusage(resource.RUSAGE_SELF).ru_maxrss
            if sys.platform == "darwin":
                process_mb = usage / (1024 * 1024)
            else:
                process_mb = usage / 1024
        except Exception:
            process_mb = 0.0

        memory_mb = max(self._cache.memory_usage_mb, process_mb)
        return {
            "playback_fps": round(self._metrics.playback_fps, 1),
            "dropped_frames": self._metrics.dropped_frames,
            "decode_time_ms": round(self._metrics.last_decode_time_ms, 2),
            "memory_usage_mb": round(memory_mb, 1),
            "gpu_accelerated": self._decoder.gpu_accelerated,
            "cache_hit_rate": round(self._cache.cache_hit_rate, 3),
        }

    async def shutdown(self) -> None:
        if self._prefetch_queue is None:
            return
        for _ in self._workers:
            await self._prefetch_queue.put(None)
        await asyncio.gather(*self._workers, return_exceptions=True)
        self._workers.clear()
        self._prefetch_queue = None
