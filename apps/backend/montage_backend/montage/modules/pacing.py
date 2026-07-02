from __future__ import annotations

from typing import Any

from montage_backend.models.domain import utc_now_iso
from montage_backend.models.domain.montage_plan import MontagePlan
from montage_backend.models.domain.plan_pacing import PACING_ENGINE_VERSION, PlanPacingAnalysis
from montage_backend.montage.base import MontageModuleId, MontageModuleOutput, MontagePlanContext, MontagePlanState
from montage_backend.montage.pacing_engine import build_cache_key, recommend_plan_pacing
from montage_backend.montage.base import MontagePlannerModule


class PacingEngineModule(MontagePlannerModule):
    module_id = MontageModuleId.PACING
    version = PACING_ENGINE_VERSION

    def cache_key(self, random_seed: int, **params: Any) -> str:
        plan_id = str(params.get("plan_id", "unknown"))
        pacing_profile = params.get("pacing_profile")
        target_duration_ms = params.get("target_duration_ms")
        clips = params.get("clips", [])
        return build_cache_key(plan_id, random_seed, pacing_profile, target_duration_ms, clips)

    async def plan(
        self,
        ctx: MontagePlanContext,
        state: MontagePlanState,
    ) -> MontageModuleOutput:
        ctx.check_cancelled()
        plan: MontagePlan | None = ctx.extras.get("plan")
        if plan is None:
            raise ValueError("PacingEngineModule requires plan in context extras")

        await ctx.report(0.2, f"Pacing {len(plan.clips)} clips")
        beat_markers_ms = ctx.extras.get("beat_markers_ms", [])
        analysis = recommend_plan_pacing(
            project_id=ctx.project_id,
            plan=plan,
            beat_markers_ms=beat_markers_ms,
            updated_at=utc_now_iso(),
        )
        await ctx.report(1.0, f"Paced montage to {analysis.total_duration_ms}ms")

        payload = analysis.model_dump(mode="json")
        state.module_cache[self.module_id.value] = payload
        return MontageModuleOutput(
            module_id=self.module_id.value,
            module_version=self.version,
            cache_key=self.cache_key(
                ctx.random_seed,
                plan_id=plan.id,
                pacing_profile=plan.metadata.pacing_profile,
                target_duration_ms=plan.metadata.target_duration_ms,
                clips=plan.clips,
            ),
            confidence=analysis.confidence,
            reasoning=analysis.reasoning,
            payload=payload,
        )
