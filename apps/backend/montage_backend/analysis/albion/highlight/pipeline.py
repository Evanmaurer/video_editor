from __future__ import annotations

from dataclasses import dataclass

from montage_backend.analysis.albion.ability.albion_ability_analysis import AlbionAbilityEventType
from montage_backend.analysis.albion.combat.albion_combat_analysis import AlbionCombatEventType
from montage_backend.analysis.albion.engagement.albion_engagement_analysis import AlbionEngagementType
from montage_backend.analysis.albion.engagement.pipeline import extract_fight_durations
from montage_backend.analysis.albion.highlight.albion_highlight_analysis import (
    ALBION_HIGHLIGHT_DETECTOR_VERSION,
    AlbionHighlightAnalysisResult,
    AlbionHighlightFactor,
    AlbionHighlightFrameWindow,
    AlbionHighlightMoment,
    AlbionHighlightSummary,
)
from montage_backend.analysis.albion.highlight.config import (
    AlbionHighlightConfig,
    config_cache_token,
    factor_weights,
    get_highlight_config,
)
from montage_backend.analysis.albion.ui.albion_ui_analysis import AlbionUiElementType
from montage_backend.analysis.audio_analysis import AudioEventType
from montage_backend.analysis.ocr_analysis import sample_timestamps_ms

DEDUPE_MS = 1200


@dataclass(frozen=True)
class HighlightSignals:
    kill_count: int
    death_count: int
    fight_count: int
    bomb_count: int
    top_bomb_score: float
    sustained_combat_ms: int
    party_frame_count: int
    ocr_event_count: int
    ability_activation_count: int
    ultimate_count: int
    unique_ability_count: int
    engagement_primary: str | None
    engagement_top_score: float
    avg_motion_score: float
    max_motion_score: float
    max_audio_peak: float
    healing_keyword_hits: int
    ui_confidence_avg: float
    kill_feed_count: int


def build_window_cache_key(
    *,
    source_fingerprint: str,
    config_id: str,
    window_start_ms: int,
    window_end_ms: int,
) -> str:
    return (
        f"{ALBION_HIGHLIGHT_DETECTOR_VERSION}:{source_fingerprint}:config={config_id}:"
        f"window={window_start_ms}-{window_end_ms}"
    )


def build_detector_cache_key(
    source_fingerprint: str,
    *,
    frame_rate: float | None,
    config_id: str,
    config_token: str,
    sample_interval_ms: int,
    window_ms: int,
    source_flags: str,
) -> str:
    fps_part = f"{frame_rate:.3f}" if frame_rate is not None else "unknown"
    return (
        f"{ALBION_HIGHLIGHT_DETECTOR_VERSION}:{source_fingerprint}:fps={fps_part}:"
        f"config={config_id}:{config_token}:interval={sample_interval_ms}:"
        f"window={window_ms}:sources={source_flags}"
    )


def _normalize_search_text(*parts: str) -> str:
    return " ".join(part.strip().lower() for part in parts if part.strip())


def _clamp01(value: float) -> float:
    return round(min(max(value, 0.0), 1.0), 3)


def _clamp_score(value: float) -> float:
    return round(min(max(value, 0.0), 100.0), 1)


def count_ocr_events(*payloads: dict | None) -> int:
    total = 0
    for payload in payloads:
        if not payload:
            continue
        total += len(payload.get("mentions", []))
        for window in payload.get("frame_windows", []):
            total += len(window.get("mentions", []))
    return total


def count_healing_keywords(*payloads: dict | None, keywords: list[str]) -> int:
    lowered = [keyword.lower() for keyword in keywords]
    hits = 0
    for payload in payloads:
        if not payload:
            continue
        for mention in payload.get("mentions", []):
            text = str(mention.get("text", "")).lower()
            if any(keyword in text for keyword in lowered):
                hits += 1
        for window in payload.get("frame_windows", []):
            for mention in window.get("mentions", []):
                text = str(mention.get("text", "")).lower()
                if any(keyword in text for keyword in lowered):
                    hits += 1
    return hits


