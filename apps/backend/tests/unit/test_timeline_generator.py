from __future__ import annotations

import pytest

from montage_backend.models.domain.montage_plan import (
    MontageEffect,
    MontageEffectType,
    MontagePlan,
    MontagePlanCard,
    MontagePlanClip,
    MontagePlanMetadata,
    MontagePlanMusic,
    MontagePlanStatus,
    MontageTransition,
    TransitionType,
)
from montage_backend.models.domain.plan_timeline import TIMELINE_GENERATOR_VERSION
from montage_backend.models.domain.timeline import default_timeline_document
from montage_backend.montage.timeline_generator import (
    TimelineOverwriteConfirmationRequiredError,
    apply_plan_to_timeline_document,
    build_cache_key,
    build_plan_timeline_application,
    requires_overwrite_confirmation,
)


def _plan_clip(
    *,
    clip_id: str = "plan-clip-1",
    order: int = 0,
    media_id: str = "media-1",
) -> MontagePlanClip:
    return MontagePlanClip(
        id=clip_id,
        media_id=media_id,
        order=order,
        source_start_ms=1000,
        source_end_ms=4000,
        timeline_start_ms=2500,
        timeline_end_ms=5500,
        clip_score=88.0,
        playback_speed=1.1,
        transition_in=MontageTransition(type=TransitionType.FADE, duration_ms=250, confidence=0.8),
        transition_out=MontageTransition(type=TransitionType.FLASH, duration_ms=120, confidence=0.85),
        effects=[
            MontageEffect(
                id="fx-1",
                type=MontageEffectType.ZOOM_PUNCH,
                confidence=0.8,
                reasoning="Peak moment",
            ),
        ],
        confidence=0.9,
        reasoning="Strong opener",
    )


def _plan() -> MontagePlan:
    return MontagePlan(
        id="plan-timeline-1",
        project_id="project-1",
        name="Arena Montage",
        status=MontagePlanStatus.READY,
        clips=[_plan_clip()],
        title_card=MontagePlanCard(type="title", text="Arena Montage", duration_ms=2500),
        ending_card=MontagePlanCard(type="ending", text="GG", duration_ms=2000),
        music=MontagePlanMusic(
            media_id="music-1",
            bpm=128.0,
            beat_markers_ms=[3000, 6000],
            confidence=0.9,
            reasoning="Selected track",
        ),
        metadata=MontagePlanMetadata(random_seed=42, pacing_profile="aggressive"),
        duration_ms=8000,
        version=2,
        created_at="2026-06-27T00:00:00Z",
        updated_at="2026-06-27T00:00:00Z",
    )


def test_apply_plan_to_timeline_document_populates_video_and_audio_tracks():
    plan = _plan()
    document = default_timeline_document(
        project_id="project-1",
        width=1920,
        height=1080,
        frame_rate=60.0,
    )

    updated = apply_plan_to_timeline_document(plan, document)
    video_track = next(track for track in updated.tracks if track["name"] == "Video 1")
    audio_track = next(track for track in updated.tracks if track["name"] == "Audio 1")
    music_track = next(track for track in updated.tracks if track["name"] == "Music")

    assert len(video_track["clips"]) == 1
    assert len(audio_track["clips"]) == 1
    assert len(music_track["clips"]) == 1
    clip = video_track["clips"][0]
    assert clip["media_item_id"] == "media-1"
    assert clip["start_ms"] == 2500
    assert clip["end_ms"] == 5500
    assert clip["source_in_ms"] == 1000
    assert clip["source_out_ms"] == 4000
    assert clip["speed"] == pytest.approx(1.1)
    assert clip["transition_in"]["type"] == "fade"
    assert clip["transition_out"]["type"] == "flash"
    assert clip["effects"][0]["type"] == "zoom"
    assert clip["ai"]["montage_plan_clip_id"] == "plan-clip-1"
    assert updated.metadata["montage_plan_id"] == plan.id
    assert updated.metadata["generator"] == TIMELINE_GENERATOR_VERSION
    assert len(updated.markers) == 2
    assert len(updated.beat_markers) == 2


def test_requires_overwrite_confirmation_when_timeline_has_foreign_clips():
    plan = _plan()
    document = default_timeline_document(
        project_id="project-1",
        width=1920,
        height=1080,
        frame_rate=60.0,
    )
    video_track = document.tracks[0]
    video_track["clips"] = [
        {
            "id": "manual-clip",
            "media_item_id": "other-media",
            "track_id": video_track["id"],
            "start_ms": 0,
            "end_ms": 1000,
            "source_in_ms": 0,
            "source_out_ms": 1000,
            "speed": 1.0,
            "opacity": 1.0,
        },
    ]
    assert requires_overwrite_confirmation(document, plan) is True


def test_apply_plan_requires_confirmation_for_foreign_timeline_edits():
    plan = _plan()
    document = default_timeline_document(
        project_id="project-1",
        width=1920,
        height=1080,
        frame_rate=60.0,
    )
    document.tracks[0]["clips"] = [{"id": "manual"}]

    with pytest.raises(TimelineOverwriteConfirmationRequiredError):
        apply_plan_to_timeline_document(plan, document, confirm_overwrite=False)


def test_partial_apply_replaces_only_selected_plan_clips():
    plan = _plan()
    plan.clips.append(
        _plan_clip(clip_id="plan-clip-2", order=1, media_id="media-2"),
    )
    plan.clips[1].timeline_start_ms = 5500
    plan.clips[1].timeline_end_ms = 8000
    document = default_timeline_document(
        project_id="project-1",
        width=1920,
        height=1080,
        frame_rate=60.0,
    )
    updated = apply_plan_to_timeline_document(plan, document)
    preserved = apply_plan_to_timeline_document(
        plan,
        updated,
        partial_clip_ids=["plan-clip-2"],
        confirm_overwrite=True,
    )
    video_track = next(track for track in preserved.tracks if track["name"] == "Video 1")
    clip_ids = {clip["ai"]["montage_plan_clip_id"] for clip in video_track["clips"]}
    assert clip_ids == {"plan-clip-1", "plan-clip-2"}


def test_build_plan_timeline_application_includes_cache_key():
    plan = _plan()
    document = default_timeline_document(
        project_id="project-1",
        width=1920,
        height=1080,
        frame_rate=60.0,
    )
    updated = apply_plan_to_timeline_document(plan, document)
    application = build_plan_timeline_application(
        project_id="project-1",
        plan=plan,
        timeline_id=updated.id,
        document=updated,
        overwritten=False,
    )
    assert application.engine_version == TIMELINE_GENERATOR_VERSION
    assert application.cache_key == build_cache_key(plan, updated.id)
