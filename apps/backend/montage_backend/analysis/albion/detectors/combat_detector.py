from __future__ import annotations

from montage_backend.analysis.albion.base import (
    AlbionDetector,
    AlbionDetectorContext,
    AlbionDetectorEvent,
    AlbionDetectorId,
    AlbionDetectorOutput,
)
from montage_backend.analysis.albion.combat.albion_combat_analysis import (
    ALBION_COMBAT_DETECTOR_VERSION,
    AlbionCombatEventType,
)
from montage_backend.analysis.albion.combat.config import config_cache_token, get_combat_config
from montage_backend.analysis.albion.combat.pipeline import build_detector_cache_key, run_albion_combat_pipeline


class AlbionCombatDetector(AlbionDetector):
    """Build searchable combat timeline entries from OCR, abilities, UI, and motion."""

    detector_id = AlbionDetectorId.COMBAT
    version = ALBION_COMBAT_DETECTOR_VERSION

    def __init__(self, *, config_id: str | None = None) -> None:
        self._config_id = config_id

    def cache_key(self, source_fingerprint: str, *, frame_rate: float | None = None) -> str:
        config = get_combat_config(self._config_id)
        return build_detector_cache_key(
            source_fingerprint,
            frame_rate=frame_rate,
            config_id=config.id,
            config_token=config_cache_token(config),
            sample_interval_ms=config.sample_interval_ms,
            window_ms=config.window_ms,
            source_flags="any",
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
        config = get_combat_config(self._config_id)
        await ctx.report(0.0, f"Albion combat config ready ({config.id})")

    async def analyze(
        self,
        ctx: AlbionDetectorContext,
        *,
        video_path: str,
        duration_ms: int | None,
        frame_rate: float | None,
    ) -> AlbionDetectorOutput:
        _ = video_path
        await ctx.report(0.1, "Resolving combat signal sources")
        ctx.check_cancelled()

        albion_ocr_payload = self._resolve_detector_payload(ctx, "ocr")
        albion_ability_payload = self._resolve_detector_payload(ctx, "ability")
        albion_ui_payload = self._resolve_detector_payload(ctx, "ui")
        m3_ocr_payload = ctx.extras.get("ocr_analysis")
        motion_payload = ctx.extras.get("motion_analysis")

        resolved_duration_ms = duration_ms or 0
        resolved_frame_rate = frame_rate or 0.0
        for payload in (albion_ocr_payload, albion_ability_payload, albion_ui_payload, motion_payload, m3_ocr_payload):
            if isinstance(payload, dict):
                resolved_duration_ms = int(payload.get("duration_ms", resolved_duration_ms))
                resolved_frame_rate = float(payload.get("frame_rate", resolved_frame_rate))

        result = run_albion_combat_pipeline(
            source_fingerprint=ctx.source_fingerprint,
            duration_ms=resolved_duration_ms,
            frame_rate=resolved_frame_rate,
            albion_ocr_payload=albion_ocr_payload,
            m3_ocr_payload=m3_ocr_payload,
            albion_ability_payload=albion_ability_payload,
            albion_ui_payload=albion_ui_payload,
            motion_payload=motion_payload if isinstance(motion_payload, dict) else None,
            config_id=self._config_id,
        )

        events = [
            AlbionDetectorEvent(
                event_type=entry.event_type.value,
                timestamp_ms=entry.timestamp_ms,
                confidence=entry.confidence,
                reasoning=entry.label,
                metadata={
                    "entry_id": entry.entry_id,
                    "label": entry.label,
                    "search_text": entry.search_text,
                    "window_start_ms": entry.window_start_ms,
                    "window_end_ms": entry.window_end_ms,
                    **entry.metadata,
                },
            )
            for entry in result.entries
            if entry.event_type
            in {
                AlbionCombatEventType.FIGHT_START,
                AlbionCombatEventType.FIGHT_END,
                AlbionCombatEventType.KILL,
                AlbionCombatEventType.DEATH,
                AlbionCombatEventType.RETREAT,
            }
        ]

        confidence = 0.5
        if result.summary.entry_count > 0:
            confidence = min(0.96, 0.62 + result.summary.entry_count * 0.04)

        reasoning = (
            f"Albion combat timeline ({result.config_id}) found {result.summary.entry_count} entries "
            f"({result.summary.kill_count} kills, {result.summary.death_count} deaths, "
            f"{result.summary.fight_count} fights, {result.summary.retreat_count} retreats)"
        )
        if result.summary.reused_albion_ocr:
            reasoning += " (from Albion OCR cache)"

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
    def _resolve_detector_payload(ctx: AlbionDetectorContext, detector_id: str) -> dict | None:
        detector_results = ctx.extras.get("detector_results", {})
        if not isinstance(detector_results, dict):
            return None
        detector_result = detector_results.get(detector_id)
        if not isinstance(detector_result, dict):
            return None
        payload = detector_result.get("payload")
        if isinstance(payload, dict):
            return payload
        return None
