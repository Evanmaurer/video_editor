from __future__ import annotations

from montage_backend.analysis.albion.base import (
    AlbionDetector,
    AlbionDetectorContext,
    AlbionDetectorEvent,
    AlbionDetectorId,
    AlbionDetectorOutput,
)
from montage_backend.analysis.albion.highlight.albion_highlight_analysis import ALBION_HIGHLIGHT_DETECTOR_VERSION
from montage_backend.analysis.albion.highlight.config import config_cache_token, get_highlight_config
from montage_backend.analysis.albion.highlight.pipeline import build_detector_cache_key, run_albion_highlight_pipeline


class AlbionHighlightDetector(AlbionDetector):
    """Rank clip highlight quality from Albion combat, bomb, engagement, and signal fusion."""

    detector_id = AlbionDetectorId.HIGHLIGHT
    version = ALBION_HIGHLIGHT_DETECTOR_VERSION

    def __init__(self, *, config_id: str | None = None) -> None:
        self._config_id = config_id

    def cache_key(self, source_fingerprint: str, *, frame_rate: float | None = None) -> str:
        config = get_highlight_config(self._config_id)
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
        config = get_highlight_config(self._config_id)
        await ctx.report(0.0, f"Albion highlight config ready ({config.id})")

    async def analyze(
        self,
        ctx: AlbionDetectorContext,
        *,
        video_path: str,
        duration_ms: int | None,
        frame_rate: float | None,
    ) -> AlbionDetectorOutput:
        _ = video_path
        await ctx.report(0.1, "Resolving Albion highlight ranking sources")
        ctx.check_cancelled()

        combat_payload = self._resolve_detector_payload(ctx, "combat")
        bomb_payload = self._resolve_detector_payload(ctx, "bomb")
        engagement_payload = self._resolve_detector_payload(ctx, "engagement")
        ability_payload = self._resolve_detector_payload(ctx, "ability")
        ui_payload = self._resolve_detector_payload(ctx, "ui")
        albion_ocr_payload = self._resolve_detector_payload(ctx, "ocr")
        m3_ocr_payload = ctx.extras.get("ocr_analysis")
        motion_payload = ctx.extras.get("motion_analysis")
        audio_payload = ctx.extras.get("audio_analysis")

        resolved_duration_ms = duration_ms or 0
        resolved_frame_rate = frame_rate or 0.0
        for payload in (
            combat_payload,
            bomb_payload,
            engagement_payload,
            ability_payload,
            ui_payload,
            albion_ocr_payload,
            motion_payload,
            audio_payload,
            m3_ocr_payload,
        ):
            if isinstance(payload, dict):
                resolved_duration_ms = int(payload.get("duration_ms", resolved_duration_ms))
                resolved_frame_rate = float(payload.get("frame_rate", resolved_frame_rate))

        result = run_albion_highlight_pipeline(
            source_fingerprint=ctx.source_fingerprint,
            duration_ms=resolved_duration_ms,
            frame_rate=resolved_frame_rate,
            combat_payload=combat_payload,
            bomb_payload=bomb_payload,
            engagement_payload=engagement_payload,
            ability_payload=ability_payload,
            albion_ocr_payload=albion_ocr_payload,
            m3_ocr_payload=m3_ocr_payload if isinstance(m3_ocr_payload, dict) else None,
            ui_payload=ui_payload,
            motion_payload=motion_payload if isinstance(motion_payload, dict) else None,
            audio_payload=audio_payload if isinstance(audio_payload, dict) else None,
            config_id=self._config_id,
        )

        events = [
            AlbionDetectorEvent(
                event_type="highlight",
                timestamp_ms=moment.timestamp_ms,
                confidence=moment.confidence,
                reasoning=moment.reasoning,
                metadata={
                    "moment_id": moment.moment_id,
                    "moment_score": moment.moment_score,
                    "moment_type": moment.moment_type,
                    "search_text": moment.search_text,
                    "window_start_ms": moment.window_start_ms,
                    "window_end_ms": moment.window_end_ms,
                    **moment.metadata,
                },
            )
            for moment in result.moments
        ]

        reasoning = (
            f"Albion highlights ({result.config_id}) scored clip {result.highlight_score:.1f}/100 "
            f"with {result.summary.moment_count} ranked moment(s)"
        )
        if result.summary.reused_albion_bomb:
            reasoning += " (bomb quality included)"
        if result.summary.reused_albion_engagement:
            reasoning += " (engagement included)"

        await ctx.report(1.0, reasoning)
        return AlbionDetectorOutput(
            detector_id=self.detector_id.value,
            detector_version=self.version,
            cache_key=result.cache_key,
            confidence=result.confidence,
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
