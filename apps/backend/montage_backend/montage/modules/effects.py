from __future__ import annotations

from typing import Any

from montage_backend.models.domain import utc_now_iso
from montage_backend.models.domain.montage_plan import MontagePlan
from montage_backend.models.domain.plan_effects import EFFECTS_ENGINE_VERSION, PlanEffectsAnalysis
from montage_backend.montage.base import MontageModuleId, MontageModuleOutput, MontagePlanContext, MontagePlanState
from montage_backend.montage.effects_engine import (
    ClipMotionSignals,
    build_cache_key,
    extract_motion_signals,
    recommend_plan_effects,
)
from montage_backend.montage.base import MontagePlannerModule


class EffectsEngineModule(MontagePlannerModule):
    module_id = MontageModuleId.EFFECTS
    version = EFFECTS_ENGINE_VERSION

    def cache_key(self, random_seed: int, **params: Any) -> str:
        plan_id = str(params.get("plan_id", "unknown"))
        pacing_profile = params.get("pacing_profile")
        clips = params.get("clips", [])
        media_fingerprints = params.get("media_fingerprints", {})
        return build_cache_key(plan_id, random_seed, pacing_profile, clips, media_fingerprints)

    async def plan(
        self,
        ctx: MontagePlanContext,
        state: MontagePlanState,
    ) -> MontageModuleOutput:
        ctx.check_cancelled()
        plan: MontagePlan | None = ctx.extras.get("plan")
        if plan is None:
            raise ValueError("EffectsEngineModule requires plan in context extras")

        clip_records = ctx.extras.get("clip_records", [])
        clip_signals: dict[str, ClipMotionSignals] = {}
        media_fingerprints: dict[str, str] = {}
        for record in clip_records:
            clip_signals[record.media_id] = extract_motion_signals(record)
            if record.source_fingerprint:
                media_fingerprints[record.media_id] = record.source_fingerprint

        await ctx.report(0.2, f"Selecting effects for {len(plan.clips)} clips")
        beat_markers_ms = ctx.extras.get("beat_markers_ms", [])
        analysis = recommend_plan_effects(
            project_id=ctx.project_id,
            plan=plan,
            clip_signals=clip_signals,
            media_fingerprints=media_fingerprints,
            beat_markers_ms=beat_markers_ms,
            updated_at=utc_now_iso(),
        )
        await ctx.report(1.0, f"Generated effects for {analysis.clip_count} clips")

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
                media_fingerprints=media_fingerprints,
            ),
            confidence=analysis.confidence,
            reasoning=analysis.reasoning,
            payload=payload,
        )
