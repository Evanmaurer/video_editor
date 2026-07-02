from __future__ import annotations

from pathlib import Path

from montage_backend.analysis.albion.albion_analysis import AlbionAnalysisResult
from montage_backend.analysis.albion.base import ALBION_FRAMEWORK_VERSION, AlbionDetectorContext
from montage_backend.analysis.albion.registry import AlbionDetectorRegistry
from montage_backend.analysis.albion.runtime import AlbionAnalysisEngine, build_default_albion_registry
from montage_backend.analysis.base import AnalysisModuleId, AnalysisOutput, AnalysisRunContext, Analyzer
from montage_backend.media.processor import MediaProcessor


class AlbionAnalyzer(Analyzer):
    """Top-level M3 analysis module that orchestrates Albion-specific detector plugins."""

    module_id = AnalysisModuleId.ALBION
    version = ALBION_FRAMEWORK_VERSION

    def __init__(
        self,
        processor: MediaProcessor | None = None,
        detector_registry: AlbionDetectorRegistry | None = None,
    ) -> None:
        self._processor = processor or MediaProcessor()
        registry = detector_registry or build_default_albion_registry()
        self._engine = AlbionAnalysisEngine(registry)

    @property
    def detector_registry(self) -> AlbionDetectorRegistry:
        return self._engine.registry

    def cache_key(self, source_fingerprint: str, *, frame_rate: float | None = None) -> str:
        return self._engine.composite_cache_key(source_fingerprint, frame_rate=frame_rate)

    def is_cache_valid(
        self,
        cached_version: str,
        cached_key: str,
        source_fingerprint: str,
        *,
        frame_rate: float | None = None,
    ) -> bool:
        return self._engine.is_cache_valid(
            cached_version,
            cached_key,
            source_fingerprint,
            frame_rate=frame_rate,
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
        await ctx.report(0.0, "Starting Albion analysis")
        ctx.check_cancelled()

        probe = await self._processor.probe(video)
        resolved_duration_ms = duration_ms if duration_ms is not None else probe.duration_ms
        resolved_frame_rate = frame_rate if frame_rate is not None else probe.frame_rate

        albion_ctx = AlbionDetectorContext(
            project_id=ctx.project_id,
            media_id=ctx.media_id,
            source_fingerprint=ctx.source_fingerprint,
            gpu_enabled=ctx.gpu_enabled,
            extras=dict(ctx.extras),
        )

        prior_payload = ctx.extras.get("prior_albion_payload")
        if isinstance(prior_payload, dict):
            albion_ctx.extras["detector_caches"] = prior_payload.get("detector_caches", {})
            albion_ctx.extras["detector_results"] = prior_payload.get("detector_results", {})

        async def aggregate_progress(progress) -> None:
            await ctx.report(0.05 + (progress.progress * 0.9), progress.message)

        albion_ctx.bind_progress(aggregate_progress)

        partial_payload: dict = {}

        async def on_incremental(detector_results) -> None:
            partial = build_partial_payload(
                detector_results=detector_results,
                duration_ms=resolved_duration_ms or 0,
                frame_rate=resolved_frame_rate or 0.0,
                cache_key=self.cache_key(ctx.source_fingerprint, frame_rate=resolved_frame_rate),
                gpu_enabled=ctx.gpu_enabled,
            )
            partial_payload.update(partial)
            await ctx.report(
                min(0.05 + (len(detector_results) / max(len(self._engine.registry.list_detectors()), 1)) * 0.9, 0.95),
                f"Completed {len(detector_results)} Albion detectors",
            )

        result = await self._engine.analyze(
            albion_ctx,
            video_path=video_path,
            duration_ms=resolved_duration_ms,
            frame_rate=resolved_frame_rate,
            on_incremental=on_incremental,
        )
        payload = result.model_dump(mode="json")
        if partial_payload:
            payload["incremental_updates"] = partial_payload.get("incremental_updates", 0) + 1

        avg_confidence = (
            round(
                sum(item.confidence for item in result.detector_results.values())
                / len(result.detector_results),
                2,
            )
            if result.detector_results
            else 0.0
        )
        reasoning = (
            f"Ran {result.summary.detector_count} Albion detectors; "
            f"{result.summary.event_count} events detected."
        )
        await ctx.report(1.0, "Albion analysis complete")
        return AnalysisOutput(
            module_id=self.module_id.value,
            analyzer_version=self.version,
            cache_key=result.cache_key,
            payload=payload,
            confidence=avg_confidence,
            reasoning=reasoning,
        )

    async def cancel(self, ctx: AnalysisRunContext) -> None:
        await super().cancel(ctx)
        for detector_id in self._engine.registry.list_detectors():
            detector = self._engine.registry.get(detector_id)
            albion_ctx = AlbionDetectorContext(
                project_id=ctx.project_id,
                media_id=ctx.media_id,
                source_fingerprint=ctx.source_fingerprint,
                gpu_enabled=ctx.gpu_enabled,
                cancel_requested=True,
            )
            await detector.cancel(albion_ctx)


def build_partial_payload(
    *,
    detector_results: dict,
    duration_ms: int,
    frame_rate: float,
    cache_key: str,
    gpu_enabled: bool,
) -> dict:
    from montage_backend.analysis.albion.albion_analysis import build_albion_analysis_result
    from montage_backend.analysis.albion.base import AlbionDetectorOutput

    typed_results = {
        key: value if isinstance(value, AlbionDetectorOutput) else AlbionDetectorOutput.model_validate(value)
        for key, value in detector_results.items()
    }
    partial = build_albion_analysis_result(
        cache_key=cache_key,
        duration_ms=duration_ms,
        frame_rate=frame_rate,
        detector_results=typed_results,
        gpu_enabled=gpu_enabled,
    )
    return {
        "partial_result": partial.model_dump(mode="json"),
        "incremental_updates": 1,
    }
