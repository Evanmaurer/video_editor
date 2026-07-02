from __future__ import annotations

from collections.abc import Awaitable, Callable

from montage_backend.analysis.albion.albion_analysis import AlbionAnalysisResult, build_albion_analysis_result
from montage_backend.analysis.albion.base import (
    ALBION_FRAMEWORK_VERSION,
    AlbionDetectorContext,
    AlbionDetectorOutput,
    AlbionDetectorProgress,
)
from montage_backend.analysis.albion.detectors.framework_probe import FrameworkProbeDetector
from montage_backend.analysis.albion.detectors.ability_detector import AlbionAbilityDetector
from montage_backend.analysis.albion.detectors.bomb_detector import AlbionBombDetector
from montage_backend.analysis.albion.detectors.combat_detector import AlbionCombatDetector
from montage_backend.analysis.albion.detectors.engagement_detector import AlbionEngagementDetector
from montage_backend.analysis.albion.detectors.highlight_detector import AlbionHighlightDetector
from montage_backend.analysis.albion.detectors.ocr_detector import AlbionOcrDetector
from montage_backend.analysis.albion.detectors.ui_detector import AlbionUiDetector
from montage_backend.analysis.albion.registry import AlbionDetectorRegistry


async def _noop_progress(_progress: AlbionDetectorProgress) -> None:
    return None


class AlbionAnalysisEngine:
    """Orchestrates Albion detector plugins with cache validation and incremental updates."""

    def __init__(self, registry: AlbionDetectorRegistry) -> None:
        self._registry = registry

    @property
    def registry(self) -> AlbionDetectorRegistry:
        return self._registry

    def composite_cache_key(
        self,
        source_fingerprint: str,
        *,
        frame_rate: float | None = None,
    ) -> str:
        fps_part = f"{frame_rate:.3f}" if frame_rate is not None else "unknown"
        detector_parts = []
        for detector_id in self._registry.list_detectors():
            detector = self._registry.get(detector_id)
            detector_parts.append(
                f"{detector_id}@{detector.version}:{detector.cache_key(source_fingerprint, frame_rate=frame_rate)}",
            )
        joined = "|".join(detector_parts)
        return f"{ALBION_FRAMEWORK_VERSION}:{source_fingerprint}:fps={fps_part}:{joined}"

    def is_cache_valid(
        self,
        cached_version: str,
        cached_key: str,
        source_fingerprint: str,
        *,
        frame_rate: float | None = None,
    ) -> bool:
        expected = self.composite_cache_key(source_fingerprint, frame_rate=frame_rate)
        return cached_version == ALBION_FRAMEWORK_VERSION and cached_key == expected

    async def analyze(
        self,
        ctx: AlbionDetectorContext,
        *,
        video_path: str,
        duration_ms: int | None,
        frame_rate: float | None,
        on_incremental: Callable[[dict[str, AlbionDetectorOutput]], Awaitable[None] | None] | None = None,
    ) -> AlbionAnalysisResult:
        detector_ids = self._registry.list_detectors()
        if not detector_ids:
            return build_albion_analysis_result(
                cache_key=self.composite_cache_key(ctx.source_fingerprint, frame_rate=frame_rate),
                duration_ms=duration_ms or 0,
                frame_rate=frame_rate or 0.0,
                detector_results={},
                gpu_enabled=ctx.gpu_enabled,
            )

        prior_caches: dict[str, dict] = dict(ctx.extras.get("detector_caches", {}))
        detector_results: dict[str, AlbionDetectorOutput] = {}
        total = len(detector_ids)

        for index, detector_id in enumerate(detector_ids):
            ctx.check_cancelled()
            detector = self._registry.get(detector_id)
            detector_cache = prior_caches.get(detector_id)
            expected_key = detector.cache_key(ctx.source_fingerprint, frame_rate=frame_rate)

            prior_result = ctx.extras.get("detector_results", {}).get(detector_id)
            if (
                isinstance(prior_result, dict)
                and prior_result.get("detector_id") == detector_id
                and detector_cache is not None
                and detector.is_cache_valid(
                    detector_cache.get("detector_version", ""),
                    detector_cache.get("cache_key", ""),
                    ctx.source_fingerprint,
                    frame_rate=frame_rate,
                )
            ):
                cached_output = AlbionDetectorOutput.model_validate(prior_result)
                if cached_output.cache_key == expected_key:
                    detector_results[detector_id] = cached_output
                    ctx.extras["detector_results"] = {
                        key: value.model_dump(mode="json")
                        for key, value in detector_results.items()
                    }
                    base_progress = index / total
                    await ctx.report(base_progress, f"Cache hit for {detector_id}")
                    if on_incremental is not None:
                        result = on_incremental(dict(detector_results))
                        if result is not None:
                            await result
                    continue

            parent_callback = ctx._on_progress

            async def detector_progress(progress: AlbionDetectorProgress) -> None:
                detector_weight = 1.0 / total
                base = index / total
                scaled = base + (progress.progress * detector_weight)
                scaled_progress = AlbionDetectorProgress(
                    detector_id=detector_id,
                    progress=scaled,
                    message=f"{detector_id}: {progress.message}",
                )
                ctx._progress = scaled_progress
                if parent_callback is not None:
                    result = parent_callback(scaled_progress)
                    if result is not None:
                        await result

            ctx.bind_progress(detector_progress)
            try:
                await detector.initialize(ctx)
                ctx.check_cancelled()
                output = await detector.analyze(
                    ctx,
                    video_path=video_path,
                    duration_ms=duration_ms,
                    frame_rate=frame_rate,
                )
                detector_results[detector_id] = output
                ctx.extras["detector_results"] = {
                    key: value.model_dump(mode="json") for key, value in detector_results.items()
                }
                if on_incremental is not None:
                    result = on_incremental(dict(detector_results))
                    if result is not None:
                        await result
            finally:
                ctx.bind_progress(parent_callback if parent_callback is not None else _noop_progress)

        return build_albion_analysis_result(
            cache_key=self.composite_cache_key(ctx.source_fingerprint, frame_rate=frame_rate),
            duration_ms=duration_ms or 0,
            frame_rate=frame_rate or 0.0,
            detector_results=detector_results,
            gpu_enabled=ctx.gpu_enabled,
        )


def build_default_albion_registry() -> AlbionDetectorRegistry:
    registry = AlbionDetectorRegistry()
    registry.register(FrameworkProbeDetector())
    registry.register(AlbionUiDetector())
    registry.register(AlbionOcrDetector())
    registry.register(AlbionAbilityDetector())
    registry.register(AlbionCombatDetector())
    registry.register(AlbionBombDetector())
    registry.register(AlbionEngagementDetector())
    registry.register(AlbionHighlightDetector())
    return registry
