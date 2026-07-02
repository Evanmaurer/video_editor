from __future__ import annotations

from dataclasses import dataclass

from montage_backend.analysis.albion.ability.albion_ability_analysis import AlbionAbilityEventType
from montage_backend.analysis.albion.combat.albion_combat_analysis import (
    ALBION_COMBAT_DETECTOR_VERSION,
    AlbionCombatAnalysisResult,
    AlbionCombatEventType,
    AlbionCombatFrameWindow,
    AlbionCombatSummary,
    AlbionCombatTimelineEntry,
)
from montage_backend.analysis.albion.combat.config import AlbionCombatConfig, config_cache_token, get_combat_config
from montage_backend.analysis.albion.ocr.albion_ocr_analysis import AlbionOcrCategory
from montage_backend.analysis.albion.ocr.pipeline import reclassify_m3_ocr_result
from montage_backend.analysis.ocr_analysis import OcrAnalysisResult, sample_timestamps_ms

DEDUPE_MS = 800


@dataclass(frozen=True)
class CombatSignal:
    event_type: AlbionCombatEventType
    timestamp_ms: int
    confidence: float
    text: str
    source: str
    metadata: dict


def build_window_cache_key(
    *,
    source_fingerprint: str,
    config_id: str,
    window_start_ms: int,
    window_end_ms: int,
) -> str:
    return (
        f"{ALBION_COMBAT_DETECTOR_VERSION}:{source_fingerprint}:config={config_id}:"
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
        f"{ALBION_COMBAT_DETECTOR_VERSION}:{source_fingerprint}:fps={fps_part}:"
        f"config={config_id}:{config_token}:interval={sample_interval_ms}:"
        f"window={window_ms}:sources={source_flags}"
    )


def _normalize_search_text(*parts: str) -> str:
    return " ".join(part.strip().lower() for part in parts if part.strip())


def _build_entry_id(event_type: AlbionCombatEventType, timestamp_ms: int, index: int) -> str:
    return f"{event_type.value}:{timestamp_ms}:{index}"


def _build_entry_label(event_type: AlbionCombatEventType, text: str) -> str:
    if event_type == AlbionCombatEventType.KILL:
        return f"Kill: {text}" if text else "Kill"
    if event_type == AlbionCombatEventType.DEATH:
        return f"Death: {text}" if text else "Death"
    if event_type == AlbionCombatEventType.FIGHT_START:
        return "Fight started"
    if event_type == AlbionCombatEventType.FIGHT_END:
        return "Fight ended"
    if event_type == AlbionCombatEventType.RETREAT:
        return "Retreat"
    return text or event_type.value


def extract_signals_from_albion_ocr(payload: dict) -> list[CombatSignal]:
    signals: list[CombatSignal] = []
    for detection in payload.get("detections", []):
        category = str(detection.get("category", ""))
        text = str(detection.get("text", "")).strip()
        if not text:
            continue
        timestamp_ms = int(detection.get("timestamp_ms", 0))
        confidence = float(detection.get("confidence", 0.65))
        metadata = dict(detection.get("metadata", {}))
        if category in {AlbionOcrCategory.KILL_MESSAGE.value, "kill_message"}:
            signals.append(
                CombatSignal(
                    event_type=AlbionCombatEventType.KILL,
                    timestamp_ms=timestamp_ms,
                    confidence=confidence,
                    text=text,
                    source="albion_ocr",
                    metadata=metadata,
                ),
            )
        elif category in {AlbionOcrCategory.DEATH_MESSAGE.value, "death_message"}:
            signals.append(
                CombatSignal(
                    event_type=AlbionCombatEventType.DEATH,
                    timestamp_ms=timestamp_ms,
                    confidence=confidence,
                    text=text,
                    source="albion_ocr",
                    metadata=metadata,
                ),
            )
    return signals


