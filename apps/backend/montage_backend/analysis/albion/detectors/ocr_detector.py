from __future__ import annotations

import asyncio
from pathlib import Path

from montage_backend.analysis.albion.base import (
    AlbionDetector,
    AlbionDetectorContext,
    AlbionDetectorEvent,
    AlbionDetectorId,
    AlbionDetectorOutput,
)
from montage_backend.analysis.albion.ocr.albion_ocr_analysis import (
    ALBION_OCR_DETECTOR_VERSION,
    AlbionOcrCategory,
    DEFAULT_WINDOW_MS,
)
from montage_backend.analysis.albion.ocr.pipeline import (
    build_detector_cache_key,
    reclassify_m3_ocr_result,
    run_albion_ocr_pipeline,
)
from montage_backend.analysis.ocr.engine import OcrEngine, resolve_ocr_engine
from montage_backend.analysis.ocr_analysis import OcrAnalysisResult, sample_timestamps_ms
from montage_backend.media.ffmpeg_runner import FFmpegRunner, ProcessingContext
from montage_backend.media.processor import MediaProcessor

EVENT_CATEGORIES = {
    AlbionOcrCategory.KILL_MESSAGE,
    AlbionOcrCategory.DEATH_MESSAGE,
    AlbionOcrCategory.LOOT_NOTIFICATION,
    AlbionOcrCategory.ABILITY_NAME,
}


