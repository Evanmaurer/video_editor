from __future__ import annotations

import json
import re
import struct
from pathlib import Path

from montage_backend.media.cache import source_fingerprint
from montage_backend.media.ffmpeg_runner import FFmpegRunner, ProcessingContext
from montage_backend.media.processor import MediaProcessor
from montage_backend.models.domain.media import SceneMarker
from montage_backend.models.domain.metadata import (
    AICacheMetadata,
    AudioMetadata,
    BeatMarker,
    BrightnessStats,
    CameraMovement,
    ColorHistogram,
    KeyframeMarker,
    SilenceRegion,
    SpeechDetection,
    VisualMetadata,
)

_YAVG_RE = re.compile(r"lavfi\.signalstats\.YAVG=([0-9.+-eE]+)")
_YMIN_RE = re.compile(r"lavfi\.signalstats\.YMIN=([0-9.+-eE]+)")
_YMAX_RE = re.compile(r"lavfi\.signalstats\.YMAX=([0-9.+-eE]+)")
_SILENCE_START_RE = re.compile(r"silence_start:\s*([0-9.]+)")
_SILENCE_END_RE = re.compile(r"silence_end:\s*([0-9.]+)")
_MEAN_VOLUME_RE = re.compile(r"mean_volume:\s*([-0-9.]+)\s*dB")
_MAX_VOLUME_RE = re.compile(r"max_volume:\s*([-0-9.]+)\dB")