def score_motion_payload(motion_payload: dict | None) -> tuple[float, float]:
    if not motion_payload:
        return 0.0, 0.0
    scores = [
        float(window.get("motion_score", window.get("motion_intensity", 0.0)))
        for window in motion_payload.get("windows", [])
    ]
    if not scores:
        return 0.0, 0.0
    return sum(scores) / len(scores), max(scores)


def score_audio_payload(audio_payload: dict | None) -> float:
    if not audio_payload:
        return 0.0
    peaks: list[float] = []
    for event in audio_payload.get("events", []):
        if str(event.get("event_type", "")) == AudioEventType.PEAK.value:
            peaks.append(float(event.get("value", 0.0)))
    for peak in audio_payload.get("peaks", []):
        peaks.append(float(peak))
    return max(peaks) if peaks else 0.0


def average_ui_confidence(ui_payload: dict | None) -> tuple[float, int, int]:
    if not ui_payload:
        return 0.0, 0, 0
    confidences: list[float] = []
    kill_feed_count = 0
    party_frame_count = 0
    for detection in ui_payload.get("detections", []):
        confidences.append(float(detection.get("confidence", 0.0)))
        element_type = str(detection.get("element_type", ""))
        if element_type == AlbionUiElementType.KILL_FEED.value:
            kill_feed_count += 1
        if element_type == AlbionUiElementType.PARTY_FRAME.value:
            party_frame_count += 1
    summary_by_element = ui_payload.get("summary", {}).get("by_element", {})
    if isinstance(summary_by_element, dict):
        party_frame_count = max(party_frame_count, int(summary_by_element.get("party_frame", 0)))
        kill_feed_count = max(kill_feed_count, int(summary_by_element.get("kill_feed", 0)))
    if not confidences:
        return 0.0, kill_feed_count, party_frame_count
    return sum(confidences) / len(confidences), kill_feed_count, party_frame_count


def resolve_highlight_signals(
    *,
    combat_payload: dict | None,
    bomb_payload: dict | None,
    engagement_payload: dict | None,
    ability_payload: dict | None,
    albion_ocr_payload: dict | None,
    m3_ocr_payload: dict | None,
    ui_payload: dict | None,
    motion_payload: dict | None,
    audio_payload: dict | None,
    config: AlbionHighlightConfig,
) -> HighlightSignals:
    combat_summary = combat_payload.get("summary", {}) if combat_payload else {}
    bomb_summary = bomb_payload.get("summary", {}) if bomb_payload else {}
    ability_summary = ability_payload.get("summary", {}) if ability_payload else {}
    engagement_tags = engagement_payload.get("tags", []) if engagement_payload else []
    primary_engagement = engagement_payload.get("summary", {}).get("primary_engagement") if engagement_payload else None
    engagement_top_score = 0.0
    if engagement_tags:
        engagement_top_score = max(float(tag.get("score", 0.0)) for tag in engagement_tags) / 10.0

    sustained_combat_ms = max(extract_fight_durations(combat_payload), default=0)
    avg_motion, max_motion = score_motion_payload(motion_payload)
    ui_confidence, kill_feed_count, party_frame_count = average_ui_confidence(ui_payload)
    if party_frame_count == 0 and engagement_payload:
        party_frame_count = int(
            engagement_payload.get("summary", {}).get("signals", {}).get("party_frame_count", 0),
        )

    return HighlightSignals(
        kill_count=int(combat_summary.get("kill_count", 0)),
        death_count=int(combat_summary.get("death_count", 0)),
        fight_count=int(combat_summary.get("fight_count", 0)),
        bomb_count=int(bomb_summary.get("bomb_count", 0)),
        top_bomb_score=float(bomb_summary.get("top_bomb_score", 0.0)),
        sustained_combat_ms=sustained_combat_ms,
        party_frame_count=party_frame_count,
        ocr_event_count=count_ocr_events(albion_ocr_payload, m3_ocr_payload),
        ability_activation_count=int(ability_summary.get("activation_count", 0)),
        ultimate_count=int(ability_summary.get("ultimate_count", 0)),
        unique_ability_count=int(ability_summary.get("unique_ability_count", 0)),
        engagement_primary=str(primary_engagement) if primary_engagement else None,
        engagement_top_score=engagement_top_score,
        avg_motion_score=avg_motion,
        max_motion_score=max_motion,
        max_audio_peak=score_audio_payload(audio_payload),
        healing_keyword_hits=count_healing_keywords(
            albion_ocr_payload,
            m3_ocr_payload,
            keywords=config.healing_keywords,
        ),
        ui_confidence_avg=ui_confidence,
        kill_feed_count=kill_feed_count,
    )


