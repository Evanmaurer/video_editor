from __future__ import annotations

from pathlib import Path

from montage_backend.analysis.audio_analysis import WINDOW_MS, build_audio_analysis_result, downsample_peaks
from montage_backend.analysis.base import AnalysisModuleId, AnalysisOutput, AnalysisRunContext, Analyzer
from montage_backend.media.ffmpeg_runner import FFmpegRunner, ProcessingContext
from montage_backend.media.processor import MediaProcessor


class AudioAnalyzer(Analyzer):
    module_id = AnalysisModuleId.AUDIO
    version = "audio-analyzer-v1.0"

    WAVEFORM_SAMPLES = 512

    def __init__(
        self,
        processor: MediaProcessor | None = None,
        runner: FFmpegRunner | None = None,
    ) -> None:
        self._processor = processor or MediaProcessor()
        self._runner = runner or self._processor.runner

    def cache_key(self, source_fingerprint: str, *, frame_rate: float | None = None) -> str:
        _ = frame_rate
        return (
            f"{self.module_id.value}:{self.version}:{source_fingerprint}:"
            f"window={WINDOW_MS}:samples={self.WAVEFORM_SAMPLES}"
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
        _ = frame_rate, frame_count
        media_path = Path(video_path)
        processing_ctx = self._build_processing_context(ctx)

        await ctx.report(0.0, "Probing audio")
        ctx.check_cancelled()
        probe = await self._processor.probe(media_path, ctx=processing_ctx)
        resolved_duration_ms = duration_ms if duration_ms is not None else probe.duration_ms
        duration_s = max(resolved_duration_ms / 1000.0, 0.1)
        cache_key = self.cache_key(ctx.source_fingerprint)
        has_audio = probe.audio_sample_rate is not None

        if not has_audio:
            result = build_audio_analysis_result(
                analyzer_version=self.version,
                cache_key=cache_key,
                duration_ms=resolved_duration_ms,
                volume_stderr="",
                ebur128_stderr="",
                peaks=[],
                window_ms=WINDOW_MS,
                has_audio=False,
            )
            return AnalysisOutput(
                module_id=self.module_id.value,
                analyzer_version=self.version,
                cache_key=cache_key,
                payload=result.model_dump(),
                confidence=1.0,
                reasoning="No audio stream detected",
            )

        await ctx.report(0.2, "Detecting loudness and silence")
        volume_stderr = await self._runner.run(
            [
                self._runner.ffmpeg_bin,
                "-hide_banner",
                "-i",
                str(media_path),
                "-vn",
                "-af",
                "silencedetect=noise=-35dB:d=0.35,volumedetect",
                "-f",
                "null",
                "-",
            ],
            ctx=processing_ctx,
            operation="audio_volume",
            duration_seconds=duration_s,
        )
        ctx.check_cancelled()

        await ctx.report(0.45, "Measuring integrated loudness")
        ebur128_stderr = await self._runner.run(
            [
                self._runner.ffmpeg_bin,
                "-hide_banner",
                "-i",
                str(media_path),
                "-vn",
                "-af",
                "ebur128=peak=true",
                "-f",
                "null",
                "-",
            ],
            ctx=processing_ctx,
            operation="audio_ebur128",
            duration_seconds=duration_s,
        )
        ctx.check_cancelled()

        await ctx.report(0.7, "Extracting waveform envelope")
        raw_audio = await self._runner.run_capture_stdout(
            [
                self._runner.ffmpeg_bin,
                "-hide_banner",
                "-i",
                str(media_path),
                "-vn",
                "-ac",
                "1",
                "-f",
                "f32le",
                "-",
            ],
            ctx=processing_ctx,
        )
        peaks = downsample_peaks(raw_audio, self.WAVEFORM_SAMPLES)

        result = build_audio_analysis_result(
            analyzer_version=self.version,
            cache_key=cache_key,
            duration_ms=resolved_duration_ms,
            volume_stderr=volume_stderr,
            ebur128_stderr=ebur128_stderr,
            peaks=peaks,
            window_ms=WINDOW_MS,
            has_audio=True,
        )

        await ctx.report(1.0, f"Detected {len(result.events)} audio events")
        confidence = 0.85 if result.summary.tempo_bpm is not None else 0.75
        return AnalysisOutput(
            module_id=self.module_id.value,
            analyzer_version=self.version,
            cache_key=cache_key,
            payload=result.model_dump(),
            confidence=confidence,
            reasoning=(
                f"Tempo: {result.summary.tempo_bpm or 'unknown'} BPM, "
                f"{result.summary.beat_count} beats, "
                f"music={result.summary.music_probability}, voice={result.summary.voice_probability}"
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