def extract_signals_from_m3_ocr(
    ocr_result: OcrAnalysisResult | dict,
    *,
    source_fingerprint: str,
    sample_interval_ms: int,
    window_ms: int,
) -> list[CombatSignal]:
    albion_ocr = reclassify_m3_ocr_result(
        ocr_result,
        source_fingerprint=source_fingerprint,
        window_ms=window_ms,
        sample_interval_ms=sample_interval_ms,
    )
    return extract_signals_from_albion_ocr(albion_ocr.model_dump(mode="json"))


def extract_activity_points_from_ocr(payload: dict) -> dict[int, float]:
    points: dict[int, float] = {}
    for detection in payload.get("detections", []):
        category = str(detection.get("category", ""))
        timestamp_ms = int(detection.get("timestamp_ms", 0))
        weight = 0.0
        if category in {AlbionOcrCategory.KILL_MESSAGE.value, "kill_message"}:
            weight = 0.45
        elif category in {AlbionOcrCategory.DEATH_MESSAGE.value, "death_message"}:
            weight = 0.5
        elif category in {AlbionOcrCategory.DAMAGE_NUMBER.value, "damage_number"}:
            weight = 0.15
        elif category in {AlbionOcrCategory.HEALING_NUMBER.value, "healing_number"}:
            weight = 0.1
        if weight > 0:
            points[timestamp_ms] = min(1.0, points.get(timestamp_ms, 0.0) + weight)
    return points


def extract_activity_points_from_ability(payload: dict) -> dict[int, float]:
    points: dict[int, float] = {}
    for event in payload.get("events", []):
        event_type = str(event.get("event_type", ""))
        if event_type not in {
            AlbionAbilityEventType.ACTIVATION.value,
            AlbionAbilityEventType.ULTIMATE_ACTIVATION.value,
        }:
            continue
        timestamp_ms = int(event.get("timestamp_ms", 0))
        points[timestamp_ms] = min(1.0, points.get(timestamp_ms, 0.0) + 0.25)
    return points


def extract_activity_points_from_ui(payload: dict) -> dict[int, float]:
    points: dict[int, float] = {}
    for detection in payload.get("detections", []):
        element_type = str(detection.get("element_type", detection.get("label", "")))
        if element_type != "health_bar":
            continue
        timestamp_ms = int(detection.get("timestamp_ms", 0))
        confidence = float(detection.get("confidence", 0.65))
        points[timestamp_ms] = min(1.0, max(points.get(timestamp_ms, 0.0), confidence * 0.35))
    for window in payload.get("frame_windows", []):
        for detection in window.get("detections", []):
            element_type = str(detection.get("element_type", detection.get("label", "")))
            if element_type != "health_bar":
                continue
            timestamp_ms = int(detection.get("timestamp_ms", window.get("window_start_ms", 0)))
            confidence = float(detection.get("confidence", 0.65))
            points[timestamp_ms] = min(1.0, max(points.get(timestamp_ms, 0.0), confidence * 0.35))
    return points


def extract_activity_points_from_motion(payload: dict) -> dict[int, float]:
    points: dict[int, float] = {}
    for window in payload.get("windows", []):
        timestamp_ms = int(window.get("start_ms", 0))
        motion_score = float(window.get("motion_score", window.get("motion_intensity", 0.0)))
        if motion_score > 0:
            points[timestamp_ms] = min(1.0, motion_score * 0.4)
    return points


def merge_activity_points(*point_maps: dict[int, float]) -> dict[int, float]:
    merged: dict[int, float] = {}
    for point_map in point_maps:
        for timestamp_ms, score in point_map.items():
            merged[timestamp_ms] = min(1.0, merged.get(timestamp_ms, 0.0) + score)
    return merged


def build_window_activity_scores(
    timestamps: list[int],
    *,
    window_ms: int,
    activity_points: dict[int, float],
) -> list[tuple[int, int, float]]:
    windows: list[tuple[int, int, float]] = []
    for timestamp_ms in timestamps:
        window_start = timestamp_ms
        window_end = timestamp_ms + window_ms
        scores = [
            score
            for point_ms, score in activity_points.items()
            if window_start <= point_ms < window_end
        ]
        activity_score = min(1.0, sum(scores)) if scores else 0.0
        windows.append((window_start, window_end, round(activity_score, 3)))
    return windows


