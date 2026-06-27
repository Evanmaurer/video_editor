from __future__ import annotations

from pathlib import Path

from montage_backend.analysis.base import AnalysisModuleId, AnalysisOutput, AnalysisRunContext, Analyzer
from montage_backend.analysis.motion_analysis import build_motion_analysis_result
from montage_backend.media.ffmpeg_runner import FFmpegRunner, ProcessingContext
from montage_backend.media.processor import MediaProcessor


class MotionAnalyzer(Analyzer):
    module_id = AnalysisModuleId.MOTION
    version = "motion-analyzer-v1.0"

    SAMPLE_EVERY_N_FRAMES = 15
    WINDOW_MS = 1000

    def __init__(
        self,
        processor: MediaProcessor | None = None,
        runner: FFmpegRunner | None = None,
    ) -> None:
        self._processor = processor or MediaProcessor()
        self._runner = runner or self._processor.runner

    def cache_key(self, source_fingerprint: str, *, frame_rate: float | None = None) -> str:
        fps_part = f"{frame_rate:.3f}" if frame_rate is not None else "unknown"
        return (
            f"{self.module_id.value}:{self.version}:{source_fingerprint}:"
            f"fps={fps_part}:window={self.WINDOW_MS}:stride={self.SAMPLE_EVERY_N_FRAMES}"
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
        video = Path(video_path)
        processing_ctx = self._build_processing_context(ctx)

        await ctx.report(0.0, "Probing video")
        ctx.check_cancelled()
        probe = await self._processor.probe(video, ctx=processing_ctx)
        resolved_duration_ms = duration_ms if duration_ms is not None else probe.duration_ms
        resolved_frame_rate = frame_rate if frame_rate is not None else probe.frame_rate
        duration_s = resolved_duration_ms / 1000.0
        cache_key = self.cache_key(ctx.source_fingerprint, frame_rate=resolved_frame_rate)

        await ctx.report(0.15, "Sampling motion signal")
        signalstats_stderr = await self._runner.run(
            [
                self._runner.ffmpeg_bin,
                "-hide_banner",
                "-i",
                str(video),
                "-vf",
                (
                    f"select='not(mod(n\\,{self.SAMPLE_EVERY_N_FRAMES}))',"
                    "signalstats,metadata=mode=print:file=-"
                ),
                "-an",
                "-f",
                "null",
                "-",
            ],
            ctx=processing_ctx,
            operation="motion_signalstats",
            duration_seconds=duration_s,
        )
        ctx.check_cancelled()

        result = build_motion_analysis_result(
            analyzer_version=self.version,
            cache_key=cache_key,
            frame_rate=resolved_frame_rate,
            duration_ms=resolved_duration_ms,
            signalstats_stderr=signalstats_stderr,
            window_ms=self.WINDOW_MS,
            sample_stride_frames=self.SAMPLE_EVERY_N_FRAMES,
        )

        await ctx.report(1.0, f"Analyzed {len(result.windows)} motion windows")
        avg_confidence = (
            sum(window.confidence for window in result.windows) / len(result.windows)
            if result.windows
            else 1.0
        )
        return AnalysisOutput(
            module_id=self.module_id.value,
            analyzer_version=self.version,
            cache_key=cache_key,
            payload=result.model_dump(),
            confidence=round(avg_confidence, 3),
            reasoning=(
                f"Dominant movement: {result.summary.dominant_movement_class.value}, "
                f"overall score: {result.summary.overall_motion_score}"
            ),
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
