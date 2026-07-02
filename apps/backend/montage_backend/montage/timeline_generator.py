from __future__ import annotations

import hashlib

from montage_backend.models.domain import MontageError, new_uuid, utc_now_iso
from montage_backend.models.domain.montage_plan import (
    MontageEffect,
    MontageEffectType,
    MontagePlan,
    MontagePlanClip,
    MontageTransition,
    TransitionType,
)
from montage_backend.models.domain.plan_timeline import (
    TIMELINE_GENERATOR_VERSION,
    PlanTimelineApplication,
)
from montage_backend.models.domain.timeline import TimelineDocument

TRANSITION_TYPE_MAP: dict[TransitionType, str] = {
    TransitionType.HARD_CUT: "cut",
    TransitionType.FADE: "fade",
    TransitionType.CROSSFADE: "fade",
    TransitionType.FLASH: "flash",
    TransitionType.MOTION_BLUR: "fade",
    TransitionType.SPEED_RAMP: "cut",
    TransitionType.ZOOM: "zoom",
    TransitionType.WHIP: "flash",
}

EFFECT_TYPE_MAP: dict[MontageEffectType, str] = {
    MontageEffectType.SPEED_RAMP: "speed_ramp",
    MontageEffectType.CAMERA_SHAKE: "shake",
    MontageEffectType.ZOOM_PUNCH: "zoom",
    MontageEffectType.COLOR_GRADE: "color_grade",
    MontageEffectType.MOTION_BLUR: "motion_blur",
    MontageEffectType.GLOW: "flash",
    MontageEffectType.SHARPEN: "sharpen",
    MontageEffectType.VIGNETTE: "vignette",
}


class TimelineOverwriteConfirmationRequiredError(MontageError):
    code = "TIMELINE_OVERWRITE_CONFIRMATION_REQUIRED"


def build_plan_signature(plan: MontagePlan) -> str:
    ordered = sorted(plan.clips, key=lambda clip: clip.order)
    payload = "|".join(
        f"{clip.id}:{clip.order}:{clip.media_id}:{clip.source_start_ms}:{clip.source_end_ms}:"
        f"{clip.timeline_start_ms}:{clip.timeline_end_ms}:{clip.playback_speed:.2f}"
        for clip in ordered
    )
    return hashlib.sha256(payload.encode()).hexdigest()[:16]


def build_cache_key(plan: MontagePlan, timeline_id: str, *, partial_clip_ids: list[str] | None = None) -> str:
    partial = ",".join(sorted(partial_clip_ids)) if partial_clip_ids else "full"
    signature = build_plan_signature(plan)
    return (
        f"{TIMELINE_GENERATOR_VERSION}:{plan.id}:{plan.version}:{timeline_id}:{signature}:{partial}"
    )


def _find_track(tracks: list[dict], *, track_type: str, name: str | None = None) -> dict:
    for track in tracks:
        if track.get("type") != track_type:
            continue
        if name is not None and track.get("name") != name:
            continue
        return track
    raise ValueError(f"Track not found: type={track_type} name={name}")


def timeline_has_content(document: TimelineDocument) -> bool:
    return any(track.get("clips") for track in document.tracks)


def requires_overwrite_confirmation(
    document: TimelineDocument,
    plan: MontagePlan,
    *,
    partial_clip_ids: list[str] | None = None,
) -> bool:
    if not timeline_has_content(document):
        return False

    metadata = document.metadata or {}
    same_application = (
        metadata.get("montage_plan_id") == plan.id
        and metadata.get("montage_plan_version") == plan.version
        and not partial_clip_ids
    )
    return not same_application


def _map_transition(transition: MontageTransition | None) -> dict | None:
    if transition is None:
        return None
    return {
        "type": TRANSITION_TYPE_MAP.get(transition.type, "cut"),
        "duration_ms": transition.duration_ms,
        "parameters": {
            **transition.parameters,
            "montage_transition_type": transition.type.value,
        },
        "confidence": transition.confidence,
        "reasoning": transition.reasoning,
    }


def _map_effect(effect: MontageEffect) -> dict:
    return {
        "id": effect.id,
        "type": EFFECT_TYPE_MAP.get(effect.type, effect.type.value),
        "enabled": effect.enabled,
        "parameters": effect.parameters,
        "confidence": effect.confidence,
        "reasoning": effect.reasoning,
    }