def dedupe_signals(signals: list[CombatSignal]) -> list[CombatSignal]:
    deduped: list[CombatSignal] = []
    last_seen: dict[tuple[str, str], int] = {}
    for signal in sorted(signals, key=lambda item: (item.timestamp_ms, item.event_type.value)):
        key = (signal.event_type.value, signal.text.lower())
        previous = last_seen.get(key)
        if previous is not None and signal.timestamp_ms - previous < DEDUPE_MS:
            continue
        deduped.append(signal)
        last_seen[key] = signal.timestamp_ms
    return deduped


def signals_to_entries(
    signals: list[CombatSignal],
    *,
    window_ms: int,
) -> list[AlbionCombatTimelineEntry]:
    entries: list[AlbionCombatTimelineEntry] = []
    for index, signal in enumerate(signals):
        label = _build_entry_label(signal.event_type, signal.text)
        entries.append(
            AlbionCombatTimelineEntry(
                entry_id=_build_entry_id(signal.event_type, signal.timestamp_ms, index),
                event_type=signal.event_type,
                timestamp_ms=signal.timestamp_ms,
                window_start_ms=signal.timestamp_ms,
                window_end_ms=signal.timestamp_ms + window_ms,
                confidence=round(min(max(signal.confidence, 0.0), 1.0), 3),
                label=label,
                search_text=_normalize_search_text(signal.event_type.value, label, signal.text, signal.source),
                metadata={
                    "matched_text": signal.text,
                    "source": signal.source,
                    **signal.metadata,
                },
            ),
        )
    return entries


def segment_fight_boundaries(
    window_activity: list[tuple[int, int, float]],
    *,
    config: AlbionCombatConfig,
) -> list[tuple[int, int]]:
    fights: list[tuple[int, int]] = []
    active_start: int | None = None
    active_end: int | None = None
    last_active_end = 0

    for window_start, window_end, activity_score in window_activity:
        if activity_score >= config.fight_activity_threshold:
            if active_start is None:
                active_start = window_start
            active_end = window_end
            last_active_end = window_end
            continue
        if active_start is not None and active_end is not None:
            gap = window_start - last_active_end
            if gap >= config.fight_gap_ms:
                if active_end - active_start >= config.fight_min_duration_ms:
                    fights.append((active_start, active_end))
                active_start = None
                active_end = None

    if active_start is not None and active_end is not None:
        if active_end - active_start >= config.fight_min_duration_ms:
            fights.append((active_start, active_end))
    return fights


