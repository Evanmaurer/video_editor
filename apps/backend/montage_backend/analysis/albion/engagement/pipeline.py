from __future__ import annotations

from dataclasses import dataclass

from montage_backend.analysis.albion.combat.albion_combat_analysis import AlbionCombatEventType
from montage_backend.analysis.albion.engagement.albion_engagement_analysis import (
    ALBION_ENGAGEMENT_DETECTOR_VERSION,
    AlbionEngagementAnalysisResult,
    AlbionEngagementFrameWindow,
    AlbionEngagementSignals,
    AlbionEngagementSummary,
    AlbionEngagementTag,
    AlbionEngagementType,
)
from montage_backend.analysis.albion.engagement.config import (
    AlbionEngagementConfig,
    config_cache_token,
    get_engagement_config,
)
from montage_backend.analysis.albion.ui.albion_ui_analysis import AlbionUiElementType
from montage_backend.analysis.ocr_analysis import sample_timestamps_ms


@dataclass(frozen=True)
class ClipEngagementSignals:
    duration_ms: int
    kill_count: int
    death_count: int
    fight_count: int
    bomb_count: int
    top_bomb_score: float
    sustained_combat_ms: int
    sustained_ui_ms: int
    party_frame_count: int
    resource_bar_count: int
    minimap_count: int
    gathering_keyword_hits: int
    avg_motion_score: float
    max_motion_score: float
    kill_span_ms: int


def build_window_cache_key(
    *,
    source_fingerprint: str,
    config_id: str,
    window_start_ms: int,
    window_end_ms: int,
) -> str:
    return (
        f"{ALBION_ENGAGEMENT_DETECTOR_VERSION}:{source_fingerprint}:config={config_id}:"
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
        f"{ALBION_ENGAGEMENT_DETECTOR_VERSION}:{source_fingerprint}:fps={fps_part}:"
        f"config={config_id}:{config_token}:interval={sample_interval_ms}:"
        f"window={window_ms}:sources={source_flags}"
    )


def _normalize_search_text(*parts: str) -> str:
    return " ".join(part.strip().lower() for part in parts if part.strip())


def extract_fight_durations(combat_payload: dict | None) -> list[int]:
    if not combat_payload:
        return []
    durations: list[int] = []
    for entry in combat_payload.get("entries", []):
        if str(entry.get("event_type", "")) != AlbionCombatEventType.FIGHT_START.value:
            continue
        fight_end_ms = entry.get("metadata", {}).get("fight_end_ms")
        if fight_end_ms is None:
            continue
        duration = int(fight_end_ms) - int(entry.get("timestamp_ms", 0))
        if duration > 0:
            durations.append(duration)
    return durations


def extract_kill_span_ms(combat_payload: dict | None) -> int:
    if not combat_payload:
        return 0
    kill_times = [
        int(entry.get("timestamp_ms", 0))
        for entry in combat_payload.get("entries", [])
        if str(entry.get("event_type", "")) == AlbionCombatEventType.KILL.value
    ]
    if len(kill_times) < 2:
        return 0
    return max(kill_times) - min(kill_times)


def extract_ui_element_span_ms(ui_payload: dict | None, element_type: str) -> int:
    if not ui_payload:
        return 0
    timestamps = [
        int(detection.get("timestamp_ms", 0))
        for detection in ui_payload.get("detections", [])
        if str(detection.get("element_type", "")) == element_type
    ]
    if len(timestamps) < 2:
        return 0
    return max(timestamps) - min(timestamps)


def count_ui_elements(ui_payload: dict | None) -> dict[str, int]:
    if not ui_payload:
        return {}
    counts: dict[str, int] = {}
    for detection in ui_payload.get("detections", []):
        element_type = str(detection.get("element_type", "unknown"))
        counts[element_type] = counts.get(element_type, 0) + 1
    summary_by_element = ui_payload.get("summary", {}).get("by_element", {})
    if isinstance(summary_by_element, dict):
        for element_type, count in summary_by_element.items():
            counts[str(element_type)] = max(counts.get(str(element_type), 0), int(count))
    return counts


