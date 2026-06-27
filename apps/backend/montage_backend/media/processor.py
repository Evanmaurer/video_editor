from __future__ import annotations

import json
import struct
from pathlib import Path

from montage_backend.media.cache import (
    CacheManifest,
    build_cache_paths,
    invalidate_cache,
    is_cache_valid,
    load_manifest,
    save_manifest,
    source_fingerprint,
)
from montage_backend.media.ffmpeg_runner import FFmpegRunner, ProcessingContext
from montage_backend.models.domain import utc_now_iso
from montage_backend.models.domain.media import (
    CorruptMediaError,
    MediaProcessingError,
    SceneMarker,
    VideoProbeResult,
)


class MediaProcessor:
    """All FFmpeg interaction for MontageAI media processing."""

    PROXY_HEIGHT = 720
    THUMBNAIL_COUNT = 10
    WAVEFORM_SAMPLES = 512
    SCENE_THRESHOLD = 0.3

    def __init__(self, runner: FFmpegRunner | None = None) -> None:
        self._runner = runner or FFmpegRunner()

    @property
    def runner(self) -> FFmpegRunner:
        return self._runner

    async def probe(
        self,
        video: Path,
        *,
        ctx: ProcessingContext | None = None,
    ) -> VideoProbeResult:
        ctx = ctx or ProcessingContext()
        ctx.check_cancelled()
        if not video.is_file():
            raise CorruptMediaError(f"Video file not found: {video}")

        await ctx.report("probe", 0.0, f"Probing {video.name}")
        payload = await self._runner.run_json(
            [
                self._runner.ffprobe_bin,
                "-v",
                "quiet",
                "-print_format",
                "json",
                "-show_format",
                "-show_streams",
                str(video),
            ],
            ctx=ctx,
        )
        await ctx.report("probe", 1.0, "Probe complete")
        return self._parse_probe(video, payload)

    async def generate_proxy(
        self,
        video: Path,
        output: Path,
        *,
        ctx: ProcessingContext | None = None,
    ) -> Path:
        ctx = ctx or ProcessingContext()
        probe = await self.probe(video, ctx=ctx)
        duration_s = probe.duration_ms / 1000.0
        output.parent.mkdir(parents=True, exist_ok=True)

        await ctx.report("proxy", 0.0, f"Generating proxy for {video.name}")
        await self._runner.run(
            [
                self._runner.ffmpeg_bin,
                "-y",
                "-i",
                str(video),
                "-vf",
                f"scale=-2:{self.PROXY_HEIGHT}",
                "-c:v",
                "libx264",
                "-preset",
                "veryfast",
                "-crf",
                "28",
                "-c:a",
                "aac",
                "-b:a",
                "128k",
                "-movflags",
                "+faststart",
                str(output),
            ],
            ctx=ctx,
            operation="proxy",
            duration_seconds=duration_s,
        )
        await ctx.report("proxy", 1.0, "Proxy complete")
        return output

    async def generate_thumbnail_strip(
        self,
        video: Path,
        output: Path,
        *,
        ctx: ProcessingContext | None = None,
        count: int | None = None,
    ) -> Path:
        ctx = ctx or ProcessingContext()
        frame_count = count or self.THUMBNAIL_COUNT
        probe = await self.probe(video, ctx=ctx)
        duration_s = max(probe.duration_ms / 1000.0, 0.1)
        output.parent.mkdir(parents=True, exist_ok=True)

        await ctx.report("thumbnail_strip", 0.0, "Generating thumbnail strip")
        await self._runner.run(
            [
                self._runner.ffmpeg_bin,
                "-y",
                "-i",
                str(video),
                "-vf",
                f"fps=1/{duration_s / frame_count:.4f},scale=160:-1,tile={frame_count}x1",
                "-frames:v",
                "1",
                str(output),
            ],
            ctx=ctx,
            operation="thumbnail_strip",
            duration_seconds=duration_s,
        )
        await ctx.report("thumbnail_strip", 1.0, "Thumbnail strip complete")
        return output

    async def generate_poster(
        self,
        video: Path,
        output: Path,
        *,
        ctx: ProcessingContext | None = None,
    ) -> Path:
        ctx = ctx or ProcessingContext()
        probe = await self.probe(video, ctx=ctx)
        duration_s = max(probe.duration_ms / 1000.0, 0.1)
        seek_s = min(max(duration_s * 0.1, 0.1), max(duration_s - 0.1, 0.1))
        output.parent.mkdir(parents=True, exist_ok=True)

        await ctx.report("thumbnail_poster", 0.0, "Generating poster frame")
        await self._runner.run(
            [
                self._runner.ffmpeg_bin,
                "-y",
                "-ss",
                f"{seek_s:.3f}",
                "-i",
                str(video),
                "-frames:v",
                "1",
                "-vf",
                "scale=320:-1",
                "-q:v",
                "3",
                str(output),
            ],
            ctx=ctx,
            operation="thumbnail_poster",
            duration_seconds=duration_s,
        )
        await ctx.report("thumbnail_poster", 1.0, "Poster frame complete")
        return output

    async def generate_waveform(
        self,
        video: Path,
        output: Path,
        *,
        ctx: ProcessingContext | None = None,
        samples: int | None = None,
    ) -> Path:
        ctx = ctx or ProcessingContext()
        target_samples = samples or self.WAVEFORM_SAMPLES
        output.parent.mkdir(parents=True, exist_ok=True)

        await ctx.report("waveform", 0.0, "Generating waveform")
        stdout = await self._runner.run_capture_stdout(
            [
                self._runner.ffmpeg_bin,
                "-y",
                "-i",
                str(video),
                "-vn",
                "-ac",
                "1",
                "-f",
                "f32le",
                "-",
            ],
            ctx=ctx,
        )

        peaks = self._downsample_peaks(stdout, target_samples)
        output.write_text(json.dumps({"samples": peaks, "count": len(peaks)}))
        await ctx.report("waveform", 1.0, "Waveform complete")
        return output

    async def detect_scenes(
        self,
        video: Path,
        *,
        ctx: ProcessingContext | None = None,
        threshold: float | None = None,
    ) -> list[SceneMarker]:
        ctx = ctx or ProcessingContext()
        scene_threshold = threshold if threshold is not None else self.SCENE_THRESHOLD
        probe = await self.probe(video, ctx=ctx)
        duration_s = probe.duration_ms / 1000.0

        await ctx.report("detect_scenes", 0.0, "Detecting scenes")
        stderr = await self._runner.run(
            [
                self._runner.ffmpeg_bin,
                "-i",
                str(video),
                "-filter:v",
                f"select='gt(scene,{scene_threshold})',showinfo",
                "-f",
                "null",
                "-",
            ],
            ctx=ctx,
            operation="detect_scenes",
            duration_seconds=duration_s,
        )

        markers: list[SceneMarker] = []
        for line in stderr.splitlines():
            if "pts_time:" not in line:
                continue
            try:
                pts_part = line.split("pts_time:")[1].split()[0]
                score_part = line.split("scene_score:")[1].split()[0] if "scene_score:" in line else "0"
                timestamp_ms = int(float(pts_part) * 1000)
                markers.append(SceneMarker(timestamp_ms=timestamp_ms, score=float(score_part)))
            except (IndexError, ValueError):
                continue

        await ctx.report("detect_scenes", 1.0, f"Found {len(markers)} scenes")
        return markers

    async def export_frame(
        self,
        video: Path,
        timestamp: float,
        output: Path,
        *,
        ctx: ProcessingContext | None = None,
    ) -> Path:
        ctx = ctx or ProcessingContext()
        output.parent.mkdir(parents=True, exist_ok=True)
        await ctx.report("export_frame", 0.0, f"Exporting frame at {timestamp}s")
        await self._runner.run(
            [
                self._runner.ffmpeg_bin,
                "-y",
                "-ss",
                f"{timestamp:.3f}",
                "-i",
                str(video),
                "-frames:v",
                "1",
                "-q:v",
                "2",
                str(output),
            ],
            ctx=ctx,
            operation="export_frame",
        )
        await ctx.report("export_frame", 1.0, "Frame exported")
        return output

    async def transcode(
        self,
        video: Path,
        output: Path,
        *,
        ctx: ProcessingContext | None = None,
        video_codec: str = "libx264",
        audio_codec: str = "aac",
        preset: str = "medium",
        crf: int = 23,
    ) -> Path:
        ctx = ctx or ProcessingContext()
        probe = await self.probe(video, ctx=ctx)
        output.parent.mkdir(parents=True, exist_ok=True)
        await ctx.report("transcode", 0.0, "Transcoding")
        await self._runner.run(
            [
                self._runner.ffmpeg_bin,
                "-y",
                "-i",
                str(video),
                "-c:v",
                video_codec,
                "-preset",
                preset,
                "-crf",
                str(crf),
                "-c:a",
                audio_codec,
                str(output),
            ],
            ctx=ctx,
            operation="transcode",
            duration_seconds=probe.duration_ms / 1000.0,
        )
        await ctx.report("transcode", 1.0, "Transcode complete")
        return output

    async def normalize_audio(
        self,
        video: Path,
        output: Path,
        *,
        ctx: ProcessingContext | None = None,
    ) -> Path:
        ctx = ctx or ProcessingContext()
        probe = await self.probe(video, ctx=ctx)
        output.parent.mkdir(parents=True, exist_ok=True)
        await ctx.report("normalize_audio", 0.0, "Normalizing audio")
        await self._runner.run(
            [
                self._runner.ffmpeg_bin,
                "-y",
                "-i",
                str(video),
                "-c:v",
                "copy",
                "-af",
                "loudnorm=I=-16:TP=-1.5:LRA=11",
                "-c:a",
                "aac",
                str(output),
            ],
            ctx=ctx,
            operation="normalize_audio",
            duration_seconds=probe.duration_ms / 1000.0,
        )
        await ctx.report("normalize_audio", 1.0, "Audio normalized")
        return output

    async def process_import(
        self,
        video: Path,
        project_root: Path,
        media_id: str,
        *,
        ctx: ProcessingContext | None = None,
    ) -> CacheManifest:
        """Generate all cached artifacts for an imported clip."""
        ctx = ctx or ProcessingContext()
        if not video.is_file():
            raise CorruptMediaError(f"Source video not found: {video}")

        suffix = video.suffix.lower() or ".mp4"
        paths = build_cache_paths(project_root, media_id, suffix)
        cache_dir = Path(paths.probe_cache_path).parent
        cache_dir.mkdir(parents=True, exist_ok=True)

        existing = load_manifest(Path(paths.manifest_path))
        fingerprint = source_fingerprint(video)
        if existing and is_cache_valid(existing, video):
            await ctx.report("import", 1.0, "Using valid cache")
            return existing

        invalidate_cache(project_root, media_id)
        cache_dir.mkdir(parents=True, exist_ok=True)

        await ctx.report("import", 0.05, "Probing video")
        probe = await self.probe(video, ctx=ctx)
        Path(paths.probe_cache_path).write_text(probe.model_dump_json(indent=2))

        await ctx.report("import", 0.15, "Generating proxy")
        await self.generate_proxy(video, Path(paths.proxy_path), ctx=ctx)

        await ctx.report("import", 0.45, "Generating thumbnail strip")
        await self.generate_thumbnail_strip(video, Path(paths.thumbnail_strip_path), ctx=ctx)

        await ctx.report("import", 0.55, "Generating poster frame")
        await self.generate_poster(video, Path(paths.thumbnail_poster_path), ctx=ctx)

        await ctx.report("import", 0.65, "Generating waveform")
        await self.generate_waveform(video, Path(paths.waveform_path), ctx=ctx)

        await ctx.report("import", 0.85, "Detecting scenes")
        scenes = await self.detect_scenes(video, ctx=ctx)
        Path(paths.scenes_cache_path).write_text(
            json.dumps([s.model_dump() for s in scenes], indent=2),
        )

        manifest = CacheManifest(
            media_id=media_id,
            source_fingerprint=fingerprint,
            source_path=str(video),
            probe=probe,
            paths=paths,
            generated_at=utc_now_iso(),
        )
        save_manifest(Path(paths.manifest_path), manifest)
        await ctx.report("import", 1.0, "Import processing complete")
        return manifest

    def _parse_probe(self, video: Path, payload: dict) -> VideoProbeResult:
        streams = payload.get("streams", [])
        fmt = payload.get("format", {})
        video_stream = next((s for s in streams if s.get("codec_type") == "video"), None)
        audio_stream = next((s for s in streams if s.get("codec_type") == "audio"), None)

        if video_stream is None:
            raise CorruptMediaError(f"No video stream found in {video}")

        width = int(video_stream.get("width") or 0)
        height = int(video_stream.get("height") or 0)
        if width <= 0 or height <= 0:
            raise CorruptMediaError(f"Invalid video dimensions in {video}")

        frame_rate = self._parse_frame_rate(video_stream.get("avg_frame_rate", "0/1"))
        duration_ms = self._parse_duration_ms(fmt, video_stream)
        frame_count = int(video_stream.get("nb_frames") or 0)
        if frame_count <= 0 and frame_rate > 0:
            frame_count = max(int((duration_ms / 1000.0) * frame_rate), 1)

        bitrate = None
        if fmt.get("bit_rate"):
            bitrate = int(fmt["bit_rate"])

        audio_sample_rate = None
        if audio_stream and audio_stream.get("sample_rate"):
            audio_sample_rate = int(audio_stream["sample_rate"])

        return VideoProbeResult(
            width=width,
            height=height,
            frame_rate=frame_rate,
            codec=str(video_stream.get("codec_name") or "unknown"),
            duration_ms=duration_ms,
            frame_count=frame_count,
            audio_sample_rate=audio_sample_rate,
            bitrate=bitrate,
            file_size_bytes=video.stat().st_size,
        )

    @staticmethod
    def _parse_frame_rate(value: str) -> float:
        if "/" in value:
            num, den = value.split("/", 1)
            den_f = float(den)
            if den_f == 0:
                return 0.0
            return float(num) / den_f
        try:
            return float(value)
        except ValueError:
            return 0.0

    @staticmethod
    def _parse_duration_ms(fmt: dict, video_stream: dict) -> int:
        for source in (fmt, video_stream):
            raw = source.get("duration")
            if raw is not None:
                try:
                    return max(int(float(raw) * 1000), 1)
                except ValueError:
                    continue
        return 1

    @staticmethod
    def _downsample_peaks(raw: bytes, target_samples: int) -> list[float]:
        if not raw:
            return [0.0] * target_samples

        count = len(raw) // 4
        floats = struct.unpack(f"{count}f", raw[: count * 4])
        if count == 0:
            return [0.0] * target_samples
        if count <= target_samples:
            peaks = [min(abs(v), 1.0) for v in floats]
            if len(peaks) < target_samples:
                peaks.extend([0.0] * (target_samples - len(peaks)))
            return peaks

        bucket = count / target_samples
        peaks: list[float] = []
        for i in range(target_samples):
            start = int(i * bucket)
            end = int((i + 1) * bucket)
            chunk = floats[start:end] or (floats[start],)
            peaks.append(min(max(abs(v) for v in chunk), 1.0))
        return peaks