def build_fight_and_retreat_entries(
    fights: list[tuple[int, int]],
    *,
    kill_death_entries: list[AlbionCombatTimelineEntry],
    config: AlbionCombatConfig,
    window_ms: int,
    start_index: int,
) -> list[AlbionCombatTimelineEntry]:
    entries: list[AlbionCombatTimelineEntry] = []
    index = start_index
    for fight_start, fight_end in fights:
        entries.append(
            AlbionCombatTimelineEntry(
                entry_id=_build_entry_id(AlbionCombatEventType.FIGHT_START, fight_start, index),
                event_type=AlbionCombatEventType.FIGHT_START,
                timestamp_ms=fight_start,
                window_start_ms=fight_start,
                window_end_ms=fight_start + window_ms,
                confidence=0.78,
                label=_build_entry_label(AlbionCombatEventType.FIGHT_START, ""),
                search_text=_normalize_search_text("fight_start", "fight started", "combat"),
                metadata={"fight_end_ms": fight_end},
            ),
        )
        index += 1
        entries.append(
            AlbionCombatTimelineEntry(
                entry_id=_build_entry_id(AlbionCombatEventType.FIGHT_END, fight_end, index),
                event_type=AlbionCombatEventType.FIGHT_END,
                timestamp_ms=fight_end,
                window_start_ms=max(0, fight_end - window_ms),
                window_end_ms=fight_end,
                confidence=0.76,
                label=_build_entry_label(AlbionCombatEventType.FIGHT_END, ""),
                search_text=_normalize_search_text("fight_end", "fight ended", "combat"),
                metadata={"fight_start_ms": fight_start},
            ),
        )
        index += 1

        deaths_in_fight = [
            entry
            for entry in kill_death_entries
            if entry.event_type == AlbionCombatEventType.DEATH
            and fight_start <= entry.timestamp_ms <= fight_end
        ]
        if not deaths_in_fight:
            retreat_ms = min(fight_end + config.retreat_gap_ms, fight_end + window_ms)
            entries.append(
                AlbionCombatTimelineEntry(
                    entry_id=_build_entry_id(AlbionCombatEventType.RETREAT, retreat_ms, index),
                    event_type=AlbionCombatEventType.RETREAT,
                    timestamp_ms=retreat_ms,
                    window_start_ms=fight_end,
                    window_end_ms=retreat_ms + window_ms,
                    confidence=0.7,
                    label=_build_entry_label(AlbionCombatEventType.RETREAT, ""),
                    search_text=_normalize_search_text("retreat", "disengage", "combat"),
                    metadata={"fight_start_ms": fight_start, "fight_end_ms": fight_end},
                ),
            )
            index += 1
    return entries


def group_entries_into_windows(
    entries: list[AlbionCombatTimelineEntry],
    *,
    timestamps: list[int],
    window_ms: int,
    window_activity: list[tuple[int, int, float]],
    source_fingerprint: str,
    config_id: str,
) -> list[AlbionCombatFrameWindow]:
    activity_by_start = {start: score for start, _, score in window_activity}
    windows: list[AlbionCombatFrameWindow] = []
    for timestamp_ms in timestamps:
        window_start = timestamp_ms
        window_end = timestamp_ms + window_ms
        window_entries = [
            entry
            for entry in entries
            if window_start <= entry.timestamp_ms < window_end
            or (
                entry.event_type in {AlbionCombatEventType.FIGHT_END, AlbionCombatEventType.RETREAT}
                and window_start <= entry.timestamp_ms <= window_end
            )
        ]
        windows.append(
            AlbionCombatFrameWindow(
                window_start_ms=window_start,
                window_end_ms=window_end,
                cache_key=build_window_cache_key(
                    source_fingerprint=source_fingerprint,
                    config_id=config_id,
                    window_start_ms=window_start,
                    window_end_ms=window_end,
                ),
                config_id=config_id,
                activity_score=activity_by_start.get(window_start, 0.0),
                entry_count=len(window_entries),
                entries=window_entries,
            ),
        )
    return windows


def build_event_type_counts(entries: list[AlbionCombatTimelineEntry]) -> dict[str, int]:
    counts = {event_type.value: 0 for event_type in AlbionCombatEventType}
    for entry in entries:
        counts[entry.event_type.value] += 1
    return counts


def resolve_ocr_payload(
    *,
    albion_ocr_payload: dict | None,
    m3_ocr_payload: dict | OcrAnalysisResult | None,
    source_fingerprint: str,
    sample_interval_ms: int,
    window_ms: int,
) -> tuple[dict | None, bool]:
    if albion_ocr_payload:
        return albion_ocr_payload, True
    if m3_ocr_payload is not None:
        albion_ocr = reclassify_m3_ocr_result(
            m3_ocr_payload,
            source_fingerprint=source_fingerprint,
            window_ms=window_ms,
            sample_interval_ms=sample_interval_ms,
        )
        return albion_ocr.model_dump(mode="json"), False
    return None, False


