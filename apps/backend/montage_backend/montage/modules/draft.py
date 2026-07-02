from __future__ import annotations

from typing import Any

from montage_backend.models.domain import utc_now_iso
from montage_backend.models.domain.clip_highlight import ClipHighlights
from montage_backend.models.domain.clip_score import ClipScore
from montage_backend.models.domain.montage_plan import MontagePlan
from montage_backend.models.domain.plan_draft import DRAFT_GENERATOR_VERSION, PlanDraftAnalysis
from montage_backend.montage.base import MontageModuleId, MontageModuleOutput, MontagePlanContext, MontagePlanState
from montage_backend.montage.draft_generator import build_cache_key, build_project_signature, generate_plan_draft
from montage_backend.montage.base import MontagePlannerModule


class DraftGeneratorModule(MontagePlannerModule):
    module_id = MontageModuleId.DRAFT
    version = DRAFT_GENERATOR_VERSION

    def cache_key(self, random_seed: int, **params: Any) -> str:
        plan_id = str(params.get("plan_id", "unknown"))
        pacing_profile = params.get("pacing_profile")
        target_duration_ms = params.get("target_duration_ms")
        project_signature = str(params.get("project_signature", "none"))
        music_media_id = params.get("music_media_id")
        return build_cache_key(
            plan_id,
            random_seed,
            pacing_profile,
            target_duration_ms,
            project_signature,
            music_media_id,
        )

    async def plan(
        self,
        ctx: MontagePlanContext,
        state: MontagePlanState,
    ) -> MontageModuleOutput:
        ctx.check_cancelled()
        plan: MontagePlan | None = ctx.extras.get("plan")
        if plan is None:
            raise ValueError("DraftGeneratorModule requires plan in context extras")

        scores: list[ClipScore] = ctx.extras.get("clip_scores", [])
        highlights: list[ClipHighlights] = ctx.extras.get("clip_highlights", [])
        available_music_ids: list[str] = ctx.extras.get("available_music_ids", [])

        await ctx.report(0.2, f"Selecting clips from {len(scores)} scored sources")
        analysis = generate_plan_draft(
            project_id=ctx.project_id,
            plan=plan,
            scores=scores,
            highlights=highlights,
            available_music_ids=available_music_ids,
            updated_at=utc_now_iso(),
        )
        await ctx.report(1.0, f"Drafted {analysis.clip_count} clips")

        payload = analysis.model_dump(mode="json")
        state.clips = []
        state.module_cache[self.module_id.value] = payload
        project_signature = build_project_signature(scores, highlights)
        return MontageModuleOutput(
            module_id=self.module_id.value,
            module_version=self.version,
            cache_key=self.cache_key(
                ctx.random_seed,
                plan_id=plan.id,
                pacing_profile=plan.metadata.pacing_profile,
                target_duration_ms=plan.metadata.target_duration_ms,
                project_signature=project_signature,
                music_media_id=analysis.music_media_id,
            ),
            confidence=analysis.confidence,
            reasoning=analysis.reasoning,
            payload=payload,
        )
