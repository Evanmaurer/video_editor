from __future__ import annotations

from dataclasses import dataclass

from montage_backend.analysis.albion.ability.albion_ability_analysis import AlbionAbilityEventType
from montage_backend.analysis.albion.bomb.albion_bomb_analysis import (
    ALBION_BOMB_DETECTOR_VERSION,
    AlbionBombAnalysisResult,
    AlbionBombEvent,
    AlbionBombFrameWindow,
    AlbionBombFusionScores,
    AlbionBombSummary,
)
from montage_backend.analysis.albion.bomb.config import AlbionBombConfig, config_cache_token, get_bomb_config
from montage_backend.analysis.albion.combat.albion_combat_analysis import AlbionCombatEventType
from montage_backend.analysis.albion.combat.pipeline import extract_signals_from_albion_ocr
from montage_backend.analysis.albion.ocr.pipeline import reclassify_m3_ocr_result
from montage_backend.analysis.audio_analysis import AudioEventType
from montage_backend.analysis.ocr_analysis import OcrAnalysisResult, sample_timestamps_ms

DEDUPE_MS = 1500


@dataclass(frozen=True)
class KillMention:
    timestamp_ms: int
    confidence: float
    text: str
    source: str


def build_window_cache_key(
    *,
    source_fingerprint: str,
    config_id: str,
    window_start_ms: int,
    window_end_ms: int,
) -> str:
    return (
        f"{ALBION_BOMB_DETECTOR_VERSION}:{source_fingerprint}:config={config_id}:"
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
        f"{ALBION_BOMB_DETECTOR_VERSION}:{source_fingerprint}:fps={fps_part}:"
        f"config={config_id}:{config_token}:interval={sample_interval_ms}:"
        f"window={window_ms}:sources={source_flags}"
    )


def _normalize_search_text(*parts: str) -> str:
    return " ".join(part.strip().lower() for part in parts if part.strip())


def extract_kills_from_combat_payload(payload: dict) -> list[KillMention]:
    kills: list[KillMention] = []
    for entry in payload.get("entries", []):
        if str(entry.get("event_type", "")) != AlbionCombatEventType.KILL.value:
            continue
        kills.append(
            KillMention(
                timestamp_ms=int(entry.get("timestamp_ms", 0)),
                confidence=float(entry.get("confidence", 0.65)),
                text=str(entry.get("metadata", {}).get("matched_text", entry.get("label", ""))),
                source="albion_combat",
            ),
        )
    return kills


def extract_kills_from_albion_ocr(payload: dict) -> list[KillMention]:
    return [
        KillMention(
            timestamp_ms=signal.timestamp_ms,
            confidence=signal.confidence,
            text=signal.text,
            source=signal.source,
        )
        for signal in extract_signals_from_albion_ocr(payload)
        if signal.event_type == AlbionCombatEventType.KILL
    ]


def extract_kills_from_m3_ocr(
    ocr_result: OcrAnalysisResult | dict,
    *,
    source_fingerprint: str,
    sample_interval_ms: int,
    window_ms: int,
) -> list[KillMention]:
    albion_ocr = reclassify_m3_ocr_result(
        ocr_result,
        source_fingerprint=source_fingerprint,
        window_ms=window_ms,
        sample_interval_ms=sample_interval_ms,
    )
    return extract_kills_from_albion_ocr(albion_ocr.model_dump(mode="json"))


def resolve_kill_mentions(
    *,
    combat_payload: dict | None,
    albion_ocr_payload: dict | None,
    m3_ocr_payload: dict | OcrAnalysisResult | None,
    source_fingerprint: str,
    sample_interval_ms: int,
    window_ms: int,
) -> tuple[list[KillMention], bool, bool]:
    if combat_payload:
        kills = extract_kills_from_combat_payload(combat_payload)
        if kills:
            return kills, True, False
    if albion_ocr_payload:
        return extract_kills_from_albion_ocr(albion_ocr_payload), False, True
    if m3_ocr_payload is not None:
        return (
            extract_kills_from_m3_ocr(
                m3_ocr_payload,
                source_fingerprint=source_fingerprint,
                sample_interval_ms=sample_interval_ms,
                window_ms=window_ms,
            ),
            False,
            False,
        )
    return [], False, False