def build_highlight_factors(
    signals: HighlightSignals,
    *,
    config: AlbionHighlightConfig,
) -> list[AlbionHighlightFactor]:
    bomb_score = _clamp01(signals.top_bomb_score / 10.0 if signals.bomb_count > 0 else 0.0)
    kill_score = _clamp01(signals.kill_count / config.kill_reference_count)
    team_score = _clamp01(
        min(
            1.0,
            (0.35 if signals.fight_count > 0 else 0.0)
            + min(signals.party_frame_count, 4) * 0.1
            + (0.25 if signals.engagement_primary == AlbionEngagementType.ZVZ.value else 0.0)
            + signals.engagement_top_score * 0.2,
        ),
    )
    survival_score = _clamp01(1.0 - signals.death_count * 0.35)
    damage_score = _clamp01(
        max(
            kill_score * 0.6,
            signals.max_motion_score / config.motion_threshold if signals.max_motion_score > 0 else 0.0,
        ),
    )
    healing_score = _clamp01(
        min(
            1.0,
            signals.healing_keyword_hits * 0.25
            + min(signals.ability_activation_count, 4) * 0.1
            + (0.2 if signals.ultimate_count > 0 else 0.0),
        ),
    )
    visual_score = _clamp01(
        max(signals.ui_confidence_avg, 0.15 if signals.kill_feed_count > 0 else 0.0),
    )
    motion_score = _clamp01(
        signals.avg_motion_score / config.motion_threshold if signals.avg_motion_score > 0 else 0.0,
    )
    audio_score = _clamp01(
        signals.max_audio_peak / config.audio_peak_threshold if signals.max_audio_peak > 0 else 0.0,
    )
    fight_duration_score = _clamp01(signals.sustained_combat_ms / config.fight_duration_reference_ms)
    ocr_score = _clamp01(min(1.0, signals.ocr_event_count / 6.0))
    ability_score = _clamp01(
        min(
            1.0,
            min(signals.unique_ability_count, 4) * 0.2
            + min(signals.ultimate_count, 2) * 0.25
            + min(signals.ability_activation_count, 6) * 0.08,
        ),
    )

    raw_factors = {
        "bomb_quality": (
            bomb_score,
            (
                f"Top bomb score {signals.top_bomb_score:.1f}/10"
                if signals.bomb_count > 0
                else "No bomb events detected"
            ),
        ),
        "kill_count": (
            kill_score,
            f"{signals.kill_count} kill notification(s) in combat timeline",
        ),
        "team_fight_intensity": (
            team_score,
            (
                f"{signals.fight_count} fight(s), party UI x{signals.party_frame_count}, "
                f"engagement={signals.engagement_primary or 'none'}"
            ),
        ),
        "player_survival": (
            survival_score,
            "No deaths recorded" if signals.death_count == 0 else f"{signals.death_count} death(s) recorded",
        ),
        "damage_spikes": (
            damage_score,
            f"Kill spike + motion peak {signals.max_motion_score:.2f}",
        ),
        "healing_spikes": (
            healing_score,
            (
                f"{signals.healing_keyword_hits} healing OCR hit(s), "
                f"{signals.ability_activation_count} ability activation(s)"
            ),
        ),
        "visual_clarity": (
            visual_score,
            f"UI confidence {signals.ui_confidence_avg:.2f}, kill feed detections={signals.kill_feed_count}",
        ),
        "motion": (
            motion_score,
            f"Average motion {signals.avg_motion_score:.2f}",
        ),
        "audio_intensity": (
            audio_score,
            f"Peak audio intensity {signals.max_audio_peak:.2f}",
        ),
        "fight_duration": (
            fight_duration_score,
            f"Sustained combat {signals.sustained_combat_ms}ms",
        ),
        "ocr_events": (
            ocr_score,
            f"{signals.ocr_event_count} OCR combat mention(s)",
        ),
        "ability_combinations": (
            ability_score,
            (
                f"{signals.unique_ability_count} unique abilities, "
                f"{signals.ultimate_count} ultimate(s), "
                f"{signals.ability_activation_count} activation(s)"
            ),
        ),
    }

    weight_total = sum(weight for _, _, weight in factor_weights(config)) or 1.0
    factors: list[AlbionHighlightFactor] = []
    for factor_id, label, weight in factor_weights(config):
        score, reasoning = raw_factors[factor_id]
        contribution = _clamp_score((score * weight / weight_total) * 100.0)
        factors.append(
            AlbionHighlightFactor(
                factor_id=factor_id,
                label=label,
                score=score,
                weight=round(weight, 3),
                contribution=contribution,
                reasoning=reasoning,
            ),
        )
    return factors