class AlbionOcrDetector(AlbionDetector):
    """Albion-specific OCR pipeline with per-frame-window caching."""

    detector_id = AlbionDetectorId.OCR
    version = ALBION_OCR_DETECTOR_VERSION

    SAMPLE_INTERVAL_MS = 1500
    MAX_FRAMES = 80
    WINDOW_MS = DEFAULT_WINDOW_MS

    def __init__(
        self,
        processor: MediaProcessor | None = None,
        runner: FFmpegRunner | None = None,
        ocr_engine: OcrEngine | None = None,
    ) -> None:
        self._processor = processor or MediaProcessor()
        self._runner = runner or self._processor.runner
        self._ocr_engine = ocr_engine
        self._resolved_engine: OcrEngine | None = None

    def cache_key(self, source_fingerprint: str, *, frame_rate: float | None = None) -> str:
        engine = self._get_engine()
        return build_detector_cache_key(
            source_fingerprint,
            frame_rate=frame_rate,
            sample_interval_ms=self.SAMPLE_INTERVAL_MS,
            window_ms=self.WINDOW_MS,
            engine_id=engine.engine_id,
            engine_version=engine.version,
            reused_m3_ocr=False,
        )

    def is_cache_valid(
        self,
        cached_version: str,
        cached_key: str,
        source_fingerprint: str,
        *,
        frame_rate: float | None = None,
    ) -> bool:
        if cached_version != self.version:
            return False
        base = self.cache_key(source_fingerprint, frame_rate=frame_rate)
        return cached_key == base or cached_key.startswith(f"{base}:m3:")

    async def initialize(self, ctx: AlbionDetectorContext) -> None:
        ctx.check_cancelled()
        engine = self._get_engine(prefer_gpu=ctx.gpu_enabled)
        await ctx.report(0.0, f"Albion OCR engine ready ({engine.engine_id})")

    async def analyze(
        self,
        ctx: AlbionDetectorContext,
        *,
        video_path: str,
        duration_ms: int | None,
        frame_rate: float | None,
    ) -> AlbionDetectorOutput:
        video = Path(video_path)
        processing_ctx = self._build_processing_context(ctx)
        engine = self._get_engine(prefer_gpu=ctx.gpu_enabled)

        await ctx.report(0.05, "Preparing Albion OCR pipeline")
        ctx.check_cancelled()

        m3_payload = ctx.extras.get("ocr_analysis")
        if m3_payload:
            if isinstance(m3_payload, dict):
                resolved_duration_ms = duration_ms if duration_ms is not None else int(m3_payload.get("duration_ms", 0))
                resolved_frame_rate = frame_rate if frame_rate is not None else float(m3_payload.get("frame_rate", 0.0))
            else:
                resolved_duration_ms = duration_ms if duration_ms is not None else m3_payload.duration_ms
                resolved_frame_rate = frame_rate if frame_rate is not None else m3_payload.frame_rate
        else:
            probe = await self._processor.probe(video, ctx=processing_ctx)
            resolved_duration_ms = duration_ms if duration_ms is not None else probe.duration_ms
            resolved_frame_rate = frame_rate if frame_rate is not None else probe.frame_rate

        if m3_payload:
            await ctx.report(0.2, "Reclassifying cached M3 OCR for Albion")
            result = reclassify_m3_ocr_result(
                m3_payload,
                source_fingerprint=ctx.source_fingerprint,
                window_ms=self.WINDOW_MS,
                sample_interval_ms=self.SAMPLE_INTERVAL_MS,
            )
            base_key = self.cache_key(ctx.source_fingerprint, frame_rate=resolved_frame_rate)
            m3_key = m3_payload.get("cache_key", "unknown") if isinstance(m3_payload, dict) else m3_payload.cache_key
            result = result.model_copy(update={"cache_key": f"{base_key}:m3:{m3_key}"})
        else:
            timestamps = sample_timestamps_ms(
                resolved_duration_ms,
                interval_ms=self.SAMPLE_INTERVAL_MS,
                max_frames=self.MAX_FRAMES,
            )
            result = await run_albion_ocr_pipeline(
                source_fingerprint=ctx.source_fingerprint,
                duration_ms=resolved_duration_ms,
                frame_rate=resolved_frame_rate,
                sample_interval_ms=self.SAMPLE_INTERVAL_MS,
                window_ms=self.WINDOW_MS,
                timestamps=timestamps,
                engine=engine,
                video_path=video,
                export_png_frame=lambda path, ts: self._export_png_frame(path, ts, ctx=processing_ctx),
                check_cancelled=ctx.check_cancelled,
                report_progress=ctx.report,
            )

        events = [
            AlbionDetectorEvent(
                event_type=detection.category.value,
                timestamp_ms=detection.timestamp_ms,
                confidence=detection.confidence,
                reasoning=f"OCR: {detection.text}",
                metadata={
                    "text": detection.text,
                    "window_start_ms": detection.window_start_ms,
                    "window_end_ms": detection.window_end_ms,
                    **detection.metadata,
                },
            )
            for detection in result.detections
            if detection.category in EVENT_CATEGORIES
        ]

        confidence = 0.5 if result.summary.engine_id == "unavailable" else 0.82
        if result.summary.detection_count > 0:
            confidence = min(0.96, 0.72 + result.summary.unique_text_count * 0.015)

        reasoning = (
            f"Albion OCR ({result.summary.engine_id}) found {result.summary.detection_count} detections "
            f"across {result.summary.window_count} frame windows"
        )
        if result.summary.reused_m3_ocr:
            reasoning += " (reclassified from M3 OCR cache)"

        await ctx.report(1.0, reasoning)
        return AlbionDetectorOutput(
            detector_id=self.detector_id.value,
            detector_version=self.version,
            cache_key=result.cache_key,
            confidence=round(confidence, 3),
            reasoning=reasoning,
            events=events,
            payload=result.model_dump(mode="json"),
        )

    def _get_engine(self, *, prefer_gpu: bool = False) -> OcrEngine:
        if self._ocr_engine is not None:
            return self._ocr_engine
        if self._resolved_engine is None:
            self._resolved_engine = resolve_ocr_engine(prefer_gpu=prefer_gpu)
        return self._resolved_engine

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

    def _build_processing_context(self, ctx: AlbionDetectorContext) -> ProcessingContext:
        processing_ctx = ProcessingContext()

        async def on_progress(_operation: str, progress: float, message: str) -> None:
            if ctx.cancel_requested:
                processing_ctx.cancel_event.set()
            ctx.check_cancelled()
            await ctx.report(progress, message)

        processing_ctx.on_progress = on_progress
        return processing_ctx
