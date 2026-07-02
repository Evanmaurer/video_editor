from __future__ import annotations

import hashlib
import random
from dataclasses import dataclass

from montage_backend.models.domain import new_uuid, utc_now_iso
from montage_backend.models.domain.clip_highlight import ClipHighlights, HighlightSegment
from montage_backend.models.domain.clip_score import ClipScore
from montage_backend.models.domain.montage_plan import (
    MontagePlan,
    MontagePlanCard,
    MontagePlanClip,
)
from montage_backend.models.domain.plan_draft import (
    DRAFT_GENERATOR_VERSION,
    DraftClipCandidate,
    PlanDraftAnalysis,
)
from montage_backend.montage.pacing_engine import PACING_PROFILES, normalize_pacing_profile

MIN_SEGMENT_MS = 1200
MAX_SEGMENTS_PER_MEDIA = 2
HIGHLIGHT_SCORE_WEIGHT = 0.62
CLIP_SCORE_WEIGHT = 0.38

PROFILE_CLIP_LIMITS: dict[str, tuple[int, int]] = {
    "balanced": (6, 12),
    "aggressive": (8, 16),
    "cinematic": (4, 8),
    "music_driven": (7, 14),
    "story_driven": (5, 10),
}


@dataclass(frozen=True)
class SegmentCandidate:
    media_id: str
    file_name: str | None
    source_start_ms: int
    source_end_ms: int
    clip_score: float
    highlight_score: float
    combined_score: float
    confidence: float
    reasoning: str


def build_project_signature(
    scores: list[ClipScore],
    highlights: list[ClipHighlights],
) -> str:
    score_part = "|".join(
        f"{score.media_id}:{score.montage_score:.1f}:{score.cache_key}"
        for score in sorted(scores, key=lambda item: item.media_id)
    )
    highlight_part = "|".join(
        f"{clip.media_id}:{clip.highlight_count}:{clip.cache_key}"
        for clip in sorted(highlights, key=lambda item: item.media_id)
    )
    payload = f"{score_part}::{highlight_part}"
    return hashlib.sha256(payload.encode()).hexdigest()[:16]


def build_cache_key(
    plan_id: str,
    random_seed: int,
    pacing_profile: str | None,
    target_duration_ms: int | None,
    project_signature: str,
    music_media_id: str | None,
) -> str:
    profile = normalize_pacing_profile(pacing_profile)
    target = target_duration_ms if target_duration_ms is not None else 0
    music = music_media_id or "none"
    return f"{DRAFT_GENERATOR_VERSION}:{plan_id}:{random_seed}:{profile}:{target}:{project_signature}:{music}"


def _clamp_ms(value: int, *, minimum: int = 0, maximum: int | None = None) -> int:
    result = max(minimum, value)
    if maximum is not None:
        result = min(result, maximum)
    return result


def _segment_from_highlight(
    *,
    media_id: str,
    file_name: str | None,
    segment: HighlightSegment,
    clip_score: ClipScore,
) -> SegmentCandidate:
    combined = (segment.score * HIGHLIGHT_SCORE_WEIGHT) + (clip_score.montage_score * CLIP_SCORE_WEIGHT)
    confidence = round(min((segment.confidence * 0.6) + (clip_score.confidence * 0.4), 0.98), 2)
    duration_ms = segment.end_ms - segment.start_ms
    reasoning = (
        f"Highlight {segment.start_ms}-{segment.end_ms}ms ({duration_ms}ms) "
        f"with montage score {clip_score.montage_score:.1f}"
    )
    return SegmentCandidate(
        media_id=media_id,
        file_name=file_name,
        source_start_ms=segment.start_ms,
        source_end_ms=segment.end_ms,
        clip_score=clip_score.montage_score,
        highlight_score=segment.score,
        combined_score=round(combined, 2),
        confidence=confidence,
        reasoning=reasoning,
    )


def _segment_from_full_clip(clip_score: ClipScore) -> SegmentCandidate:
    duration_ms = clip_score.duration_ms or 8000
    source_end_ms = _clamp_ms(duration_ms, minimum=MIN_SEGMENT_MS)
    combined = clip_score.montage_score * 0.85
    return SegmentCandidate(
        media_id=clip_score.media_id,
        file_name=clip_score.file_name,
        source_start_ms=0,
        source_end_ms=source_end_ms,
        clip_score=clip_score.montage_score,
        highlight_score=clip_score.montage_score * 0.7,
        combined_score=round(combined, 2),
        confidence=round(clip_score.confidence * 0.85, 2),
        reasoning=f"Full clip fallback; montage score {clip_score.montage_score:.1f}",
    )


