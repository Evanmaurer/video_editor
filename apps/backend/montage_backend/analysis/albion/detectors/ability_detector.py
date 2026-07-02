from __future__ import annotations

from montage_backend.analysis.albion.ability.albion_ability_analysis import (
    ALBION_ABILITY_DETECTOR_VERSION,
    DEFAULT_WINDOW_MS,
    AlbionAbilityEventType,
)
from montage_backend.analysis.albion.ability.catalog import catalog_cache_token, get_catalog
from montage_backend.analysis.albion.ability.pipeline import (
    build_detector_cache_key,
    run_albion_ability_pipeline,
)
from montage_backend.analysis.albion.base import (
    AlbionDetector,
    AlbionDetectorContext,
    AlbionDetectorEvent,
    AlbionDetectorId,
    AlbionDetectorOutput,
)


class AlbionAbilityDetector(AlbionDetector):
    """Configurable Albion ability activation and cooldown tracking."""

    detector_id = AlbionDetectorId.ABILITY
    version = ALBION_ABILITY_DETECTOR_VERSION

    SAMPLE_INTERVAL_MS = 2000
    WINDOW_MS = DEFAULT_WINDOW_MS

    def __init__(self, *, catalog_id: str | None = None) -> None:
        self._catalog_id = catalog_id

    def cache_key(self, source_fingerprint: str, *, frame_rate: float | None = None) -> str:
        catalog = get_catalog(self._catalog_id)
        return build_detector_cache_key(
            source_fingerprint,
            frame_rate=frame_rate,
            catalog_id=catalog.id,
            catalog_token=catalog_cache_token(catalog),
            sample_interval_ms=self.SAMPLE_INTERVAL_MS,
            window_ms=self.WINDOW_MS,
            reused_albion_ocr=False,
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
        return cached_key == base or cached_key.startswith(f"{base}:")

    async def initialize(self, ctx: AlbionDetectorContext) -> None:
        ctx.check_cancelled()
        catalog = get_catalog(self._catalog_id)
        await ctx.report(0.0, f"Albion ability catalog ready ({catalog.id}, {len(catalog.abilities)} abilities)")

    async def analyze(
        self,
        ctx: AlbionDetectorContext,
        *,
        video_path: str,
        duration_ms: int | None,
        frame_rate: float | None,
    ) -> AlbionDetectorOutput:
        _ = video_path
        await ctx.report(0.1, "Resolving OCR sources for ability recognition")
        ctx.check_cancelled()

        albion_ocr_payload = self._resolve_albion_ocr_payload(ctx)
        m3_ocr_payload = ctx.extras.get("ocr_analysis")
        resolved_duration_ms = duration_ms or 0
        resolved_frame_rate = frame_rate or 0.0

        if albion_ocr_payload:
            resolved_duration_ms = int(albion_ocr_payload.get("duration_ms", resolved_duration_ms))
            resolved_frame_rate = float(albion_ocr_payload.get("frame_rate", resolved_frame_rate))
        elif m3_ocr_payload is not None:
            if isinstance(m3_ocr_payload, dict):
                resolved_duration_ms = int(m3_ocr_payload.get("duration_ms", resolved_duration_ms))
                resolved_frame_rate = float(m3_ocr_payload.get("frame_rate", resolved_frame_rate))
            else:
                resolved_duration_ms = m3_ocr_payload.duration_ms
                resolved_frame_rate = m3_ocr_payload.frame_rate

        result = run_albion_ability_pipeline(
            source_fingerprint=ctx.source_fingerprint,
            duration_ms=resolved_duration_ms,
            frame_rate=resolved_frame_rate,
            sample_interval_ms=self.SAMPLE_INTERVAL_MS,
            window_ms=self.WINDOW_MS,
            albion_ocr_payload=albion_ocr_payload,
            m3_ocr_payload=m3_ocr_payload,
            catalog_id=self._catalog_id,
        )

        events = [
            AlbionDetectorEvent(
                event_type=event.event_type.value,
                timestamp_ms=event.timestamp_ms,
                confidence=event.confidence,
                reasoning=f"Ability {event.ability_name} ({event.event_type.value})",
                metadata={
                    "ability_id": event.ability_id,
                    "ability_name": event.ability_name,
                    "is_ultimate": event.is_ultimate,
                    "cooldown_ms": event.cooldown_ms,
                    "window_start_ms": event.window_start_ms,
                    "window_end_ms": event.window_end_ms,
                    **event.metadata,
                },
            )
            for event in result.events
            if event.event_type
            in {
                AlbionAbilityEventType.ACTIVATION,
                AlbionAbilityEventType.ULTIMATE_ACTIVATION,
                AlbionAbilityEventType.COOLDOWN_READY,
            }
        ]

        confidence = 0.5
        if result.summary.activation_count > 0:
            confidence = min(0.96, 0.68 + result.summary.unique_ability_count * 0.05)

        reasoning = (
            f"Albion abilities ({result.catalog_id}) found {result.summary.activation_count} activations "
            f"and {result.summary.cooldown_event_count} cooldown events"
        )
        if result.summary.reused_albion_ocr:
            reasoning += " (from Albion OCR cache)"
        elif result.summary.mention_count > 0:
            reasoning += " (from M3 OCR reclassification)"

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

    @staticmethod
    def _resolve_albion_ocr_payload(ctx: AlbionDetectorContext) -> dict | None:
        detector_results = ctx.extras.get("detector_results", {})
        if not isinstance(detector_results, dict):
            return None
        ocr_result = detector_results.get("ocr")
        if not isinstance(ocr_result, dict):
            return None
        payload = ocr_result.get("payload")
        if isinstance(payload, dict) and payload.get("detections") is not None:
            return payload
        return None