def count_gathering_keywords(
    *,
    albion_ocr_payload: dict | None,
    m3_ocr_payload: dict | None,
    keywords: list[str],
) -> int:
    lowered_keywords = [keyword.lower() for keyword in keywords]
    hits = 0
    for payload in (albion_ocr_payload, m3_ocr_payload):
        if not payload:
            continue
        for mention in payload.get("mentions", []):
            text = str(mention.get("text", "")).lower()
            if any(keyword in text for keyword in lowered_keywords):
                hits += 1
        for window in payload.get("frame_windows", []):
            for mention in window.get("mentions", []):
                text = str(mention.get("text", "")).lower()
                if any(keyword in text for keyword in lowered_keywords):
                    hits += 1
    return hits


def score_motion_payload(motion_payload: dict | None) -> tuple[float, float]:
    if not motion_payload:
        return 0.0, 0.0
    scores: list[float] = []
    for window in motion_payload.get("windows", []):
        scores.append(float(window.get("motion_score", window.get("motion_intensity", 0.0))))
    if not scores:
        return 0.0, 0.0
    return sum(scores) / len(scores), max(scores)


def resolve_clip_signals(
    *,
    duration_ms: int,
    combat_payload: dict | None,
    bomb_payload: dict | None,
    ui_payload: dict | None,
    albion_ocr_payload: dict | None,
    m3_ocr_payload: dict | None,
    motion_payload: dict | None,
    keywords: list[str],
) -> ClipEngagementSignals:
    combat_summary = combat_payload.get("summary", {}) if combat_payload else {}
    bomb_summary = bomb_payload.get("summary", {}) if bomb_payload else {}
    fight_durations = extract_fight_durations(combat_payload)
    sustained_combat_ms = max(fight_durations, default=0)
    ui_counts = count_ui_elements(ui_payload)
    health_bar_span = extract_ui_element_span_ms(
        ui_payload,
        AlbionUiElementType.HEALTH_BAR.value,
    )
    sustained_ui_ms = max(sustained_combat_ms, health_bar_span)
    avg_motion, max_motion = score_motion_payload(motion_payload)
    return ClipEngagementSignals(
        duration_ms=duration_ms,
        kill_count=int(combat_summary.get("kill_count", 0)),
        death_count=int(combat_summary.get("death_count", 0)),
        fight_count=int(combat_summary.get("fight_count", 0)),
        bomb_count=int(bomb_summary.get("bomb_count", 0)),
        top_bomb_score=float(bomb_summary.get("top_bomb_score", 0.0)),
        sustained_combat_ms=sustained_combat_ms,
        sustained_ui_ms=sustained_ui_ms,
        party_frame_count=ui_counts.get(AlbionUiElementType.PARTY_FRAME.value, 0),
        resource_bar_count=ui_counts.get(AlbionUiElementType.RESOURCE_BAR.value, 0),
        minimap_count=ui_counts.get(AlbionUiElementType.MINIMAP.value, 0),
        gathering_keyword_hits=count_gathering_keywords(
            albion_ocr_payload=albion_ocr_payload,
            m3_ocr_payload=m3_ocr_payload,
            keywords=keywords,
        ),
        avg_motion_score=avg_motion,
        max_motion_score=max_motion,
        kill_span_ms=extract_kill_span_ms(combat_payload),
    )


def _build_tag(
    engagement_type: AlbionEngagementType,
    confidence: float,
    reasoning: str,
    *,
    metadata: dict | None = None,
) -> AlbionEngagementTag:
    clamped = round(min(max(confidence, 0.0), 1.0), 3)
    return AlbionEngagementTag(
        engagement_type=engagement_type,
        confidence=clamped,
        score=round(clamped * 10.0, 1),
        reasoning=reasoning,
        search_text=_normalize_search_text(engagement_type.value, reasoning),
        metadata=metadata or {},
    )