def apply_feedback_score_bias(
    candidates: list[SegmentCandidate],
    feedback_preferences: dict | None,
) -> None:
    if not feedback_preferences:
        return
    quality_bias = float(feedback_preferences.get("quality_bias", 0.0))
    action_bias = float(feedback_preferences.get("action_bias", 0.0))
    if quality_bias == 0.0 and action_bias == 0.0:
        return
    for candidate in candidates:
        boost = quality_bias * 10.0
        if action_bias > 0:
            boost += action_bias * candidate.highlight_score * 0.1
        candidate.combined_score = round(max(0.0, candidate.combined_score + boost), 2)


def collect_segment_candidates(
    scores: list[ClipScore],
    highlights: list[ClipHighlights],
) -> list[SegmentCandidate]:
    highlight_map = {item.media_id: item for item in highlights}
    candidates: list[SegmentCandidate] = []

    for clip_score in scores:
        highlight_entry = highlight_map.get(clip_score.media_id)
        if highlight_entry is not None and highlight_entry.highlights:
            for segment in highlight_entry.highlights:
                if segment.end_ms - segment.start_ms < MIN_SEGMENT_MS:
                    continue
                candidates.append(
                    _segment_from_highlight(
                        media_id=clip_score.media_id,
                        file_name=clip_score.file_name,
                        segment=segment,
                        clip_score=clip_score,
                    ),
                )
        else:
            candidates.append(_segment_from_full_clip(clip_score))

    candidates.sort(key=lambda item: item.combined_score, reverse=True)
    return candidates