def _ai_metadata(clip: MontagePlanClip, plan: MontagePlan) -> dict:
    return {
        "generated": True,
        "confidence": clip.confidence,
        "reasoning": clip.reasoning,
        "expected_improvement": None,
        "agent_id": "timeline-generator",
        "agent_version": TIMELINE_GENERATOR_VERSION,
        "montage_plan_id": plan.id,
        "montage_plan_clip_id": clip.id,
        "clip_score": clip.clip_score,
    }


def _timeline_clip_volume(clip: MontagePlanClip) -> float:
    volume = 1.0
    for action in clip.audio_actions:
        if action.type.value == "mute":
            return 0.0
        if action.type.value == "duck" and action.level_db is not None:
            volume = min(volume, max(0.0, 1.0 + (action.level_db / 20.0)))
        if action.type.value == "boost" and action.level_db is not None:
            volume = min(1.5, volume + (action.level_db / 20.0))
    return round(volume, 3)


def _build_timeline_clip(
    *,
    plan_clip: MontagePlanClip,
    plan: MontagePlan,
    track_id: str,
    include_transitions: bool,
    include_effects: bool,
) -> dict:
    return {
        "id": new_uuid(),
        "media_item_id": plan_clip.media_id,
        "track_id": track_id,
        "start_ms": plan_clip.timeline_start_ms,
        "end_ms": plan_clip.timeline_end_ms,
        "source_in_ms": plan_clip.source_start_ms,
        "source_out_ms": plan_clip.source_end_ms,
        "speed": plan_clip.playback_speed,
        "opacity": 1.0,
        "scale": 1.0,
        "position": {"x": 0.0, "y": 0.0},
        "rotation": 0.0,
        "volume": _timeline_clip_volume(plan_clip),
        "effects": [_map_effect(effect) for effect in plan_clip.effects] if include_effects else [],
        "keyframes": [],
        "transition_in": _map_transition(plan_clip.transition_in) if include_transitions else None,
        "transition_out": _map_transition(plan_clip.transition_out) if include_transitions else None,
        "ai": _ai_metadata(plan_clip, plan),
        "name": f"Clip {plan_clip.order + 1}",
    }


def _build_markers(plan: MontagePlan) -> list[dict]:
    markers: list[dict] = []
    if plan.title_card is not None:
        markers.append(
            {
                "id": new_uuid(),
                "time_ms": 0,
                "label": plan.title_card.text or "Title",
                "color": "#4fc3f7",
                "type": "event",
                "confidence": plan.title_card.confidence,
                "reasoning": plan.title_card.reasoning,
            },
        )
    if plan.ending_card is not None and plan.duration_ms > 0:
        markers.append(
            {
                "id": new_uuid(),
                "time_ms": max(plan.duration_ms - plan.ending_card.duration_ms, 0),
                "label": plan.ending_card.text or "Ending",
                "color": "#9575cd",
                "type": "event",
                "confidence": plan.ending_card.confidence,
                "reasoning": plan.ending_card.reasoning,
            },
        )
    return markers


def _build_beat_markers(plan: MontagePlan) -> list[dict]:
    if plan.music is None:
        return []
    return [
        {
            "id": new_uuid(),
            "time_ms": beat_ms,
            "label": "Beat",
            "color": "#ffca28",
            "type": "beat",
            "strength": 0.8,
        }
        for beat_ms in plan.music.beat_markers_ms
    ]


def _filter_existing_clips(
    clips: list[dict],
    *,
    plan: MontagePlan,
    partial_clip_ids: list[str] | None,
) -> list[dict]:
    if not partial_clip_ids:
        return []
    partial_set = set(partial_clip_ids)
    return [
        clip
        for clip in clips
        if (clip.get("ai") or {}).get("montage_plan_clip_id") not in partial_set
        or (clip.get("ai") or {}).get("montage_plan_id") != plan.id
    ]