class MetadataExtractor:
    """FFmpeg-based feature extraction for AI metadata cache (M2-006)."""

    SAMPLE_EVERY_N_FRAMES = 30
    HISTOGRAM_SIZE = 16

    def __init__(
        self,
        processor: MediaProcessor | None = None,
        runner: FFmpegRunner | None = None,
    ) -> None:
        self._processor = processor or MediaProcessor()
        self._runner = runner or self._processor.runner

    async def extract_visual(
        self,
        video: Path,
        *,
        ctx: ProcessingContext | None = None,
        scenes_cache_path: Path | None = None,
    ) -> VisualMetadata:
        ctx = ctx or ProcessingContext()
        probe = await self._processor.probe(video, ctx=ctx)
        duration_ms = probe.duration_ms

        scenes = await self._load_or_detect_scenes(video, scenes_cache_path, ctx=ctx)
        keyframes = await self._detect_keyframes(video, ctx=ctx)
        y_stats = await self._sample_signalstats(video, ctx=ctx)

        brightness = _brightness_from_stats(y_stats)
        motion_score = _motion_score_from_stats(y_stats, scenes, duration_ms)
        sharpness = await self._estimate_sharpness(video, ctx=ctx)
        blur_score = max(0.0, min(1.0, 1.0 - sharpness))
        histogram = await self._sample_color_histogram(video, duration_ms, ctx=ctx)
        camera = _camera_movement_from_metrics(motion_score, scenes, duration_ms)

        return VisualMetadata(
            scenes=scenes,
            motion_score=motion_score,
            camera_movement=camera,
            brightness=brightness,
            color_histogram=histogram,
            blur_score=blur_score,
            sharpness=sharpness,
            keyframes=keyframes,
        )

    async def extract_audio(
        self,
        video: Path,
        *,
        ctx: ProcessingContext | None = None,
        waveform_path: Path | None = None,
        duration_ms: int | None = None,
    ) -> AudioMetadata:
        ctx = ctx or ProcessingContext()
        if duration_ms is None:
            probe = await self._processor.probe(video, ctx=ctx)
            duration_ms = probe.duration_ms

        stderr = await self._runner.run(
            [
                self._runner.ffmpeg_bin,
                "-hide_banner",
                "-i",
                str(video),
                "-af",
                "silencedetect=noise=-35dB:d=0.35,volumedetect",
                "-f",
                "null",
                "-",
            ],
            ctx=ctx,
            operation="metadata_audio",
            duration_seconds=max(duration_ms / 1000.0, 0.1),
        )

        silence_regions = _parse_silence_regions(stderr, duration_ms)
        mean_volume = _first_match(_MEAN_VOLUME_RE, stderr)
        max_volume = _first_match(_MAX_VOLUME_RE, stderr)

        peaks: list[float] = []
        beat_markers: list[BeatMarker] = []
        if waveform_path and waveform_path.is_file():
            peaks, beat_markers = _beats_from_waveform(waveform_path.read_text(), duration_ms)

        speech = _detect_speech(mean_volume, silence_regions, duration_ms)

        return AudioMetadata(
            loudness_lufs=mean_volume,
            mean_volume_db=mean_volume,
            max_volume_db=max_volume,
            peaks=peaks,
            silence_regions=silence_regions,
            beat_markers=beat_markers,
            speech=speech,
        )

    @staticmethod
    def empty_ai_cache() -> AICacheMetadata:
        return AICacheMetadata()

    @staticmethod
    def fingerprint(video: Path) -> str:
        return source_fingerprint(video)

    async def _load_or_detect_scenes(
        self,
        video: Path,
        scenes_cache_path: Path | None,
        *,
        ctx: ProcessingContext,
    ) -> list[SceneMarker]:
        if scenes_cache_path and scenes_cache_path.is_file():
            try:
                raw = json.loads(scenes_cache_path.read_text())
                return [SceneMarker.model_validate(item) for item in raw]
            except (json.JSONDecodeError, ValueError):
                pass
        return await self._processor.detect_scenes(video, ctx=ctx)

    async def _detect_keyframes(
        self,
        video: Path,
        *,
        ctx: ProcessingContext,
    ) -> list[KeyframeMarker]:
        ctx.check_cancelled()
        payload = await self._runner.run_json(
            [
                self._runner.ffprobe_bin,
                "-v",
                "quiet",
                "-select_streams",
                "v:0",
                "-show_frames",
                "-show_entries",
                "frame=key_frame,pkt_pts_time",
                "-of",
                "json",
                str(video),
            ],
            ctx=ctx,
        )
        markers: list[KeyframeMarker] = []
        for frame in payload.get("frames", []):
            if str(frame.get("key_frame")) not in {"1", "True", "true"}:
                continue
            pts = frame.get("pkt_pts_time")
            if pts is None:
                continue
            try:
                markers.append(KeyframeMarker(timestamp_ms=int(float(pts) * 1000)))
            except (TypeError, ValueError):
                continue
        return markers

    async def _sample_signalstats(
        self,
        video: Path,
        *,
        ctx: ProcessingContext,
    ) -> list[dict[str, float]]:
        stderr = await self._runner.run(
            [
                self._runner.ffmpeg_bin,
                "-hide_banner",
                "-i",
                str(video),
                "-vf",
                f"select='not(mod(n\\,{self.SAMPLE_EVERY_N_FRAMES}))',signalstats,metadata=mode=print:file=-",
                "-an",
                "-f",
                "null",
                "-",
            ],
            ctx=ctx,
            operation="metadata_visual_stats",
        )
        samples: list[dict[str, float]] = []
        current: dict[str, float] = {}
        for line in stderr.splitlines():
            yavg = _YAVG_RE.search(line)
            if yavg:
                current["yavg"] = float(yavg.group(1))
            ymin = _YMIN_RE.search(line)
            if ymin:
                current["ymin"] = float(ymin.group(1))
            ymax = _YMAX_RE.search(line)
            if ymax:
                current["ymax"] = float(ymax.group(1))
            if "yavg" in current and "ymin" in current and "ymax" in current:
                samples.append(dict(current))
                current = {}
        return samples

    async def _estimate_sharpness(
        self,
        video: Path,
        *,
        ctx: ProcessingContext,
    ) -> float:
        ctx.check_cancelled()
        probe = await self._processor.probe(video, ctx=ctx)
        seek_s = max((probe.duration_ms / 1000.0) * 0.25, 0.0)
        raw = await self._runner.run_capture_stdout(
            [
                self._runner.ffmpeg_bin,
                "-hide_banner",
                "-ss",
                f"{seek_s:.3f}",
                "-i",
                str(video),
                "-frames:v",
                "1",
                "-vf",
                "scale=160:90,format=gray",
                "-f",
                "rawvideo",
                "-",
            ],
            ctx=ctx,
        )
        return _edge_variance(raw, 160, 90)

    async def _sample_color_histogram(
        self,
        video: Path,
        duration_ms: int,
        *,
        ctx: ProcessingContext,
    ) -> ColorHistogram:
        ctx.check_cancelled()
        seek_s = max((duration_ms / 1000.0) * 0.5, 0.0)
        raw = await self._runner.run_capture_stdout(
            [
                self._runner.ffmpeg_bin,
                "-hide_banner",
                "-ss",
                f"{seek_s:.3f}",
                "-i",
                str(video),
                "-frames:v",
                "1",
                "-vf",
                f"scale={self.HISTOGRAM_SIZE}:{self.HISTOGRAM_SIZE},format=rgb24",
                "-f",
                "rawvideo",
                "-",
            ],
            ctx=ctx,
        )
        return _histogram_from_rgb(raw, self.HISTOGRAM_SIZE)