def compute_highlight_score(factors: list[AlbionHighlightFactor]) -> float:
    weight_total = sum(factor.weight for factor in factors) or 1.0
    weighted = sum(factor.score * factor.weight for factor in factors) / weight_total
    return _clamp_score(weighted * 100.0)


def build_highlight_explanation(
    factors: list[AlbionHighlightFactor],
    *,
    highlight_score: float,
) -> str:
    ranked = sorted(factors, key=lambda item: (-item.contribution, item.factor_id))
    top = ranked[:4]
    parts = [f"Albion highlight score {highlight_score:.1f}/100"]
    for factor in top:
        if factor.contribution <= 0:
            continue
        parts.append(f"{factor.label}: {factor.reasoning}")
    return ". ".join(parts) + "."


def build_highlight_moments(
    *,
    combat_payload: dict | None,
    bomb_payload: dict | None,
    ability_payload: dict | None,
    config: AlbionHighlightConfig,
) -> list[AlbionHighlightMoment]:
    moments: list[AlbionHighlightMoment] = []

    for index, event in enumerate((bomb_payload or {}).get("events", [])):
        bomb_score = float(event.get("bomb_score", 0.0))
        timestamp_ms = int(event.get("timestamp_ms", 0))
        moments.append(
            AlbionHighlightMoment(
                moment_id=f"highlight:bomb:{timestamp_ms}:{index}",
                timestamp_ms=timestamp_ms,
                window_start_ms=int(event.get("window_start_ms", timestamp_ms)),
                window_end_ms=int(event.get("window_end_ms", timestamp_ms + config.window_ms)),
                moment_score=_clamp_score(bomb_score * 10.0),
                confidence=float(event.get("confidence", 0.7)),
                moment_type="bomb",
                reasoning=str(event.get("reasoning", "Bomb moment")),
                search_text=_normalize_search_text("highlight", "bomb", event.get("search_text", "")),
                metadata={"kill_count": event.get("kill_count", 0)},
            ),
        )

    for index, entry in enumerate((combat_payload or {}).get("entries", [])):
        event_type = str(entry.get("event_type", ""))
        if event_type not in {
            AlbionCombatEventType.KILL.value,
            AlbionCombatEventType.FIGHT_START.value,
            AlbionCombatEventType.DEATH.value,
        }:
            continue
        timestamp_ms = int(entry.get("timestamp_ms", 0))
        base_score = 55.0
        if event_type == AlbionCombatEventType.KILL.value:
            base_score = 68.0
        elif event_type == AlbionCombatEventType.FIGHT_START.value:
            base_score = 62.0
        elif event_type == AlbionCombatEventType.DEATH.value:
            base_score = 72.0
        moments.append(
            AlbionHighlightMoment(
                moment_id=f"highlight:{event_type}:{timestamp_ms}:{index}",
                timestamp_ms=timestamp_ms,
                window_start_ms=int(entry.get("window_start_ms", timestamp_ms)),
                window_end_ms=int(entry.get("window_end_ms", timestamp_ms + config.window_ms)),
                moment_score=base_score,
                confidence=float(entry.get("confidence", 0.65)),
                moment_type=event_type,
                reasoning=str(entry.get("label", event_type)),
                search_text=_normalize_search_text("highlight", event_type, entry.get("search_text", "")),
                metadata=dict(entry.get("metadata", {})),
            ),
        )

    for index, event in enumerate((ability_payload or {}).get("events", [])):
        event_type = str(event.get("event_type", ""))
        if event_type not in {
            AlbionAbilityEventType.ACTIVATION.value,
            AlbionAbilityEventType.ULTIMATE_ACTIVATION.value,
        }:
            continue
        timestamp_ms = int(event.get("timestamp_ms", 0))
        base_score = 58.0 if event_type == AlbionAbilityEventType.ACTIVATION.value else 74.0
        moments.append(
            AlbionHighlightMoment(
                moment_id=f"highlight:ability:{timestamp_ms}:{index}",
                timestamp_ms=timestamp_ms,
                window_start_ms=int(event.get("window_start_ms", timestamp_ms)),
                window_end_ms=int(event.get("window_end_ms", timestamp_ms + config.window_ms)),
                moment_score=base_score,
                confidence=float(event.get("confidence", 0.6)),
                moment_type="ability",
                reasoning=f"{event.get('ability_name', 'Ability')} {event_type.replace('_', ' ')}",
                search_text=_normalize_search_text(
                    "highlight",
                    "ability",
                    str(event.get("ability_name", "")),
                    event_type,
                ),
                metadata={"ability_id": event.get("ability_id", "")},
            ),
        )

    return dedupe_highlight_moments(moments)[: config.max_moments]