def apply_plan_to_timeline_document(
    plan: MontagePlan,
    document: TimelineDocument,
    *,
    partial_clip_ids: list[str] | None = None,
    confirm_overwrite: bool = False,
) -> TimelineDocument:
    if not plan.clips:
        raise ValueError("Montage plan has no clips to apply")

    if requires_overwrite_confirmation(document, plan, partial_clip_ids=partial_clip_ids):
        if not confirm_overwrite:
            clip_count = sum(len(track.get("clips", [])) for track in document.tracks)
            raise TimelineOverwriteConfirmationRequiredError(
                "Timeline contains edits from another source; confirm overwrite to replace them.",
                details={
                    "timeline_id": document.id,
                    "existing_clip_count": clip_count,
                    "montage_plan_id": (document.metadata or {}).get("montage_plan_id"),
                },
            )

    video_track = _find_track(document.tracks, track_type="video", name="Video 1")
    game_audio_track = _find_track(document.tracks, track_type="audio", name="Audio 1")
    music_track = _find_track(document.tracks, track_type="audio", name="Music")

    selected_plan_clips = sorted(plan.clips, key=lambda clip: clip.order)
    if partial_clip_ids:
        selected_ids = set(partial_clip_ids)
        selected_plan_clips = [clip for clip in selected_plan_clips if clip.id in selected_ids]

    preserved_video = _filter_existing_clips(video_track.get("clips", []), plan=plan, partial_clip_ids=partial_clip_ids)
    preserved_audio = _filter_existing_clips(
        game_audio_track.get("clips", []),
        plan=plan,
        partial_clip_ids=partial_clip_ids,
    )

    video_clips = list(preserved_video)
    audio_clips = list(preserved_audio)
    for plan_clip in selected_plan_clips:
        video_clips.append(
            _build_timeline_clip(
                plan_clip=plan_clip,
                plan=plan,
                track_id=video_track["id"],
                include_transitions=True,
                include_effects=True,
            ),
        )
        audio_clips.append(
            _build_timeline_clip(
                plan_clip=plan_clip,
                plan=plan,
                track_id=game_audio_track["id"],
                include_transitions=False,
                include_effects=False,
            ),
        )

    video_track["clips"] = sorted(video_clips, key=lambda clip: clip["start_ms"])
    game_audio_track["clips"] = sorted(audio_clips, key=lambda clip: clip["start_ms"])

    if not partial_clip_ids:
        music_track["clips"] = []
        if plan.music is not None and plan.music.media_id and plan.duration_ms > 0:
            music_track["clips"] = [
                {
                    "id": new_uuid(),
                    "media_item_id": plan.music.media_id,
                    "track_id": music_track["id"],
                    "start_ms": 0,
                    "end_ms": plan.duration_ms,
                    "source_in_ms": 0,
                    "source_out_ms": plan.duration_ms,
                    "speed": 1.0,
                    "opacity": 1.0,
                    "volume": 1.0,
                    "effects": [],
                    "keyframes": [],
                    "transition_in": None,
                    "transition_out": None,
                    "ai": {
                        "generated": True,
                        "confidence": plan.music.confidence,
                        "reasoning": plan.music.reasoning,
                        "agent_id": "timeline-generator",
                        "agent_version": TIMELINE_GENERATOR_VERSION,
                        "montage_plan_id": plan.id,
                    },
                    "name": "Music",
                },
            ]

    document.duration_ms = plan.duration_ms
    document.markers = _build_markers(plan)
    document.beat_markers = _build_beat_markers(plan)
    document.metadata = {
        **(document.metadata or {}),
        "ai_generated": True,
        "generator": TIMELINE_GENERATOR_VERSION,
        "montage_plan_id": plan.id,
        "montage_plan_version": plan.version,
        "generated_at": utc_now_iso(),
        "montage_plan_name": plan.name,
    }
    document.updated_at = utc_now_iso()
    return document


def build_plan_timeline_application(
    *,
    project_id: str,
    plan: MontagePlan,
    timeline_id: str,
    document: TimelineDocument,
    overwritten: bool,
    partial_clip_ids: list[str] | None = None,
    updated_at: str | None = None,
) -> PlanTimelineApplication:
    video_track = _find_track(document.tracks, track_type="video", name="Video 1")
    game_audio_track = _find_track(document.tracks, track_type="audio", name="Audio 1")
    avg_confidence = (
        round(sum(clip.confidence for clip in plan.clips) / len(plan.clips), 2) if plan.clips else 0.0
    )
    partial = bool(partial_clip_ids)
    applied_count = len(partial_clip_ids) if partial else len(plan.clips)
    reasoning = (
        f"Applied {applied_count} montage clips to timeline {timeline_id}."
        if not partial
        else f"Partially regenerated {applied_count} montage clips on timeline {timeline_id}."
    )
    return PlanTimelineApplication(
        plan_id=plan.id,
        project_id=project_id,
        timeline_id=timeline_id,
        plan_version=plan.version,
        clip_count=applied_count,
        duration_ms=document.duration_ms,
        video_clip_count=len(video_track.get("clips", [])),
        audio_clip_count=len(game_audio_track.get("clips", [])),
        music_media_id=plan.music.media_id if plan.music else None,
        overwritten=overwritten,
        partial=partial,
        confidence=avg_confidence,
        reasoning=reasoning,
        cache_key=build_cache_key(plan, timeline_id, partial_clip_ids=partial_clip_ids),
        updated_at=updated_at or utc_now_iso(),
    )