def find_kill_spike_windows(
    kills: list[KillMention],
    *,
    config: AlbionBombConfig,
) -> list[tuple[int, int, list[KillMention]]]:
    if not kills:
        return []
    sorted_kills = sorted(kills, key=lambda item: item.timestamp_ms)
    candidates: list[tuple[int, int, list[KillMention]]] = []
    seen_ranges: set[tuple[int, int]] = set()

    for index, anchor in enumerate(sorted_kills):
        window_start = anchor.timestamp_ms
        window_end = anchor.timestamp_ms + config.bomb_kill_window_ms
        window_kills = [
            kill
            for kill in sorted_kills
            if window_start <= kill.timestamp_ms <= window_end
        ]
        if len(window_kills) < config.bomb_min_kills:
            continue
        range_key = (window_start, window_end)
        if range_key in seen_ranges:
            continue
        seen_ranges.add(range_key)
        candidates.append((window_start, window_end, window_kills))

    for left in range(len(sorted_kills)):
        for right in range(left + config.bomb_min_kills - 1, len(sorted_kills)):
            window_kills = sorted_kills[left : right + 1]
            span = window_kills[-1].timestamp_ms - window_kills[0].timestamp_ms
            if span > config.bomb_kill_window_ms:
                break
            if len(window_kills) < config.bomb_min_kills:
                continue
            window_start = window_kills[0].timestamp_ms
            window_end = window_kills[-1].timestamp_ms + config.bomb_kill_window_ms
            range_key = (window_start, window_end)
            if range_key in seen_ranges:
                continue
            seen_ranges.add(range_key)
            candidates.append((window_start, window_end, window_kills))
    return candidates


def score_motion_in_window(motion_payload: dict | None, window_start: int, window_end: int) -> float:
    if not motion_payload:
        return 0.0
    scores: list[float] = []
    for window in motion_payload.get("windows", []):
        start_ms = int(window.get("start_ms", 0))
        if window_start <= start_ms < window_end:
            scores.append(float(window.get("motion_score", window.get("motion_intensity", 0.0))))
    return max(scores) if scores else 0.0


def score_audio_in_window(audio_payload: dict | None, window_start: int, window_end: int) -> float:
    if not audio_payload:
        return 0.0
    scores: list[float] = []
    for event in audio_payload.get("events", []):
        timestamp_ms = int(event.get("timestamp_ms", 0))
        if not (window_start <= timestamp_ms < window_end):
            continue
        event_type = str(event.get("event_type", ""))
        value = float(event.get("value", 0.0))
        if event_type == AudioEventType.PEAK.value:
            scores.append(min(1.0, value))
    for index, peak in enumerate(audio_payload.get("peaks", [])):
        timestamp_ms = int(index * audio_payload.get("window_ms", 1000))
        if window_start <= timestamp_ms < window_end:
            scores.append(min(1.0, float(peak)))
    return max(scores) if scores else 0.0


def score_abilities_in_window(ability_payload: dict | None, window_start: int, window_end: int) -> float:
    if not ability_payload:
        return 0.0
    score = 0.0
    for event in ability_payload.get("events", []):
        timestamp_ms = int(event.get("timestamp_ms", 0))
        if not (window_start <= timestamp_ms < window_end):
            continue
        event_type = str(event.get("event_type", ""))
        if event_type == AlbionAbilityEventType.ULTIMATE_ACTIVATION.value:
            score += 0.6
        elif event_type == AlbionAbilityEventType.ACTIVATION.value:
            score += 0.25
    return min(1.0, score)


