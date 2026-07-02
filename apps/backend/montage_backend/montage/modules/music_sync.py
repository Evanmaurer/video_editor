from __future__ import annotations

from typing import Any

from montage_backend.models.domain.clip_analysis import ClipAnalysisRecord
from montage_backend.models.domain.music_sync import MUSIC_SYNC_VERSION, MusicSyncAnalysis
from montage_backend.models.domain import utc_now_iso
from montage_backend.montage.base import MontageModuleId, MontageModuleOutput, MontagePlanContext, MontagePlanState
from montage_backend.montage.music_sync import analyze_music_sync, build_cache_key
from montage_backend.montage.base import MontagePlannerModule


class MusicSyncModule(MontagePlannerModule):
    module_id = MontageModuleId.MUSIC_SYNC
    version = MUSIC_SYNC_VERSION

    def cache_key(self, random_seed: int, **params: Any) -> str:
        fingerprint = params.get("source_fingerprint", "unknown")
        return build_cache_key(str(fingerprint))

    async def plan(
        self,
        ctx: MontagePlanContext,
        state: MontagePlanState,
    ) -> MontageModuleOutput:
        ctx.check_cancelled()
        records: list[ClipAnalysisRecord] = ctx.extras.get("music_records", [])
        await ctx.report(0.1, f"Analyzing music sync for {len(records)} tracks")

        results: list[MusicSyncAnalysis] = []
        now = utc_now_iso()
        for index, record in enumerate(records):
            ctx.check_cancelled()
            sync = analyze_music_sync(
                project_id=ctx.project_id,
                media_id=record.media_id,
                record=record,
                updated_at=now,
            )
            results.append(sync)
            progress = 0.1 + ((index + 1) / max(len(records), 1)) * 0.9
            await ctx.report(progress, f"Synced music track {record.media_id}")

        payload = {
            "tracks": [item.model_dump(mode="json") for item in results],
            "track_count": len(results),
        }
        avg_confidence = (
            round(sum(item.confidence for item in results) / len(results), 2) if results else 0.0
        )
        state.module_cache[self.module_id.value] = payload
        return MontageModuleOutput(
            module_id=self.module_id.value,
            module_version=self.version,
            cache_key=self.cache_key(ctx.random_seed, source_fingerprint="batch"),
            confidence=avg_confidence,
            reasoning=f"Synchronized {len(results)} music tracks",
            payload=payload,
        )
