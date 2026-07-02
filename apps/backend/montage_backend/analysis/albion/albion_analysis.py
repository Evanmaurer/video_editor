from __future__ import annotations

from pydantic import BaseModel, Field

from montage_backend.analysis.albion.base import ALBION_FRAMEWORK_VERSION, AlbionDetectorOutput


class AlbionDetectorCacheEntry(BaseModel):
    detector_id: str
    detector_version: str
    cache_key: str
    confidence: float = Field(ge=0.0, le=1.0)
    reasoning: str = ""
    event_count: int = 0


class AlbionAnalysisSummary(BaseModel):
    detector_count: int
    event_count: int
    gpu_enabled: bool
    detector_ids: list[str] = Field(default_factory=list)


class AlbionAnalysisResult(BaseModel):
    analyzer_version: str = ALBION_FRAMEWORK_VERSION
    cache_key: str
    duration_ms: int
    frame_rate: float
    summary: AlbionAnalysisSummary
    detector_results: dict[str, AlbionDetectorOutput] = Field(default_factory=dict)
    detector_caches: dict[str, AlbionDetectorCacheEntry] = Field(default_factory=dict)


def build_albion_analysis_result(
    *,
    cache_key: str,
    duration_ms: int,
    frame_rate: float,
    detector_results: dict[str, AlbionDetectorOutput],
    gpu_enabled: bool,
) -> AlbionAnalysisResult:
    detector_caches = {
        detector_id: AlbionDetectorCacheEntry(
            detector_id=detector_id,
            detector_version=result.detector_version,
            cache_key=result.cache_key,
            confidence=result.confidence,
            reasoning=result.reasoning,
            event_count=len(result.events),
        )
        for detector_id, result in detector_results.items()
    }
    event_count = sum(len(result.events) for result in detector_results.values())
    return AlbionAnalysisResult(
        cache_key=cache_key,
        duration_ms=duration_ms,
        frame_rate=frame_rate,
        summary=AlbionAnalysisSummary(
            detector_count=len(detector_results),
            event_count=event_count,
            gpu_enabled=gpu_enabled,
            detector_ids=sorted(detector_results.keys()),
        ),
        detector_results=detector_results,
        detector_caches=detector_caches,
    )
