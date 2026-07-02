from __future__ import annotations

from montage_backend.analysis.albion.base import (
    AlbionDetector,
    AlbionDetectorContext,
    AlbionDetectorEvent,
    AlbionDetectorId,
    AlbionDetectorOutput,
)
from montage_backend.analysis.albion.engagement.albion_engagement_analysis import ALBION_ENGAGEMENT_DETECTOR_VERSION
from montage_backend.analysis.albion.engagement.config import config_cache_token, get_engagement_config
from montage_backend.analysis.albion.engagement.pipeline import build_detector_cache_key, run_albion_engagement_pipeline


class AlbionEngagementDetector(AlbionDetector):
    """Classify clip engagement types from combat, bomb, UI, OCR, and motion signals."""

    detector_id = AlbionDetectorId.ENGAGEMENT
    version = ALBION_ENGAGEMENT_DETECTOR_VERSION

    def __init__(self, *, config_id: str | None = None) -> None:
        self._config_id = config_id

    def cache_key(self, source_fingerprint: str, *, frame_rate: float | None = None) -> str:
        config = get_engagement_config(self._config_id)
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
        config = get_engagement_config(self._config_id)
        await ctx.report(
            0.0,
            f"Albion engagement config ready ({config.id}, min_duration={config.engagement_min_duration_ms}ms)",
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
        await ctx.report(0.1, "Resolving engagement classification sources")
        ctx.check_cancelled()

        combat_payload = self._resolve_detector_payload(ctx, "combat")
        bomb_payload = self._resolve_detector_payload(ctx, "bomb")
        ui_payload = self._resolve_detector_payload(ctx, "ui")
        albion_ocr_payload = self._resolve_detector_payload(ctx, "ocr")
        m3_ocr_payload = ctx.extras.get("ocr_analysis")
        motion_payload = ctx.extras.get("motion_analysis")

        resolved_duration_ms = duration_ms or 0
        resolved_frame_rate = frame_rate or 0.0
        for payload in (
            combat_payload,
            bomb_payload,
            ui_payload,
            albion_ocr_payload,
            motion_payload,
            m3_ocr_payload,
        ):
            if isinstance(payload, dict):
                resolved_duration_ms = int(payload.get("duration_ms", resolved_duration_ms))
                resolved_frame_rate = float(payload.get("frame_rate", resolved_frame_rate))

        result = run_albion_engagement_pipeline(
            source_fingerprint=ctx.source_fingerprint,
            duration_ms=resolved_duration_ms,
            frame_rate=resolved_frame_rate,
            combat_payload=combat_payload,
            bomb_payload=bomb_payload,
            ui_payload=ui_payload,
            albion_ocr_payload=albion_ocr_payload,
            m3_ocr_payload=m3_ocr_payload if isinstance(m3_ocr_payload, dict) else None,
            motion_payload=motion_payload if isinstance(motion_payload, dict) else None,
            config_id=self._config_id,
        )

        events = [
            AlbionDetectorEvent(
                event_type="engagement",
                timestamp_ms=0,
                confidence=tag.confidence,
                reasoning=tag.reasoning,
                metadata={
                    "engagement_type": tag.engagement_type.value,
                    "score": tag.score,
                    "search_text": tag.search_text,
                    **tag.metadata,
                },
            )
            for tag in result.tags
        ]

        confidence = 0.45
        if result.tags:
            confidence = min(0.98, 0.55 + result.tags[0].confidence * 0.35)

        tag_labels = ", ".join(tag.engagement_type.value for tag in result.tags) or "none"
        reasoning = (
            f"Albion engagement ({result.config_id}) tagged clip as: {tag_labels} "
            f"(primary={result.summary.primary_engagement.value if result.summary.primary_engagement else 'none'})"
        )
        if result.summary.reused_albion_combat:
            reasoning += " (from combat timeline)"
        if result.summary.reused_albion_bomb:
            reasoning += " (from bomb detector)"

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
