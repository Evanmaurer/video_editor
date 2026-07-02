from __future__ import annotations

import pytest

from montage_backend.models.domain.clip_highlight import ClipHighlights, HighlightSegment
from montage_backend.models.domain.clip_score import (
    CLIP_SCORER_VERSION,
    ClipScore,
    ClipScoreBreakdown,
    ClipScoreComponent,
)
from montage_backend.models.domain.montage_plan import (
    MontagePlan,
    MontagePlanMetadata,
    MontagePlanStatus,
)
from montage_backend.models.domain.plan_draft import DRAFT_GENERATOR_VERSION
from montage_backend.montage.base import MontagePlanContext, MontagePlanState
from montage_backend.montage.draft_generator import (
    apply_draft_to_plan,
    build_plan_clips_from_draft,
    collect_segment_candidates,
    generate_plan_draft,
    order_excitement_arc,
    select_segment_candidates,
)
from montage_backend.montage.modules.draft import DraftGeneratorModule
from montage_backend.montage.registry import build_default_montage_registry


def _component(key: str, score: float) -> ClipScoreComponent:
    return ClipScoreComponent(
        key=key,
        label=key,
        score=score,
        weight=0.1,
        weighted_score=score * 0.1,
        reasoning="test",
    )


def _breakdown() -> ClipScoreBreakdown:
    return ClipScoreBreakdown(
        motion=_component("motion", 80),
        camera_shake=_component("camera_shake", 70),
        audio_intensity=_component("audio_intensity", 75),
        ocr_activity=_component("ocr_activity", 60),
        scene_complexity=_component("scene_complexity", 65),
        visual_quality=_component("visual_quality", 70),
        exposure=_component("exposure", 68),
        scene_length=_component("scene_length", 72),
    )


def _score(media_id: str, montage_score: float, *, duration_ms: int = 10000) -> ClipScore:
    return ClipScore(
        media_id=media_id,
        project_id="project-1",
        file_name=f"{media_id}.mp4",
        montage_score=montage_score,
        confidence=0.9,
        reasoning="test score",
        breakdown=_breakdown(),
        scorer_version=CLIP_SCORER_VERSION,
        cache_key=f"score:{media_id}",
        duration_ms=duration_ms,
        updated_at="2026-06-27T00:00:00Z",
    )


def _highlights(media_id: str, segments: list[tuple[int, int, float]]) -> ClipHighlights:
    return ClipHighlights(
        media_id=media_id,
        project_id="project-1",
        file_name=f"{media_id}.mp4",
        highlight_count=len(segments),
        highlights=[
            HighlightSegment(
                id=f"hl-{media_id}-{index}",
                start_ms=start,
                end_ms=end,
                score=score,
                confidence=0.88,
                reasoning="test highlight",
            )
            for index, (start, end, score) in enumerate(segments)
        ],
        cache_key=f"hl:{media_id}",
        duration_ms=10000,
        updated_at="2026-06-27T00:00:00Z",
    )


def _plan(*, pacing_profile: str = "balanced", seed: int = 42, target: int | None = 60000) -> MontagePlan:
    return MontagePlan(
        id="plan-draft-1",
        project_id="project-1",
        name="Arena Montage",
        status=MontagePlanStatus.DRAFT,
        metadata=MontagePlanMetadata(
            random_seed=seed,
            pacing_profile=pacing_profile,
            target_duration_ms=target,
        ),
        created_at="2026-06-27T00:00:00Z",
        updated_at="2026-06-27T00:00:00Z",
    )


def test_collect_segment_candidates_prefers_highlights():
    scores = [_score("m1", 80), _score("m2", 70)]
    highlights = [
        _highlights("m1", [(1000, 4500, 92)]),
        _highlights("m2", [(500, 3000, 75)]),
    ]
    candidates = collect_segment_candidates(scores, highlights)
    assert len(candidates) == 2
    assert candidates[0].combined_score >= candidates[1].combined_score