def score_zvz(signals: ClipEngagementSignals, config: AlbionEngagementConfig) -> AlbionEngagementTag | None:
    confidence = 0.0
    reasons: list[str] = []
    if signals.bomb_count >= config.zvz_min_bombs:
        confidence = max(confidence, 0.82 + min(signals.top_bomb_score / 100.0, 0.15))
        reasons.append(f"{signals.bomb_count} bomb event(s)")
    if signals.kill_count >= config.zvz_min_kills:
        confidence = max(confidence, 0.78 + min((signals.kill_count - config.zvz_min_kills) * 0.04, 0.12))
        reasons.append(f"{signals.kill_count} kills")
    if (
        signals.kill_count >= 3
        and signals.sustained_combat_ms >= config.engagement_min_duration_ms
        and signals.party_frame_count > 0
    ):
        confidence = max(confidence, 0.72)
        reasons.append("sustained group combat")
    if confidence < config.min_tag_confidence:
        return None
    return _build_tag(
        AlbionEngagementType.ZVZ,
        confidence,
        "ZvZ engagement: " + ", ".join(reasons),
        metadata={"kill_count": signals.kill_count, "bomb_count": signals.bomb_count},
    )


def score_ganking(signals: ClipEngagementSignals, config: AlbionEngagementConfig) -> AlbionEngagementTag | None:
    if signals.kill_count <= 0 or signals.kill_count > config.ganking_max_kills:
        return None
    if signals.bomb_count > 0:
        return None
    span = signals.kill_span_ms or signals.duration_ms
    if span > config.ganking_max_span_ms:
        return None
    confidence = 0.55 + (config.ganking_max_kills - signals.kill_count + 1) * 0.1
    if signals.sustained_combat_ms > 0 and signals.sustained_combat_ms < config.engagement_min_duration_ms:
        confidence += 0.05
    if confidence < config.min_tag_confidence:
        return None
    return _build_tag(
        AlbionEngagementType.GANKING,
        confidence,
        f"Ganking engagement: {signals.kill_count} kill(s) in a short burst",
        metadata={"kill_count": signals.kill_count, "kill_span_ms": signals.kill_span_ms},
    )


def score_gathering(signals: ClipEngagementSignals, config: AlbionEngagementConfig) -> AlbionEngagementTag | None:
    if signals.kill_count > config.gathering_max_kills:
        return None
    if signals.bomb_count > 0:
        return None
    confidence = 0.4
    reasons: list[str] = []
    if signals.avg_motion_score <= config.gathering_max_motion_score:
        confidence += 0.15
        reasons.append("low combat motion")
    if signals.resource_bar_count > 0:
        confidence += 0.2
        reasons.append("resource UI visible")
    if signals.gathering_keyword_hits > 0:
        confidence += min(0.25, signals.gathering_keyword_hits * 0.08)
        reasons.append(f"{signals.gathering_keyword_hits} gathering OCR hit(s)")
    if signals.sustained_combat_ms < config.engagement_min_duration_ms:
        confidence += 0.1
        reasons.append("no sustained combat")
    if not reasons:
        return None
    if confidence < config.min_tag_confidence:
        return None
    return _build_tag(
        AlbionEngagementType.GATHERING,
        confidence,
        "Gathering engagement: " + ", ".join(reasons),
        metadata={
            "gathering_keyword_hits": signals.gathering_keyword_hits,
            "resource_bar_count": signals.resource_bar_count,
        },
    )


def score_dungeon(signals: ClipEngagementSignals, config: AlbionEngagementConfig) -> AlbionEngagementTag | None:
    if signals.bomb_count > 0:
        return None
    if signals.sustained_combat_ms < config.dungeon_min_sustained_combat_ms:
        return None
    if signals.kill_count <= 0 or signals.kill_count > config.dungeon_max_kills:
        return None
    confidence = 0.62 + min(signals.sustained_combat_ms / 20000.0, 0.2)
    if confidence < config.min_tag_confidence:
        return None
    return _build_tag(
        AlbionEngagementType.DUNGEON,
        confidence,
        (
            f"Dungeon engagement: sustained combat for {signals.sustained_combat_ms}ms "
            f"with {signals.kill_count} kill(s)"
        ),
        metadata={"sustained_combat_ms": signals.sustained_combat_ms},
    )


