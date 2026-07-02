from __future__ import annotations

from typing import Any

from montage_backend.models.domain.clip_analysis import ClipAnalysisRecord
from montage_backend.models.domain.clip_highlight import HIGHLIGHT_DETECTOR_VERSION, ClipHighlights
from montage_backend.models.domain import utc_now_iso
from montage_backend.montage.base import MontageModuleId, MontageModuleOutput, MontagePlanContext, MontagePlanState
from montage_backend.montage.highlight_detection import build_cache_key, detect_clip_highlights
from montage_backend.montage.base import MontagePlannerModule


class HighlightDetectionModule(MontagePlannerModule):
    module_id = MontageModuleId.HIGHLIGHTS
    version = HIGHLIGHT_DETECTOR_VERSION

    def cache_key(self, random_seed: int, **params: Any) -> str:
        fingerprint = params.get("source_fingerprint", "unknown")
        return build_cache_key(str(fingerprint))

    async def plan(
        self,
        ctx: MontagePlanContext,
        state: MontagePlanState,
    ) -> MontageModuleOutput:
        ctx.check_cancelled()
        records: list[ClipAnalysisRecord] = ctx.extras.get("clip_records", [])
        await ctx.report(0.1, f"Detecting highlights in {len(records)} clips")

        results: list[ClipHighlights] = []
        now = utc_now_iso()
        total_highlights = 0
        for index, record in enumerate(records):
            ctx.check_cancelled()
            highlights = detect_clip_highlights(
                project_id=ctx.project_id,
                media_id=record.media_id,
                record=record,
                updated_at=now,
            )
            results.append(highlights)
            total_highlights += highlights.highlight_count
            progress = 0.1 + ((index + 1) / max(len(records), 1)) * 0.9
            await ctx.report(progress, f"Found {highlights.highlight_count} highlights in {record.media_id}")

        payload = {
            "clips": [item.model_dump(mode="json") for item in results],
            "clip_count": len(results),
            "highlight_count": total_highlights,
        }
        avg_confidence = 0.0
        confidences = [
            segment.confidence
            for item in results
            for segment in item.highlights
        ]
        if confidences:
            avg_confidence = round(sum(confidences) / len(confidences), 2)

        state.module_cache[self.module_id.value] = payload
        return MontageModuleOutput(
            module_id=self.module_id.value,
            module_version=self.version,
            cache_key=self.cache_key(ctx.random_seed, source_fingerprint="batch"),
            confidence=avg_confidence,
            reasoning=f"Detected {total_highlights} highlights across {len(results)} clips",
            payload=payload,
        )
