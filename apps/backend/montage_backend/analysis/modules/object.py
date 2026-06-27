from __future__ import annotations

import asyncio
from pathlib import Path

from montage_backend.analysis.base import AnalysisModuleId, AnalysisOutput, AnalysisRunContext, Analyzer
from montage_backend.analysis.object.engine import ObjectDetector, resolve_object_detector
from montage_backend.analysis.object_analysis import (
    build_object_analysis_result,
    raw_to_detection,
    sample_timestamps_ms,
)
from montage_backend.media.ffmpeg_runner import FFmpegRunner, ProcessingContext
from montage_backend.media.processor import MediaProcessor


class ObjectAnalyzer(Analyzer):
    module_id = AnalysisModuleId.OBJECT
    version = "object-analyzer-v1.0"

    SAMPLE_INTERVAL_MS = 2500
    MAX_FRAMES = 40

    def __init__(
        self,
        processor: MediaProcessor | None = None,
        runner: FFmpegRunner | None = None,
        object_detector: ObjectDetector | None = None,
        *,
        prefer_gpu: bool = False,
    ) -> None:
        self._processor = processor or MediaProcessor()
        self._runner = runner or self._processor.runner
        self._object_detector = object_detector
        self._prefer_gpu = prefer_gpu
        self._resolved_detector: ObjectDetector | None = None

    def cache_key(self, source_fingerprint: str, *, frame_rate: float | None = None) -> str:
        fps_part = f"{frame_rate:.3f}" if frame_rate is not None else "unknown"
        detector = self._get_detector()
        return (
            f"{self.module_id.value}:{self.version}:{source_fingerprint}:"
            f"fps={fps_part}:interval={self.SAMPLE_INTERVAL_MS}:max={self.MAX_FRAMES}:"
            f"detector={detector.detector_id}"
        )

    async def analyze(
        self,
        ctx: AnalysisRunContext,
        *,
        video_path: str,
        duration_ms: int | None,
        frame_rate: float | None,
        frame_count: int | None,
    ) -> AnalysisOutput:
        _ = frame_count
        video = Path(video_path)
        processing_ctx = self._build_processing_context(ctx)
        detector = self._get_detector()

        await ctx.report(0.0, "Probing video for object detection")
        ctx.check_cancelled()
        probe = await self._processor.probe(video, ctx=processing_ctx)
        resolved_duration_ms = duration_ms if duration_ms is not None else probe.duration_ms
        resolved_frame_rate = frame_rate if frame_rate is not None else probe.frame_rate
        cache_key = self.cache_key(ctx.source_fingerprint, frame_rate=resolved_frame_rate)

        timestamps = sample_timestamps_ms(
            resolved_duration_ms,
            interval_ms=self.SAMPLE_INTERVAL_MS,
            max_frames=self.MAX_FRAMES,
        )
        detections = []
        total = max(len(timestamps), 1)

        for index, timestamp_ms in enumerate(timestamps):
            ctx.check_cancelled()
            progress = 0.1 + (0.85 * (index / total))
            await ctx.report(progress, f"Detecting objects {index + 1}/{total}")

            png_bytes = await self._export_png_frame(
                video,
                timestamp_ms / 1000.0,
                ctx=processing_ctx,
            )
            if not png_bytes:
                continue

            raw_detections = await asyncio.to_thread(detector.detect_png, png_bytes)
            for raw in raw_detections:
                detections.append(
                    raw_to_detection(
                        raw,
                        timestamp_ms=timestamp_ms,
                        frame_rate=resolved_frame_rate,
                    ),
                )

        result = build_object_analysis_result(
            analyzer_version=self.version,
            cache_key=cache_key,
            duration_ms=resolved_duration_ms,
            frame_rate=resolved_frame_rate,
            sample_interval_ms=self.SAMPLE_INTERVAL_MS,
            frames_sampled=len(timestamps),
            detector=detector,
            detections=detections,
        )

        await ctx.report(1.0, f"Detected {result.summary.unique_detection_count} objects")
        confidence = 0.5 if detector.detector_id == "unavailable" else 0.78
        if result.summary.detection_count > 0:
            confidence = min(0.95, 0.72 + result.summary.unique_detection_count * 0.01)

        return AnalysisOutput(
            module_id=self.module_id.value,
            analyzer_version=self.version,
            cache_key=cache_key,
            payload=result.model_dump(),
            confidence=round(confidence, 3),
            reasoning=(
                f"Detector={detector.detector_id}, "
                f"{result.summary.detection_count} detections, "
                f"{result.summary.unique_detection_count} unique"
            ),
        )

    def _get_detector(self) -> ObjectDetector:
        if self._object_detector is not None:
            return self._object_detector
        if self._resolved_detector is None:
            self._resolved_detector = resolve_object_detector(prefer_gpu=self._prefer_gpu)
        return self._resolved_detector

    async def _export_png_frame(
        self,
        video: Path,
        timestamp_s: float,
        *,
        ctx: ProcessingContext,
    ) -> bytes:
        ctx.check_cancelled()
        return await self._runner.run_capture_stdout(
            [
                self._runner.ffmpeg_bin,
                "-hide_banner",
                "-ss",
                f"{timestamp_s:.3f}",
                "-i",
                str(video),
                "-frames:v",
                "1",
                "-f",
                "image2pipe",
                "-vcodec",
                "png",
                "-",
            ],
            ctx=ctx,
        )

    def _build_processing_context(self, ctx: AnalysisRunContext) -> ProcessingContext:
        processing_ctx = ProcessingContext()

        async def on_progress(_operation: str, progress: float, message: str) -> None:
            if ctx.cancel_requested:
                processing_ctx.cancel_event.set()
            ctx.check_cancelled()
            await ctx.report(progress, message)

        processing_ctx.on_progress = on_progress
        return processing_ctx