def score_roaming(signals: ClipEngagementSignals, config: AlbionEngagementConfig) -> AlbionEngagementTag | None:
    if signals.kill_count > config.roaming_max_kills:
        return None
    if signals.bomb_count > 0:
        return None
    confidence = 0.38
    reasons: list[str] = []
    if signals.minimap_count > 0:
        confidence += 0.12
        reasons.append("minimap activity")
    if 0.0 < signals.avg_motion_score <= 0.55:
        confidence += 0.1
        reasons.append("ambient movement")
    if signals.sustained_combat_ms < config.engagement_min_duration_ms:
        confidence += 0.08
        reasons.append("no sustained combat")
    if not reasons:
        return None
    if confidence < config.min_tag_confidence:
        return None
    return _build_tag(
        AlbionEngagementType.ROAMING,
        confidence,
        "Roaming engagement: " + ", ".join(reasons),
        metadata={"minimap_count": signals.minimap_count},
    )


def score_open_world_pvp(signals: ClipEngagementSignals, config: AlbionEngagementConfig) -> AlbionEngagementTag | None:
    if signals.kill_count <= 0:
        return None
    confidence = 0.5 + min(signals.kill_count * 0.06, 0.25)
    if signals.sustained_combat_ms >= config.engagement_min_duration_ms:
        confidence += 0.08
    if confidence < config.min_tag_confidence:
        return None
    return _build_tag(
        AlbionEngagementType.OPEN_WORLD_PVP,
        confidence,
        f"Open-world PvP engagement: {signals.kill_count} kill(s) detected",
        metadata={"kill_count": signals.kill_count},
    )


def classify_engagement_tags(
    signals: ClipEngagementSignals,
    *,
    config: AlbionEngagementConfig,
) -> list[AlbionEngagementTag]:
    candidates = [
        score_zvz(signals, config),
        score_ganking(signals, config),
        score_gathering(signals, config),
        score_dungeon(signals, config),
        score_roaming(signals, config),
        score_open_world_pvp(signals, config),
    ]
    tags = [tag for tag in candidates if tag is not None]
    return sorted(tags, key=lambda item: (-item.confidence, item.engagement_type.value))


def group_tags_into_windows(
    *,
    tags: list[AlbionEngagementTag],
    combat_payload: dict | None,
    timestamps: list[int],
    window_ms: int,
    engagement_min_duration_ms: int,
    source_fingerprint: str,
    config_id: str,
) -> list[AlbionEngagementFrameWindow]:
    fight_ranges: list[tuple[int, int]] = []
    for entry in (combat_payload or {}).get("entries", []):
        if str(entry.get("event_type", "")) != AlbionCombatEventType.FIGHT_START.value:
            continue
        fight_end_ms = entry.get("metadata", {}).get("fight_end_ms")
        if fight_end_ms is None:
            continue
        fight_ranges.append((int(entry.get("timestamp_ms", 0)), int(fight_end_ms)))

    windows: list[AlbionEngagementFrameWindow] = []
    for timestamp_ms in timestamps:
        window_start = timestamp_ms
        window_end = timestamp_ms + window_ms
        combat_ui_active = any(
            window_start <= fight_end and fight_start < window_end
            for fight_start, fight_end in fight_ranges
        ) or any(
            str(entry.get("event_type", "")) == AlbionCombatEventType.KILL.value
            and window_start <= int(entry.get("timestamp_ms", 0)) < window_end
            for entry in (combat_payload or {}).get("entries", [])
        )
        window_tags = tags if combat_ui_active else [
            tag
            for tag in tags
            if tag.engagement_type in {AlbionEngagementType.GATHERING, AlbionEngagementType.ROAMING}
        ]
        windows.append(
            AlbionEngagementFrameWindow(
                window_start_ms=window_start,
                window_end_ms=window_end,
                cache_key=build_window_cache_key(
                    source_fingerprint=source_fingerprint,
                    config_id=config_id,
                    window_start_ms=window_start,
                    window_end_ms=window_end,
                ),
                config_id=config_id,
                combat_ui_active=combat_ui_active or (
                    window_end - window_start >= engagement_min_duration_ms and bool(window_tags)
                ),
                tag_count=len(window_tags),
                tags=window_tags,
            ),
        )
    return windows


