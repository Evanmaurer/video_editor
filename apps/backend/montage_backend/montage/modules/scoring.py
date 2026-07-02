from __future__ import annotations

from typing import Any

from montage_backend.models.domain.clip_analysis import ClipAnalysisRecord
from montage_backend.models.domain.clip_score import CLIP_SCORER_VERSION, ClipScore
from montage_backend.models.domain import utc_now_iso
from montage_backend.montage.base import MontageModuleId, MontageModuleOutput, MontagePlanContext, MontagePlanState
from montage_backend.montage.clip_scoring import build_cache_key, score_clip_analysis
from montage_backend.montage.base import MontagePlannerModule


class ClipScoringModule(MontagePlannerModule):
    module_id = MontageModuleId.SCORING
    version = CLIP_SCORER_VERSION

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
        await ctx.report(0.1, f"Scoring {len(records)} clips")

        scores: list[ClipScore] = []
        now = utc_now_iso()
        for index, record in enumerate(records):
            ctx.check_cancelled()
            score = score_clip_analysis(
                project_id=ctx.project_id,
                media_id=record.media_id,
                record=record,
                updated_at=now,
            )
            scores.append(score)
            progress = 0.1 + ((index + 1) / max(len(records), 1)) * 0.9
            await ctx.report(progress, f"Scored {record.media_id}")

        scores.sort(key=lambda item: item.montage_score, reverse=True)
        payload = {
            "scores": [score.model_dump(mode="json") for score in scores],
            "clip_count": len(scores),
        }
        avg_confidence = (
            round(sum(score.confidence for score in scores) / len(scores), 2) if scores else 0.0
        )
        state.module_cache[self.module_id.value] = payload
        return MontageModuleOutput(
            module_id=self.module_id.value,
            module_version=self.version,
            cache_key=self.cache_key(ctx.random_seed, source_fingerprint="batch"),
            confidence=avg_confidence,
            reasoning=f"Scored {len(scores)} clips for montage selection",
            payload=payload,
        )
