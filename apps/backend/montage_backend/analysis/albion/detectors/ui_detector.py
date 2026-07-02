from __future__ import annotations

from pathlib import Path

from montage_backend.analysis.albion.base import (
    AlbionDetector,
    AlbionDetectorContext,
    AlbionDetectorEvent,
    AlbionDetectorId,
    AlbionDetectorOutput,
)
from montage_backend.analysis.albion.ui.albion_ui_analysis import (
    ALBION_UI_DETECTOR_VERSION,
    DEFAULT_WINDOW_MS,
    AlbionUiElementType,
)
from montage_backend.analysis.albion.ui.engine import AlbionUiDetectionEngine, resolve_ui_detection_engine
from montage_backend.analysis.albion.ui.pipeline import (
    build_detector_cache_key,
    reclassify_m3_object_result,
    resolve_pipeline_template,
    run_albion_ui_pipeline,
)
from montage_backend.analysis.ocr_analysis import sample_timestamps_ms
from montage_backend.media.ffmpeg_runner import FFmpegRunner, ProcessingContext
from montage_backend.media.processor import MediaProcessor

EVENT_ELEMENTS = {
    AlbionUiElementType.KILL_FEED,
    AlbionUiElementType.PARTY_FRAME,
    AlbionUiElementType.HEALTH_BAR,
    AlbionUiElementType.SPELL_EFFECT,
}


class AlbionUiDetector(AlbionDetector):
    """Albion HUD recognition using configurable UI templates and per-window caching."""

    detector_id = AlbionDetectorId.UI
    version = ALBION_UI_DETECTOR_VERSION

    SAMPLE_INTERVAL_MS = 2000
    MAX_FRAMES = 60
    WINDOW_MS = DEFAULT_WINDOW_MS
    DEFAULT_FRAME_WIDTH = 1920
    DEFAULT_FRAME_HEIGHT = 1080

    def __init__(
        self,
        processor: MediaProcessor | None = None,
        runner: FFmpegRunner | None = None,
        ui_engine: AlbionUiDetectionEngine | None = None,
        template_id: str | None = None,
    ) -> None:
        self._processor = processor or MediaProcessor()
        self._runner = runner or self._processor.runner
        self._ui_engine = ui_engine
        self._resolved_engine: AlbionUiDetectionEngine | None = None
        self._template_id = template_id

    def cache_key(self, source_fingerprint: str, *, frame_rate: float | None = None) -> str:
        engine = self._get_engine()
        template = resolve_pipeline_template(
            frame_width=self.DEFAULT_FRAME_WIDTH,
            frame_height=self.DEFAULT_FRAME_HEIGHT,
            template_id=self._template_id,
        )
        return build_detector_cache_key(
            source_fingerprint,
            frame_rate=frame_rate,
            template_id=template.id,
            sample_interval_ms=self.SAMPLE_INTERVAL_MS,
            window_ms=self.WINDOW_MS,
            engine_id=engine.engine_id,
            engine_version=engine.version,
            reused_m3_object=False,
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
        engine = self._get_engine()
        template = resolve_pipeline_template(
            frame_width=self.DEFAULT_FRAME_WIDTH,
            frame_height=self.DEFAULT_FRAME_HEIGHT,
            template_id=self._template_id,
        )
        await ctx.report(0.0, f"Albion UI engine ready ({engine.engine_id}, template={template.id})")

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
        engine = self._get_engine()

        await ctx.report(0.05, "Preparing Albion UI pipeline")
        ctx.check_cancelled()

        m3_payload = ctx.extras.get("object_analysis")
        frame_width = self.DEFAULT_FRAME_WIDTH
        frame_height = self.DEFAULT_FRAME_HEIGHT

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
            frame_width = probe.width or self.DEFAULT_FRAME_WIDTH
            frame_height = probe.height or self.DEFAULT_FRAME_HEIGHT

        template = resolve_pipeline_template(
            frame_width=frame_width,
            frame_height=frame_height,
            template_id=self._template_id,
        )

        if m3_payload:
            await ctx.report(0.2, "Reclassifying cached M3 object detections for Albion UI")
            result = reclassify_m3_object_result(
                m3_payload,
                source_fingerprint=ctx.source_fingerprint,
                template_id=template.id,
                window_ms=self.WINDOW_MS,
                sample_interval_ms=self.SAMPLE_INTERVAL_MS,
            )
            base_key = self.cache_key(ctx.source_fingerprint, frame_rate=resolved_frame_rate)
            m3_key = (
                m3_payload.get("cache_key", "unknown")
                if isinstance(m3_payload, dict)
                else m3_payload.cache_key
            )
            result = result.model_copy(update={"cache_key": f"{base_key}:m3:{m3_key}"})
        else:
            timestamps = sample_timestamps_ms(
                resolved_duration_ms,
                interval_ms=self.SAMPLE_INTERVAL_MS,
                max_frames=self.MAX_FRAMES,
            )
            result = await run_albion_ui_pipeline(
                source_fingerprint=ctx.source_fingerprint,
                duration_ms=resolved_duration_ms,
                frame_rate=resolved_frame_rate,
                sample_interval_ms=self.SAMPLE_INTERVAL_MS,
                window_ms=self.WINDOW_MS,
                timestamps=timestamps,
                template=template,
                engine=engine,
                video_path=video,
                export_png_frame=lambda path, ts: self._export_png_frame(path, ts, ctx=processing_ctx),
                check_cancelled=ctx.check_cancelled,
                report_progress=ctx.report,
            )

        events = [
            AlbionDetectorEvent(
                event_type=detection.element_type.value,
                timestamp_ms=detection.timestamp_ms,
                confidence=detection.confidence,
                reasoning=f"UI: {detection.label}",
                metadata={
                    "label": detection.label,
                    "template_id": detection.template_id,
                    "bbox": detection.bbox.model_dump(mode="json"),
                    "window_start_ms": detection.window_start_ms,
                    "window_end_ms": detection.window_end_ms,
                    **detection.metadata,
                },
            )
            for detection in result.detections
            if detection.element_type in EVENT_ELEMENTS
        ]

        confidence = 0.5 if result.summary.engine_id == "unavailable" else 0.84
        if result.summary.detection_count > 0:
            confidence = min(0.96, 0.7 + result.summary.unique_element_count * 0.02)

        reasoning = (
            f"Albion UI ({result.summary.engine_id}, template={result.template_id}) found "
            f"{result.summary.detection_count} elements across {result.summary.window_count} frame windows"
        )
        if result.summary.reused_m3_object:
            reasoning += " (reclassified from M3 object cache)"

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

    def _get_engine(self) -> AlbionUiDetectionEngine:
        if self._ui_engine is not None:
            return self._ui_engine
        if self._resolved_engine is None:
            self._resolved_engine = resolve_ui_detection_engine()
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