def _max_clip_count(
    *,
    pacing_profile: str,
    target_duration_ms: int | None,
) -> int:
    profile = normalize_pacing_profile(pacing_profile)
    minimum, maximum = PROFILE_CLIP_LIMITS.get(profile, PROFILE_CLIP_LIMITS["balanced"])
    if target_duration_ms is None:
        return maximum

    base_duration = PACING_PROFILES[profile].base_duration_ms
    estimated = max(minimum, target_duration_ms // max(base_duration, 1))
    return _clamp_ms(estimated, minimum=minimum, maximum=maximum)


def select_segment_candidates(
    candidates: list[SegmentCandidate],
    *,
    pacing_profile: str,
    target_duration_ms: int | None,
    random_seed: int,
) -> list[SegmentCandidate]:
    if not candidates:
        return []

    max_clips = _max_clip_count(pacing_profile=pacing_profile, target_duration_ms=target_duration_ms)
    selected: list[SegmentCandidate] = []
    per_media: dict[str, int] = {}

    for candidate in candidates:
        if len(selected) >= max_clips:
            break
        count = per_media.get(candidate.media_id, 0)
        if count >= MAX_SEGMENTS_PER_MEDIA:
            continue
        selected.append(candidate)
        per_media[candidate.media_id] = count + 1

    if len(selected) < min(3, max_clips):
        for candidate in candidates:
            if candidate in selected:
                continue
            if len(selected) >= max_clips:
                break
            selected.append(candidate)

    return order_excitement_arc(selected, random_seed=random_seed)


def order_excitement_arc(
    candidates: list[SegmentCandidate],
    *,
    random_seed: int,
) -> list[SegmentCandidate]:
    if len(candidates) <= 2:
        return candidates

    ranked = sorted(candidates, key=lambda item: item.combined_score, reverse=True)
    n = len(ranked)
    ordered: list[SegmentCandidate | None] = [None] * n
    peak_index = n // 2
    ordered[peak_index] = ranked[0]

    left = peak_index - 1
    right = peak_index + 1
    for index, candidate in enumerate(ranked[1:], start=1):
        if index % 2 == 1 and left >= 0:
            ordered[left] = candidate
            left -= 1
        elif right < n:
            ordered[right] = candidate
            right += 1
        elif left >= 0:
            ordered[left] = candidate
            left -= 1

    result = [item for item in ordered if item is not None]
    rng = random.Random(random_seed)
    if len(result) > 3 and rng.random() < 0.15:
        swap_index = rng.randint(1, len(result) - 2)
        result[0], result[swap_index] = result[swap_index], result[0]
    return result


def build_title_card(plan: MontagePlan) -> MontagePlanCard:
    return MontagePlanCard(
        type="title",
        text=plan.name,
        duration_ms=2500,
        confidence=0.86,
        reasoning=f"Title card for {plan.name}",
    )


def build_ending_card(*, random_seed: int) -> MontagePlanCard:
    endings = ["GG", "Thanks for watching", "Like & Subscribe"]
    rng = random.Random(random_seed + 991)
    text = rng.choice(endings)
    return MontagePlanCard(
        type="ending",
        text=text,
        duration_ms=2000,
        confidence=0.82,
        reasoning=f"Ending card: {text}",
    )


def choose_music_media_id(
    plan: MontagePlan,
    available_music_ids: list[str],
) -> str | None:
    if plan.music is not None and plan.music.media_id:
        if plan.music.media_id in available_music_ids or not available_music_ids:
            return plan.music.media_id
    if not available_music_ids:
        return None
    return available_music_ids[0]


def generate_plan_draft(
    *,
    project_id: str,
    plan: MontagePlan,
    scores: list[ClipScore],
    highlights: list[ClipHighlights],
    available_music_ids: list[str] | None = None,
    updated_at: str | None = None,
) -> PlanDraftAnalysis:
    pacing = normalize_pacing_profile(plan.metadata.pacing_profile)
    seed = plan.metadata.random_seed
    project_signature = build_project_signature(scores, highlights)
    music_media_id = choose_music_media_id(plan, available_music_ids or [])

    all_candidates = collect_segment_candidates(scores, highlights)
    apply_feedback_score_bias(all_candidates, plan.metadata.feedback_preferences)
    selected = select_segment_candidates(
        all_candidates,
        pacing_profile=pacing,
        target_duration_ms=plan.metadata.target_duration_ms,
        random_seed=seed,
    )

    draft_candidates: list[DraftClipCandidate] = []
    for order, segment in enumerate(selected):
        draft_candidates.append(
            DraftClipCandidate(
                clip_id=new_uuid(),
                media_id=segment.media_id,
                file_name=segment.file_name,
                order=order,
                source_start_ms=segment.source_start_ms,
                source_end_ms=segment.source_end_ms,
                clip_score=segment.clip_score,
                highlight_score=segment.highlight_score,
                combined_score=segment.combined_score,
                confidence=segment.confidence,
                reasoning=segment.reasoning,
            ),
        )

    avg_confidence = (
        round(sum(item.confidence for item in draft_candidates) / len(draft_candidates), 2)
        if draft_candidates
        else 0.0
    )
    if draft_candidates:
        reasoning = (
            f"Selected {len(draft_candidates)} clips from {len(scores)} scored sources "
            f"using {pacing} pacing and excitement-arc ordering."
        )
    else:
        reasoning = "No scored clips available; import and analyze gameplay clips before generating a draft."

    return PlanDraftAnalysis(
        plan_id=plan.id,
        project_id=project_id,
        pacing_profile=pacing,
        target_duration_ms=plan.metadata.target_duration_ms,
        clip_count=len(draft_candidates),
        candidates=draft_candidates,
        title_card=build_title_card(plan),
        ending_card=build_ending_card(random_seed=seed),
        music_media_id=music_media_id,
        confidence=avg_confidence,
        reasoning=reasoning,
        cache_key=build_cache_key(
            plan.id,
            seed,
            pacing,
            plan.metadata.target_duration_ms,
            project_signature,
            music_media_id,
        ),
        random_seed=seed,
        updated_at=updated_at or utc_now_iso(),
    )


def build_plan_clips_from_draft(analysis: PlanDraftAnalysis) -> list[MontagePlanClip]:
    clips: list[MontagePlanClip] = []
    timeline_cursor = analysis.title_card.duration_ms
    placeholder_duration = 3000

    for candidate in sorted(analysis.candidates, key=lambda item: item.order):
        timeline_start = timeline_cursor
        timeline_end = timeline_start + placeholder_duration
        clips.append(
            MontagePlanClip(
                id=candidate.clip_id,
                media_id=candidate.media_id,
                order=candidate.order,
                source_start_ms=candidate.source_start_ms,
                source_end_ms=candidate.source_end_ms,
                timeline_start_ms=timeline_start,
                timeline_end_ms=timeline_end,
                clip_score=candidate.clip_score,
                confidence=candidate.confidence,
                reasoning=candidate.reasoning,
            ),
        )
        timeline_cursor = timeline_end

    return clips


def apply_draft_to_plan(plan: MontagePlan, analysis: PlanDraftAnalysis) -> None:
    plan.clips = build_plan_clips_from_draft(analysis)
    plan.title_card = analysis.title_card
    plan.ending_card = analysis.ending_card
    if analysis.music_media_id:
        from montage_backend.models.domain.montage_plan import MontagePlanMusic

        plan.music = plan.music or MontagePlanMusic()
        plan.music.media_id = analysis.music_media_id
        if not plan.music.reasoning:
            plan.music.reasoning = "Music track selected for draft montage"