def dedupe_highlight_moments(moments: list[AlbionHighlightMoment]) -> list[AlbionHighlightMoment]:
    if not moments:
        return []
    sorted_moments = sorted(moments, key=lambda item: (-item.moment_score, item.timestamp_ms))
    kept: list[AlbionHighlightMoment] = []
    for moment in sorted_moments:
        if any(abs(moment.timestamp_ms - existing.timestamp_ms) < DEDUPE_MS for existing in kept):
            continue
        kept.append(moment)
    return sorted(kept, key=lambda item: (-item.moment_score, item.timestamp_ms))


def group_moments_into_windows(
    moments: list[AlbionHighlightMoment],
    *,
    timestamps: list[int],
    window_ms: int,
    source_fingerprint: str,
    config_id: str,
) -> list[AlbionHighlightFrameWindow]:
    windows: list[AlbionHighlightFrameWindow] = []
    for timestamp_ms in timestamps:
        window_start = timestamp_ms
        window_end = timestamp_ms + window_ms
        window_moments = [
            moment
            for moment in moments
            if window_start <= moment.timestamp_ms < window_end
            or window_start <= moment.window_start_ms < window_end
        ]
        window_score = max((moment.moment_score for moment in window_moments), default=0.0)
        windows.append(
            AlbionHighlightFrameWindow(
                window_start_ms=window_start,
                window_end_ms=window_end,
                cache_key=build_window_cache_key(
                    source_fingerprint=source_fingerprint,
                    config_id=config_id,
                    window_start_ms=window_start,
                    window_end_ms=window_end,
                ),
                config_id=config_id,
                window_score=window_score,
                moment_count=len(window_moments),
                moments=window_moments,
            ),
        )
    return windows


