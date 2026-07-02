from __future__ import annotations

from montage_backend.analysis.albion.base import (
    AlbionDetector,
    AlbionDetectorContext,
    AlbionDetectorEvent,
    AlbionDetectorId,
    AlbionDetectorOutput,
)
from montage_backend.analysis.albion.bomb.albion_bomb_analysis import ALBION_BOMB_DETECTOR_VERSION
from montage_backend.analysis.albion.bomb.config import config_cache_token, get_bomb_config
from montage_backend.analysis.albion.bomb.pipeline import build_detector_cache_key, run_albion_bomb_pipeline


class AlbionBombDetector(AlbionDetector):
    """Detect coordinated bomb moments from OCR kill spikes, motion, audio, and abilities."""

    detector_id = AlbionDetectorId.BOMB
    version = ALBION_BOMB_DETECTOR_VERSION

    def __init__(self, *, config_id: str | None = None) -> None:
        self._config_id = config_id

    def cache_key(self, source_fingerprint: str, *, frame_rate: float | None = None) -> str:
        config = get_bomb_config(self._config_id)
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
        config = get_bomb_config(self._config_id)
        await ctx.report(
            0.0,
            f"Albion bomb config ready ({config.id}, min_kills={config.bomb_min_kills})",
        )

    async def analyze(
        self,
        ctx: AlbionDetectorContext,
        *,
        video_path: str,
        duration_ms: int | None,
        frame_rate: float | None,
    ) -> AlbionDetectorOutput:
        _ = video_path
        await ctx.report(0.1, "Resolving bomb fusion sources")
        ctx.check_cancelled()

        combat_payload = self._resolve_detector_payload(ctx, "combat")
        albion_ocr_payload = self._resolve_detector_payload(ctx, "ocr")
        albion_ability_payload = self._resolve_detector_payload(ctx, "ability")
        m3_ocr_payload = ctx.extras.get("ocr_analysis")
        motion_payload = ctx.extras.get("motion_analysis")
        audio_payload = ctx.extras.get("audio_analysis")

        resolved_duration_ms = duration_ms or 0
        resolved_frame_rate = frame_rate or 0.0
        for payload in (
            combat_payload,
            albion_ocr_payload,
            albion_ability_payload,
            motion_payload,
            audio_payload,
            m3_ocr_payload,
        ):
            if isinstance(payload, dict):
                resolved_duration_ms = int(payload.get("duration_ms", resolved_duration_ms))
                resolved_frame_rate = float(payload.get("frame_rate", resolved_frame_rate))

        result = run_albion_bomb_pipeline(
            source_fingerprint=ctx.source_fingerprint,
            duration_ms=resolved_duration_ms,
            frame_rate=resolved_frame_rate,
            combat_payload=combat_payload,
            albion_ocr_payload=albion_ocr_payload,
            m3_ocr_payload=m3_ocr_payload,
            albion_ability_payload=albion_ability_payload,
            motion_payload=motion_payload if isinstance(motion_payload, dict) else None,
            audio_payload=audio_payload if isinstance(audio_payload, dict) else None,
            config_id=self._config_id,
        )

        events = [
            AlbionDetectorEvent(
                event_type="bomb",
                timestamp_ms=event.timestamp_ms,
                confidence=event.confidence,
                reasoning=event.reasoning,
                metadata={
                    "event_id": event.event_id,
                    "bomb_score": event.bomb_score,
                    "kill_count": event.kill_count,
                    "fusion": event.fusion.model_dump(mode="json"),
                    "search_text": event.search_text,
                    "window_start_ms": event.window_start_ms,
                    "window_end_ms": event.window_end_ms,
                    **event.metadata,
                },
            )
            for event in result.events
        ]

        confidence = 0.5
        if result.summary.bomb_count > 0:
            confidence = min(0.98, 0.65 + result.summary.top_bomb_score * 0.03)

        reasoning = (
            f"Albion bombs ({result.config_id}) found {result.summary.bomb_count} coordinated moments "
            f"(top score {result.summary.top_bomb_score:.1f}/10)"
        )
        if result.summary.reused_albion_combat:
            reasoning += " (from combat timeline)"
        elif result.summary.reused_albion_ocr:
            reasoning += " (from Albion OCR)"

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