def _brightness_from_stats(samples: list[dict[str, float]]) -> BrightnessStats:
    if not samples:
        return BrightnessStats(mean=128.0, min=0.0, max=255.0, std=0.0)
    yavg_values = [sample["yavg"] for sample in samples]
    ymin_values = [sample.get("ymin", sample["yavg"]) for sample in samples]
    ymax_values = [sample.get("ymax", sample["yavg"]) for sample in samples]
    mean = sum(yavg_values) / len(yavg_values)
    std = (sum((value - mean) ** 2 for value in yavg_values) / len(yavg_values)) ** 0.5
    return BrightnessStats(
        mean=round(mean, 2),
        min=round(min(ymin_values), 2),
        max=round(max(ymax_values), 2),
        std=round(std, 2),
    )


def _motion_score_from_stats(
    samples: list[dict[str, float]],
    scenes: list[SceneMarker],
    duration_ms: int,
) -> float:
    if len(samples) >= 2:
        deltas = [abs(samples[i]["yavg"] - samples[i - 1]["yavg"]) for i in range(1, len(samples))]
        frame_motion = min(sum(deltas) / len(deltas) / 32.0, 1.0)
    else:
        frame_motion = 0.0
    scene_rate = len(scenes) / max(duration_ms / 1000.0, 1.0)
    scene_motion = min(scene_rate / 2.0, 1.0)
    return round(min(max(frame_motion * 0.6 + scene_motion * 0.4, 0.0), 1.0), 3)


def _camera_movement_from_metrics(
    motion_score: float,
    scenes: list[SceneMarker],
    duration_ms: int,
) -> CameraMovement:
    scene_rate = len(scenes) / max(duration_ms / 1000.0, 1.0)
    pan = min(motion_score * 0.7 + scene_rate * 0.1, 1.0)
    zoom = min(scene_rate * 0.35, 1.0)
    shake = min(motion_score * 0.45, 1.0)
    if motion_score < 0.15:
        label = "static"
    elif motion_score < 0.45:
        label = "slow"
    elif shake > 0.35:
        label = "handheld"
    else:
        label = "dynamic"
    return CameraMovement(
        label=label,
        pan=round(pan, 3),
        zoom=round(zoom, 3),
        shake=round(shake, 3),
    )


def _edge_variance(raw: bytes, width: int, height: int) -> float:
    if len(raw) < width * height:
        return 0.0
    pixels = raw[: width * height]
    diffs: list[int] = []
    for y in range(height):
        row = y * width
        for x in range(1, width):
            left = pixels[row + x - 1]
            right = pixels[row + x]
            diffs.append(abs(right - left))
    for y in range(1, height):
        for x in range(width):
            up = pixels[(y - 1) * width + x]
            down = pixels[y * width + x]
            diffs.append(abs(down - up))
    if not diffs:
        return 0.0
    mean = sum(diffs) / len(diffs)
    variance = sum((value - mean) ** 2 for value in diffs) / len(diffs)
    return round(min(variance / 2000.0, 1.0), 3)


