from __future__ import annotations

from typing import Any

from montage_backend.models.domain import utc_now_iso
from montage_backend.models.domain.montage_plan import MontagePlan
from montage_backend.models.domain.plan_transitions import TRANSITION_ENGINE_VERSION, PlanTransitionAnalysis
from montage_backend.montage.base import MontageModuleId, MontageModuleOutput, MontagePlanContext, MontagePlanState
from montage_backend.montage.transition_engine import build_cache_key, recommend_plan_transitions
from montage_backend.montage.base import MontagePlannerModule


class TransitionEngineModule(MontagePlannerModule):
    module_id = MontageModuleId.TRANSITIONS
    version = TRANSITION_ENGINE_VERSION

    def cache_key(self, random_seed: int, **params: Any) -> str:
        plan_id = str(params.get("plan_id", "unknown"))
        pacing_profile = params.get("pacing_profile")
        clips = params.get("clips", [])
        return build_cache_key(plan_id, random_seed, pacing_profile, clips)

    async def plan(
        self,
        ctx: MontagePlanContext,
        state: MontagePlanState,
    ) -> MontageModuleOutput:
        ctx.check_cancelled()
        plan: MontagePlan | None = ctx.extras.get("plan")
        if plan is None:
            raise ValueError("TransitionEngineModule requires plan in context extras")

        await ctx.report(0.2, f"Selecting transitions for {len(plan.clips)} clips")
        beat_markers_ms = ctx.extras.get("beat_markers_ms", [])
        analysis = recommend_plan_transitions(
            project_id=ctx.project_id,
            plan=plan,
            beat_markers_ms=beat_markers_ms,
            updated_at=utc_now_iso(),
        )
        await ctx.report(1.0, f"Generated {analysis.junction_count} transition recommendations")

        payload = analysis.model_dump(mode="json")
        state.module_cache[self.module_id.value] = payload
        return MontageModuleOutput(
            module_id=self.module_id.value,
            module_version=self.version,
            cache_key=self.cache_key(
                ctx.random_seed,
                plan_id=plan.id,
                pacing_profile=plan.metadata.pacing_profile,
                clips=plan.clips,
            ),
            confidence=analysis.confidence,
            reasoning=analysis.reasoning,
            payload=payload,
        )
