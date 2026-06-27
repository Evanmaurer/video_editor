from __future__ import annotations

import asyncio
from pathlib import Path

from montage_backend.analysis.base import AnalysisModuleId, AnalysisOutput, AnalysisRunContext, Analyzer
from montage_backend.analysis.embedding.engine import EmbeddingEngine, resolve_embedding_engine
from montage_backend.analysis.embedding_analysis import (
    SceneSegmentRef,
    build_embedding_analysis_result,
    build_embedding_records,
    keyframe_timestamps,
    scene_segment_refs,
)
from montage_backend.media.ffmpeg_runner import FFmpegRunner, ProcessingContext
from montage_backend.media.processor import MediaProcessor


class EmbeddingAnalyzer(Analyzer):
    module_id = AnalysisModuleId.EMBEDDING
    version = "embedding-analyzer-v1.0"

    KEYFRAME_INTERVAL_MS = 3000
    MAX_KEYFRAMES = 30

    def __init__(
        self,
        processor: MediaProcessor | None = None,
        runner: FFmpegRunner | None = None,
        embedding_engine: EmbeddingEngine | None = None,
        *,
        prefer_gpu: bool = False,
    ) -> None:
        self._processor = processor or MediaProcessor()
        self._runner = runner or self._processor.runner
        self._embedding_engine = embedding_engine
        self._prefer_gpu = prefer_gpu
        self._resolved_engine: EmbeddingEngine | None = None

    def cache_key(self, source_fingerprint: str, *, frame_rate: float | None = None) -> str:
        fps_part = f"{frame_rate:.3f}" if frame_rate is not None else "unknown"
        engine = self._get_engine()
        return (
            f"{self.module_id.value}:{self.version}:{source_fingerprint}:"
            f"fps={fps_part}:model={engine.model_id}:dims={engine.dimensions}"
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
        engine = self._get_engine()

        await ctx.report(0.0, "Probing video for embeddings")
        ctx.check_cancelled()
        probe = await self._processor.probe(video, ctx=processing_ctx)
        resolved_duration_ms = duration_ms if duration_ms is not None else probe.duration_ms
        resolved_frame_rate = frame_rate if frame_rate is not None else probe.frame_rate
        cache_key = self.cache_key(ctx.source_fingerprint, frame_rate=resolved_frame_rate)

        scene_segments = ctx.extras.get("scene_segments")
        segments = scene_segment_refs(scene_segments, resolved_duration_ms)
        keyframes = keyframe_timestamps(
            resolved_duration_ms,
            interval_ms=self.KEYFRAME_INTERVAL_MS,
            max_frames=self.MAX_KEYFRAMES,
        )

        await ctx.report(0.1, "Embedding clip thumbnail")
        clip_png = await self._export_png_frame(
            video,
            (resolved_duration_ms / 2000.0),
            ctx=processing_ctx,
        )
        clip_vector = await asyncio.to_thread(engine.embed_png, clip_png)

        scene_vectors: list[tuple[SceneSegmentRef, list[float]]] = []
        total_steps = max(len(segments) + len(keyframes), 1)
        step = 0

        for segment in segments:
            ctx.check_cancelled()
            step += 1
            midpoint_s = ((segment.start_ms + segment.end_ms) / 2.0) / 1000.0
            await ctx.report(0.15 + (0.55 * step / total_steps), f"Embedding scene {segment.index + 1}")
            png_bytes = await self._export_png_frame(video, midpoint_s, ctx=processing_ctx)
            vector = await asyncio.to_thread(engine.embed_png, png_bytes)
            scene_vectors.append((segment, vector))

        keyframe_vectors: list[tuple[int, list[float]]] = []
        for timestamp_ms in keyframes:
            ctx.check_cancelled()
            step += 1
            await ctx.report(0.15 + (0.55 * step / total_steps), "Embedding keyframes")
            png_bytes = await self._export_png_frame(
                video,
                timestamp_ms / 1000.0,
                ctx=processing_ctx,
            )
            vector = await asyncio.to_thread(engine.embed_png, png_bytes)
            keyframe_vectors.append((timestamp_ms, vector))

        records = build_embedding_records(
            media_id=ctx.media_id,
            engine=engine,
            clip_vector=clip_vector,
            scene_vectors=scene_vectors,
            keyframe_vectors=keyframe_vectors,
        )
        result = build_embedding_analysis_result(
            analyzer_version=self.version,
            cache_key=cache_key,
            duration_ms=resolved_duration_ms,
            frame_rate=resolved_frame_rate,
            engine=engine,
            records=records,
        )

        await ctx.report(1.0, f"Generated {result.summary.total_embeddings} embeddings")
        return AnalysisOutput(
            module_id=self.module_id.value,
            analyzer_version=self.version,
            cache_key=cache_key,
            payload=result.model_dump(),
            confidence=0.85,
            reasoning=(
                f"Model={engine.model_id}, scenes={result.summary.scene_count}, "
                f"keyframes={result.summary.keyframe_count}"
            ),
        )

    def _get_engine(self) -> EmbeddingEngine:
        if self._embedding_engine is not None:
            return self._embedding_engine
        if self._resolved_engine is None:
            self._resolved_engine = resolve_embedding_engine(prefer_gpu=self._prefer_gpu)
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

    def _build_processing_context(self, ctx: AnalysisRunContext) -> ProcessingContext:
        processing_ctx = ProcessingContext()

        async def on_progress(_operation: str, progress: float, message: str) -> None:
            if ctx.cancel_requested:
                processing_ctx.cancel_event.set()
            ctx.check_cancelled()
            await ctx.report(progress, message)

        processing_ctx.on_progress = on_progress
        return processing_ctx