def _histogram_from_rgb(raw: bytes, size: int) -> ColorHistogram:
    bins = 16
    counts_r = [0] * bins
    counts_g = [0] * bins
    counts_b = [0] * bins
    pixel_count = size * size
    for index in range(min(pixel_count, len(raw) // 3)):
        offset = index * 3
        r, g, b = raw[offset], raw[offset + 1], raw[offset + 2]
        counts_r[r * bins // 256] += 1
        counts_g[g * bins // 256] += 1
        counts_b[b * bins // 256] += 1
    total = max(pixel_count, 1)

    def normalize(values: list[int]) -> list[float]:
        return [round(value / total, 4) for value in values]

    return ColorHistogram(bins=bins, r=normalize(counts_r), g=normalize(counts_g), b=normalize(counts_b))


def _parse_silence_regions(stderr: str, duration_ms: int) -> list[SilenceRegion]:
    regions: list[SilenceRegion] = []
    open_start: float | None = None
    for line in stderr.splitlines():
        start_match = _SILENCE_START_RE.search(line)
        if start_match:
            open_start = float(start_match.group(1))
            continue
        end_match = _SILENCE_END_RE.search(line)
        if end_match and open_start is not None:
            end_s = float(end_match.group(1))
            regions.append(
                SilenceRegion(
                    start_ms=int(open_start * 1000),
                    end_ms=int(end_s * 1000),
                ),
            )
            open_start = None
    if open_start is not None:
        regions.append(
            SilenceRegion(start_ms=int(open_start * 1000), end_ms=duration_ms),
        )
    return regions


def _beats_from_waveform(
    raw: str,
    duration_ms: int,
) -> tuple[list[float], list[BeatMarker]]:
    try:
        payload = json.loads(raw)
        samples = payload.get("samples", [])
    except json.JSONDecodeError:
        return [], []

    if not samples:
        return [], []

    peaks = [float(value) for value in samples]
    threshold = max(max(peaks) * 0.55, 0.05)
    min_gap_ms = 250
    beat_markers: list[BeatMarker] = []
    last_ms = -min_gap_ms

    for index, value in enumerate(peaks):
        if value < threshold:
            continue
        left = peaks[index - 1] if index > 0 else 0.0
        right = peaks[index + 1] if index + 1 < len(peaks) else 0.0
        if value < left or value < right:
            continue
        timestamp_ms = int((index / max(len(peaks) - 1, 1)) * duration_ms)
        if timestamp_ms - last_ms < min_gap_ms:
            continue
        beat_markers.append(BeatMarker(timestamp_ms=timestamp_ms, strength=round(value, 3)))
        last_ms = timestamp_ms

    return peaks, beat_markers


def _detect_speech(
    mean_volume: float | None,
    silence_regions: list[SilenceRegion],
    duration_ms: int,
) -> SpeechDetection:
    if mean_volume is None:
        return SpeechDetection(has_speech=False, speech_ratio=0.0, confidence=0.5)

    silent_ms = sum(region.end_ms - region.start_ms for region in silence_regions)
    speech_ratio = max(0.0, min(1.0, 1.0 - silent_ms / max(duration_ms, 1)))
    has_speech = mean_volume > -45.0 and speech_ratio > 0.15
    confidence = 0.6 if has_speech else 0.7
    return SpeechDetection(
        has_speech=has_speech,
        speech_ratio=round(speech_ratio, 3),
        confidence=confidence,
    )


def _first_match(pattern: re.Pattern[str], text: str) -> float | None:
    match = pattern.search(text)
    if not match:
        return None
    try:
        return float(match.group(1))
    except ValueError:
        return None