def run_albion_highlight_pipeline(
    *,
    source_fingerprint: str,
    duration_ms: int,
    frame_rate: float,
    combat_payload: dict | None,
    bomb_payload: dict | None,
    engagement_payload: dict | None,
    ability_payload: dict | None,
    albion_ocr_payload: dict | None,
    m3_ocr_payload: dict | None,
    ui_payload: dict | None,
    motion_payload: dict | None,
    audio_payload: dict | None,
    config_id: str | None = None,
) -> AlbionHighlightAnalysisResult:
    config = get_highlight_config(config_id)
    signals = resolve_highlight_signals(
        combat_payload=combat_payload,
        bomb_payload=bomb_payload,
        engagement_payload=engagement_payload,
        ability_payload=ability_payload,
        albion_ocr_payload=albion_ocr_payload,
        m3_ocr_payload=m3_ocr_payload,
        ui_payload=ui_payload,
        motion_payload=motion_payload,
        audio_payload=audio_payload,
        config=config,
    )
    factors = build_highlight_factors(signals, config=config)
    highlight_score = compute_highlight_score(factors)
    explanation = build_highlight_explanation(factors, highlight_score=highlight_score)
    moments = build_highlight_moments(
        combat_payload=combat_payload,
        bomb_payload=bomb_payload,
        ability_payload=ability_payload,
        config=config,
    )

    timestamps = sample_timestamps_ms(
        duration_ms,
        interval_ms=config.sample_interval_ms,
        max_frames=max(duration_ms // config.sample_interval_ms + 1, len(moments), 1),
    )
    if not timestamps:
        timestamps = [0]

    frame_windows = group_moments_into_windows(
        moments,
        timestamps=timestamps,
        window_ms=config.window_ms,
        source_fingerprint=source_fingerprint,
        config_id=config.id,
    )

    source_flags = ",".join(
        flag
        for flag, enabled in (
            ("combat", combat_payload is not None),
            ("bomb", bomb_payload is not None),
            ("engagement", engagement_payload is not None),
            ("ability", ability_payload is not None),
            ("albion-ocr", albion_ocr_payload is not None),
            ("m3-ocr", m3_ocr_payload is not None),
            ("ui", ui_payload is not None),
            ("motion", motion_payload is not None),
            ("audio", audio_payload is not None),
        )
        if enabled
    ) or "none"

    cache_key = build_detector_cache_key(
        source_fingerprint,
        frame_rate=frame_rate,
        config_id=config.id,
        config_token=config_cache_token(config),
        sample_interval_ms=config.sample_interval_ms,
        window_ms=config.window_ms,
        source_flags=source_flags,
    )
    for suffix, payload in (
        ("combat", combat_payload),
        ("bomb", bomb_payload),
        ("engagement", engagement_payload),
    ):
        if payload is not None:
            cache_key = f"{cache_key}:{suffix}:{payload.get('cache_key', 'unknown')}"

    ranked_factors = sorted(factors, key=lambda item: (-item.contribution, item.factor_id))
    confidence = 0.45
    if highlight_score > 0:
        confidence = min(0.98, 0.5 + highlight_score / 140.0)
    by_moment_type: dict[str, int] = {}
    for moment in moments:
        by_moment_type[moment.moment_type] = by_moment_type.get(moment.moment_type, 0) + 1

    return AlbionHighlightAnalysisResult(
        cache_key=cache_key,
        duration_ms=duration_ms,
        frame_rate=frame_rate,
        window_ms=config.window_ms,
        sample_interval_ms=config.sample_interval_ms,
        config_id=config.id,
        highlight_score=highlight_score,
        confidence=round(confidence, 3),
        explanation=explanation,
        summary=AlbionHighlightSummary(
            frames_sampled=len(timestamps),
            window_count=len(frame_windows),
            moment_count=len(moments),
            highlight_score=highlight_score,
            confidence=round(confidence, 3),
            explanation=explanation,
            config_id=config.id,
            factor_count=len(factors),
            top_factor_ids=[factor.factor_id for factor in ranked_factors[:4]],
            by_moment_type=by_moment_type,
            reused_albion_combat=combat_payload is not None,
            reused_albion_bomb=bomb_payload is not None,
            reused_albion_engagement=engagement_payload is not None,
            reused_albion_ability=ability_payload is not None,
            reused_albion_ocr=albion_ocr_payload is not None,
            reused_albion_ui=ui_payload is not None,
            reused_motion=motion_payload is not None,
            reused_audio=audio_payload is not None,
        ),
        factors=factors,
        frame_windows=frame_windows,
        moments=moments,
    )
