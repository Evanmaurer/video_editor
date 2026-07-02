from __future__ import annotations

from typing import Any

from montage_backend.models.domain import utc_now_iso
from montage_backend.models.domain.montage_plan import MontagePlan
from montage_backend.models.domain.plan_feedback import FEEDBACK_ENGINE_VERSION, PlanQualityAnalysis
from montage_backend.montage.base import MontageModuleId, MontageModuleOutput, MontagePlanContext, MontagePlanState
from montage_backend.montage.feedback_engine import build_cache_key, estimate_plan_quality
from montage_backend.montage.base import MontagePlannerModule


class FeedbackLoopModule(MontagePlannerModule):
    module_id = MontageModuleId.FEEDBACK
    version = FEEDBACK_ENGINE_VERSION

    def cache_key(self, random_seed: int, **params: Any) -> str:
        plan: MontagePlan | None = params.get("plan")
        if plan is None:
            return f"{FEEDBACK_ENGINE_VERSION}:unknown"
        return build_cache_key(plan)

    async def plan(
        self,
        ctx: MontagePlanContext,
        state: MontagePlanState,
    ) -> MontageModuleOutput:
        ctx.check_cancelled()
        plan: MontagePlan | None = ctx.extras.get("plan")
        if plan is None:
            raise ValueError("FeedbackLoopModule requires plan in context extras")

        transitions = ctx.extras.get("transitions")
        pacing = ctx.extras.get("pacing")
        effects = ctx.extras.get("effects")

        await ctx.report(0.3, "Estimating montage quality dimensions")
        analysis = estimate_plan_quality(
            project_id=ctx.project_id,
            plan=plan,
            transitions=transitions,
            pacing=pacing,
            effects=effects,
            updated_at=utc_now_iso(),
        )
        await ctx.report(1.0, f"Overall quality score {analysis.overall_score:.1f}")

        payload = analysis.model_dump(mode="json")
        state.module_cache[self.module_id.value] = payload
        return MontageModuleOutput(
            module_id=self.module_id.value,
            module_version=self.version,
            cache_key=self.cache_key(ctx.random_seed, plan=plan),
            confidence=analysis.overall_confidence,
            reasoning=analysis.reasoning,
            payload=payload,
        )