def test_select_segment_candidates_respects_target_duration():
    scores = [_score(f"m{i}", 90 - i) for i in range(8)]
    highlights = [_highlights(score.media_id, [(1000, 4000, 85)]) for score in scores]
    selected = select_segment_candidates(
        collect_segment_candidates(scores, highlights),
        pacing_profile="cinematic",
        target_duration_ms=20000,
        random_seed=5,
    )
    assert 4 <= len(selected) <= 8


def test_order_excitement_arc_places_peak_near_center():
    from montage_backend.montage.draft_generator import SegmentCandidate

    candidates = [
        SegmentCandidate("m1", "a.mp4", 0, 3000, 60, 60, 60, 0.8, "low"),
        SegmentCandidate("m2", "b.mp4", 0, 3000, 70, 70, 70, 0.8, "mid"),
        SegmentCandidate("m3", "c.mp4", 0, 3000, 95, 95, 95, 0.9, "peak"),
        SegmentCandidate("m4", "d.mp4", 0, 3000, 80, 80, 80, 0.85, "high"),
        SegmentCandidate("m5", "e.mp4", 0, 3000, 65, 65, 65, 0.8, "mid"),
    ]
    ordered = order_excitement_arc(candidates, random_seed=10)
    peak_index = next(i for i, item in enumerate(ordered) if item.combined_score == 95)
    assert peak_index in {1, 2, 3}


def test_generate_plan_draft_builds_cards_and_candidates():
    scores = [_score("m1", 88), _score("m2", 76)]
    highlights = [
        _highlights("m1", [(1200, 5000, 90)]),
        _highlights("m2", [(800, 4200, 78)]),
    ]
    analysis = generate_plan_draft(
        project_id="project-1",
        plan=_plan(),
        scores=scores,
        highlights=highlights,
        available_music_ids=["music-1"],
    )
    assert analysis.engine_version == DRAFT_GENERATOR_VERSION
    assert analysis.clip_count >= 2
    assert analysis.title_card.type == "title"
    assert analysis.title_card.text == "Arena Montage"
    assert analysis.ending_card.type == "ending"
    assert analysis.music_media_id == "music-1"
    assert analysis.cache_key.startswith(DRAFT_GENERATOR_VERSION)


def test_apply_draft_to_plan_populates_plan_clips():
    scores = [_score("m1", 88)]
    highlights = [_highlights("m1", [(1000, 4500, 90)])]
    plan = _plan()
    analysis = generate_plan_draft(
        project_id="project-1",
        plan=plan,
        scores=scores,
        highlights=highlights,
    )
    apply_draft_to_plan(plan, analysis)
    assert len(plan.clips) == analysis.clip_count
    assert plan.title_card is not None
    assert plan.ending_card is not None
    assert plan.clips[0].source_start_ms == 1000
    assert plan.clips[0].source_end_ms == 4500


def test_build_plan_clips_offsets_timeline_after_title_card():
    scores = [_score("m1", 80)]
    highlights = [_highlights("m1", [(0, 3000, 85)])]
    analysis = generate_plan_draft(
        project_id="project-1",
        plan=_plan(),
        scores=scores,
        highlights=highlights,
    )
    clips = build_plan_clips_from_draft(analysis)
    assert clips[0].timeline_start_ms == analysis.title_card.duration_ms


@pytest.mark.asyncio
async def test_draft_generator_module_plan():
    plan = _plan()
    module = DraftGeneratorModule()
    ctx = MontagePlanContext(
        project_id="project-1",
        plan_id=plan.id,
        random_seed=42,
        extras={
            "plan": plan,
            "clip_scores": [_score("m1", 85)],
            "clip_highlights": [_highlights("m1", [(1000, 4000, 88)])],
            "available_music_ids": [],
        },
    )
    output = await module.plan(ctx, MontagePlanState())
    assert output.module_id == "draft"
    assert output.payload["clip_count"] == 1


def test_default_registry_registers_draft():
    registry = build_default_montage_registry()
    module = registry.get("draft")
    assert module.module_id.value == "draft"