def run_albion_combat_pipeline(
    *,
    source_fingerprint: str,
    duration_ms: int,
    frame_rate: float,
    albion_ocr_payload: dict | None,
    m3_ocr_payload: dict | OcrAnalysisResult | None,
    albion_ability_payload: dict | None,
    albion_ui_payload: dict | None,
    motion_payload: dict | None,
    config_id: str | None = None,
) -> AlbionCombatAnalysisResult:
    config = get_combat_config(config_id)
    ocr_payload, reused_albion_ocr = resolve_ocr_payload(
        albion_ocr_payload=albion_ocr_payload,
        m3_ocr_payload=m3_ocr_payload,
        source_fingerprint=source_fingerprint,
        sample_interval_ms=config.sample_interval_ms,
        window_ms=config.window_ms,
    )

    ocr_signals: list[CombatSignal] = []
    if ocr_payload is not None:
        ocr_signals = extract_signals_from_albion_ocr(ocr_payload)
    ocr_signals = dedupe_signals(ocr_signals)
    kill_death_entries = signals_to_entries(ocr_signals, window_ms=config.window_ms)

    activity_points = merge_activity_points(
        extract_activity_points_from_ocr(ocr_payload or {}),
        extract_activity_points_from_ability(albion_ability_payload or {}),
        extract_activity_points_from_ui(albion_ui_payload or {}),
        extract_activity_points_from_motion(motion_payload or {}),
    )

    timestamps = sample_timestamps_ms(
        duration_ms,
        interval_ms=config.sample_interval_ms,
        max_frames=max(
            len(activity_points),
            len(kill_death_entries),
            duration_ms // config.sample_interval_ms + 1,
            1,
        ),
    )
    if not timestamps:
        timestamps = [0]

    window_activity = build_window_activity_scores(
        timestamps,
        window_ms=config.window_ms,
        activity_points=activity_points,
    )
    fights = segment_fight_boundaries(window_activity, config=config)
    fight_entries = build_fight_and_retreat_entries(
        fights,
        kill_death_entries=kill_death_entries,
        config=config,
        window_ms=config.window_ms,
        start_index=len(kill_death_entries),
    )

    entries = sorted(
        [*kill_death_entries, *fight_entries],
        key=lambda item: (item.timestamp_ms, item.event_type.value),
    )
    frame_windows = group_entries_into_windows(
        entries,
        timestamps=timestamps,
        window_ms=config.window_ms,
        window_activity=window_activity,
        source_fingerprint=source_fingerprint,
        config_id=config.id,
    )

    source_flags = ",".join(
        flag
        for flag, enabled in (
            ("albion-ocr", reused_albion_ocr),
            ("m3-ocr", ocr_payload is not None and not reused_albion_ocr),
            ("ability", albion_ability_payload is not None),
            ("ui", albion_ui_payload is not None),
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
    if reused_albion_ocr and albion_ocr_payload is not None:
        cache_key = f"{cache_key}:ocr:{albion_ocr_payload.get('cache_key', 'unknown')}"

    by_event_type = build_event_type_counts(entries)
    return AlbionCombatAnalysisResult(
        cache_key=cache_key,
        duration_ms=duration_ms,
        frame_rate=frame_rate,
        window_ms=config.window_ms,
        sample_interval_ms=config.sample_interval_ms,
        config_id=config.id,
        summary=AlbionCombatSummary(
            frames_sampled=len(timestamps),
            window_count=len(frame_windows),
            entry_count=len(entries),
            fight_count=by_event_type.get(AlbionCombatEventType.FIGHT_START.value, 0),
            kill_count=by_event_type.get(AlbionCombatEventType.KILL.value, 0),
            death_count=by_event_type.get(AlbionCombatEventType.DEATH.value, 0),
            retreat_count=by_event_type.get(AlbionCombatEventType.RETREAT.value, 0),
            config_id=config.id,
            by_event_type=by_event_type,
            reused_albion_ocr=reused_albion_ocr,
            reused_albion_ability=albion_ability_payload is not None,
            reused_albion_ui=albion_ui_payload is not None,
            reused_motion=motion_payload is not None,
        ),
        frame_windows=frame_windows,
        entries=entries,
    )