def run_albion_engagement_pipeline(
    *,
    source_fingerprint: str,
    duration_ms: int,
    frame_rate: float,
    combat_payload: dict | None,
    bomb_payload: dict | None,
    ui_payload: dict | None,
    albion_ocr_payload: dict | None,
    m3_ocr_payload: dict | None,
    motion_payload: dict | None,
    config_id: str | None = None,
) -> AlbionEngagementAnalysisResult:
    config = get_engagement_config(config_id)
    signals = resolve_clip_signals(
        duration_ms=duration_ms,
        combat_payload=combat_payload,
        bomb_payload=bomb_payload,
        ui_payload=ui_payload,
        albion_ocr_payload=albion_ocr_payload,
        m3_ocr_payload=m3_ocr_payload,
        motion_payload=motion_payload,
        keywords=config.gathering_keywords,
    )
    tags = classify_engagement_tags(signals, config=config)

    timestamps = sample_timestamps_ms(
        duration_ms,
        interval_ms=config.sample_interval_ms,
        max_frames=max(duration_ms // config.sample_interval_ms + 1, 1),
    )
    if not timestamps:
        timestamps = [0]

    frame_windows = group_tags_into_windows(
        tags=tags,
        combat_payload=combat_payload,
        timestamps=timestamps,
        window_ms=config.window_ms,
        engagement_min_duration_ms=config.engagement_min_duration_ms,
        source_fingerprint=source_fingerprint,
        config_id=config.id,
    )

    source_flags = ",".join(
        flag
        for flag, enabled in (
            ("combat", combat_payload is not None),
            ("bomb", bomb_payload is not None),
            ("ui", ui_payload is not None),
            ("albion-ocr", albion_ocr_payload is not None),
            ("m3-ocr", m3_ocr_payload is not None),
            ("motion", motion_payload is not None),
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
    if combat_payload is not None:
        cache_key = f"{cache_key}:combat:{combat_payload.get('cache_key', 'unknown')}"
    if bomb_payload is not None:
        cache_key = f"{cache_key}:bomb:{bomb_payload.get('cache_key', 'unknown')}"

    by_engagement_type = {tag.engagement_type.value: 1 for tag in tags}
    primary = tags[0].engagement_type if tags else None
    signal_model = AlbionEngagementSignals(
        kill_count=signals.kill_count,
        death_count=signals.death_count,
        fight_count=signals.fight_count,
        bomb_count=signals.bomb_count,
        sustained_combat_ms=signals.sustained_combat_ms,
        sustained_ui_ms=signals.sustained_ui_ms,
        party_frame_count=signals.party_frame_count,
        resource_bar_count=signals.resource_bar_count,
        gathering_keyword_hits=signals.gathering_keyword_hits,
        avg_motion_score=round(signals.avg_motion_score, 3),
        max_motion_score=round(signals.max_motion_score, 3),
    )

    return AlbionEngagementAnalysisResult(
        cache_key=cache_key,
        duration_ms=duration_ms,
        frame_rate=frame_rate,
        window_ms=config.window_ms,
        sample_interval_ms=config.sample_interval_ms,
        config_id=config.id,
        summary=AlbionEngagementSummary(
            frames_sampled=len(timestamps),
            window_count=len(frame_windows),
            tag_count=len(tags),
            primary_engagement=primary,
            sustained_combat_ms=signals.sustained_combat_ms,
            config_id=config.id,
            signals=signal_model,
            by_engagement_type=by_engagement_type,
            reused_albion_combat=combat_payload is not None,
            reused_albion_bomb=bomb_payload is not None,
            reused_albion_ui=ui_payload is not None,
            reused_albion_ocr=albion_ocr_payload is not None,
            reused_motion=motion_payload is not None,
        ),
        frame_windows=frame_windows,
        tags=tags,
    )