def fuse_bomb_confidence(
    *,
    kill_count: int,
    config: AlbionBombConfig,
    motion_raw: float,
    audio_raw: float,
    ability_raw: float,
) -> tuple[float, AlbionBombFusionScores]:
    ocr_score = min(1.0, kill_count / config.bomb_min_kills)
    motion_score = min(1.0, motion_raw / config.motion_threshold) if motion_raw > 0 else 0.0
    audio_score = min(1.0, audio_raw / config.audio_peak_threshold) if audio_raw > 0 else 0.0
    ability_score = ability_raw

    weight_total = config.ocr_weight + config.motion_weight + config.audio_weight + config.ability_weight
    if weight_total <= 0:
        weight_total = 1.0

    confidence = (
        ocr_score * config.ocr_weight
        + motion_score * config.motion_weight
        + audio_score * config.audio_weight
        + ability_score * config.ability_weight
    ) / weight_total
    fusion = AlbionBombFusionScores(
        ocr_score=round(ocr_score, 3),
        motion_score=round(motion_score, 3),
        audio_score=round(audio_score, 3),
        ability_score=round(ability_score, 3),
    )
    return round(min(max(confidence, 0.0), 1.0), 3), fusion


def build_bomb_events(
    candidates: list[tuple[int, int, list[KillMention]]],
    *,
    config: AlbionBombConfig,
    motion_payload: dict | None,
    audio_payload: dict | None,
    ability_payload: dict | None,
) -> list[AlbionBombEvent]:
    events: list[AlbionBombEvent] = []
    for index, (window_start, window_end, window_kills) in enumerate(candidates):
        kill_count = len(window_kills)
        center_ms = window_kills[len(window_kills) // 2].timestamp_ms
        motion_raw = score_motion_in_window(motion_payload, window_start, window_end)
        audio_raw = score_audio_in_window(audio_payload, window_start, window_end)
        ability_raw = score_abilities_in_window(ability_payload, window_start, window_end)
        confidence, fusion = fuse_bomb_confidence(
            kill_count=kill_count,
            config=config,
            motion_raw=motion_raw,
            audio_raw=audio_raw,
            ability_raw=ability_raw,
        )
        if kill_count < config.bomb_min_kills:
            continue
        kill_texts = [kill.text for kill in window_kills if kill.text]
        reasoning_parts = [f"{kill_count} kills in {config.bomb_kill_window_ms}ms"]
        if fusion.motion_score > 0:
            reasoning_parts.append("motion spike")
        if fusion.audio_score > 0:
            reasoning_parts.append("audio peak")
        if fusion.ability_score > 0:
            reasoning_parts.append("ability activity")
        reasoning = "Bomb detected: " + ", ".join(reasoning_parts)
        events.append(
            AlbionBombEvent(
                event_id=f"bomb:{center_ms}:{index}",
                timestamp_ms=center_ms,
                window_start_ms=window_start,
                window_end_ms=window_end,
                confidence=confidence,
                bomb_score=round(confidence * 10.0, 1),
                kill_count=kill_count,
                fusion=fusion,
                search_text=_normalize_search_text("bomb", reasoning, *kill_texts),
                reasoning=reasoning,
                metadata={
                    "kill_texts": kill_texts,
                    "sources": sorted({kill.source for kill in window_kills}),
                },
            ),
        )
    return dedupe_bomb_events(events)


def dedupe_bomb_events(events: list[AlbionBombEvent]) -> list[AlbionBombEvent]:
    if not events:
        return []
    sorted_events = sorted(events, key=lambda item: (-item.confidence, item.timestamp_ms))
    kept: list[AlbionBombEvent] = []
    for event in sorted_events:
        if any(abs(event.timestamp_ms - existing.timestamp_ms) < DEDUPE_MS for existing in kept):
            continue
        kept.append(event)
    return sorted(kept, key=lambda item: item.timestamp_ms)


def group_events_into_windows(
    events: list[AlbionBombEvent],
    *,
    timestamps: list[int],
    window_ms: int,
    source_fingerprint: str,
    config_id: str,
) -> list[AlbionBombFrameWindow]:
    windows: list[AlbionBombFrameWindow] = []
    for timestamp_ms in timestamps:
        window_start = timestamp_ms
        window_end = timestamp_ms + window_ms
        window_events = [
            event
            for event in events
            if window_start <= event.timestamp_ms < window_end
            or (window_start <= event.window_start_ms < window_end)
        ]
        max_score = max((event.bomb_score for event in window_events), default=0.0)
        windows.append(
            AlbionBombFrameWindow(
                window_start_ms=window_start,
                window_end_ms=window_end,
                cache_key=build_window_cache_key(
                    source_fingerprint=source_fingerprint,
                    config_id=config_id,
                    window_start_ms=window_start,
                    window_end_ms=window_end,
                ),
                config_id=config_id,
                bomb_count=len(window_events),
                max_bomb_score=max_score,
                events=window_events,
            ),
        )
    return windows


def run_albion_bomb_pipeline(
    *,
    source_fingerprint: str,
    duration_ms: int,
    frame_rate: float,
    combat_payload: dict | None,
    albion_ocr_payload: dict | None,
    m3_ocr_payload: dict | OcrAnalysisResult | None,
    albion_ability_payload: dict | None,
    motion_payload: dict | None,
    audio_payload: dict | None,
    config_id: str | None = None,
) -> AlbionBombAnalysisResult:
    config = get_bomb_config(config_id)
    kills, reused_combat, reused_albion_ocr = resolve_kill_mentions(
        combat_payload=combat_payload,
        albion_ocr_payload=albion_ocr_payload,
        m3_ocr_payload=m3_ocr_payload,
        source_fingerprint=source_fingerprint,
        sample_interval_ms=config.sample_interval_ms,
        window_ms=config.window_ms,
    )
    candidates = find_kill_spike_windows(kills, config=config)
    events = build_bomb_events(
        candidates,
        config=config,
        motion_payload=motion_payload,
        audio_payload=audio_payload,
        ability_payload=albion_ability_payload,
    )

    timestamps = sample_timestamps_ms(
        duration_ms,
        interval_ms=config.sample_interval_ms,
        max_frames=max(
            len(kills),
            len(events),
            duration_ms // config.sample_interval_ms + 1,
            1,
        ),
    )
    if not timestamps:
        timestamps = [0]

    frame_windows = group_events_into_windows(
        events,
        timestamps=timestamps,
        window_ms=config.window_ms,
        source_fingerprint=source_fingerprint,
        config_id=config.id,
    )

    source_flags = ",".join(
        flag
        for flag, enabled in (
            ("combat", reused_combat),
            ("albion-ocr", reused_albion_ocr),
            ("m3-ocr", bool(kills) and not reused_combat and not reused_albion_ocr),
            ("ability", albion_ability_payload is not None),
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
    if combat_payload is not None and reused_combat:
        cache_key = f"{cache_key}:combat:{combat_payload.get('cache_key', 'unknown')}"

    top_bomb_score = max((event.bomb_score for event in events), default=0.0)
    return AlbionBombAnalysisResult(
        cache_key=cache_key,
        duration_ms=duration_ms,
        frame_rate=frame_rate,
        window_ms=config.window_ms,
        sample_interval_ms=config.sample_interval_ms,
        config_id=config.id,
        summary=AlbionBombSummary(
            frames_sampled=len(timestamps),
            window_count=len(frame_windows),
            bomb_count=len(events),
            top_bomb_score=top_bomb_score,
            total_kill_count=len(kills),
            config_id=config.id,
            by_source={
                "ocr": bool(kills),
                "motion": motion_payload is not None,
                "audio": audio_payload is not None,
                "ability": albion_ability_payload is not None,
            },
            reused_albion_combat=reused_combat,
            reused_albion_ocr=reused_albion_ocr,
            reused_albion_ability=albion_ability_payload is not None,
            reused_motion=motion_payload is not None,
            reused_audio=audio_payload is not None,
        ),
        frame_windows=frame_windows,
        events=events,
    )
