from __future__ import annotations

from dataclasses import dataclass

from montage_backend.analysis.albion.ability.albion_ability_analysis import (
    ALBION_ABILITY_DETECTOR_VERSION,
    AlbionAbilityAnalysisResult,
    AlbionAbilityEvent,
    AlbionAbilityEventType,
    AlbionAbilityFrameWindow,
    AlbionAbilitySummary,
)
from montage_backend.analysis.albion.ability.catalog import (
    AlbionAbilityCatalog,
    AlbionAbilityDefinition,
    catalog_cache_token,
    get_catalog,
)
from montage_backend.analysis.albion.ocr.albion_ocr_analysis import AlbionOcrCategory
from montage_backend.analysis.albion.ocr.classifier import normalize_albion_text
from montage_backend.analysis.albion.ocr.pipeline import reclassify_m3_ocr_result
from montage_backend.analysis.ocr_analysis import OcrAnalysisResult, sample_timestamps_ms

DEDUPE_MS = 800


@dataclass(frozen=True)
class AbilityMention:
    text: str
    timestamp_ms: int
    confidence: float
    source: str


def build_window_cache_key(
    *,
    source_fingerprint: str,
    catalog_id: str,
    window_start_ms: int,
    window_end_ms: int,
) -> str:
    return (
        f"{ALBION_ABILITY_DETECTOR_VERSION}:{source_fingerprint}:catalog={catalog_id}:"
        f"window={window_start_ms}-{window_end_ms}"
    )


def build_detector_cache_key(
    source_fingerprint: str,
    *,
    frame_rate: float | None,
    catalog_id: str,
    catalog_token: str,
    sample_interval_ms: int,
    window_ms: int,
    reused_albion_ocr: bool,
) -> str:
    fps_part = f"{frame_rate:.3f}" if frame_rate is not None else "unknown"
    source = "albion-ocr" if reused_albion_ocr else "m3-ocr"
    return (
        f"{ALBION_ABILITY_DETECTOR_VERSION}:{source_fingerprint}:fps={fps_part}:"
        f"catalog={catalog_id}:{catalog_token}:interval={sample_interval_ms}:"
        f"window={window_ms}:source={source}"
    )


def _normalize_match_text(text: str) -> str:
    return normalize_albion_text(text)


def match_ability_definition(text: str, catalog: AlbionAbilityCatalog) -> AlbionAbilityDefinition | None:
    normalized = _normalize_match_text(text)
    if not normalized:
        return None

    best: AlbionAbilityDefinition | None = None
    best_score = 0
    for definition in catalog.abilities:
        for alias in definition.aliases:
            if normalized == alias:
                return definition
            if len(alias) >= 4 and alias in normalized:
                score = len(alias)
                if score > best_score:
                    best = definition
                    best_score = score
    return best


def extract_mentions_from_albion_ocr(payload: dict) -> list[AbilityMention]:
    mentions: list[AbilityMention] = []
    for detection in payload.get("detections", []):
        category = str(detection.get("category", ""))
        text = str(detection.get("text", "")).strip()
        if not text:
            continue
        if category == AlbionOcrCategory.ABILITY_NAME.value or category == "ability_name":
            mentions.append(
                AbilityMention(
                    text=text,
                    timestamp_ms=int(detection.get("timestamp_ms", 0)),
                    confidence=float(detection.get("confidence", 0.65)),
                    source="albion_ocr",
                ),
            )
    return mentions


def extract_mentions_from_m3_ocr(
    ocr_result: OcrAnalysisResult | dict,
    *,
    source_fingerprint: str,
    sample_interval_ms: int,
    window_ms: int,
) -> list[AbilityMention]:
    albion_ocr = reclassify_m3_ocr_result(
        ocr_result,
        source_fingerprint=source_fingerprint,
        window_ms=window_ms,
        sample_interval_ms=sample_interval_ms,
    )
    return extract_mentions_from_albion_ocr(albion_ocr.model_dump(mode="json"))


def resolve_ability_mentions(
    *,
    albion_ocr_payload: dict | None,
    m3_ocr_payload: dict | OcrAnalysisResult | None,
    source_fingerprint: str,
    sample_interval_ms: int,
    window_ms: int,
) -> tuple[list[AbilityMention], bool]:
    if albion_ocr_payload:
        return extract_mentions_from_albion_ocr(albion_ocr_payload), True
    if m3_ocr_payload is not None:
        return (
            extract_mentions_from_m3_ocr(
                m3_ocr_payload,
                source_fingerprint=source_fingerprint,
                sample_interval_ms=sample_interval_ms,
                window_ms=window_ms,
            ),
            False,
        )
    return [], False


def build_ability_events(
    mentions: list[AbilityMention],
    *,
    catalog: AlbionAbilityCatalog,
    window_ms: int,
) -> list[AlbionAbilityEvent]:
    events: list[AlbionAbilityEvent] = []
    last_activation_ms: dict[str, int] = {}
    last_event_ms: dict[str, int] = {}

    for mention in sorted(mentions, key=lambda item: item.timestamp_ms):
        definition = match_ability_definition(mention.text, catalog)
        if definition is None:
            continue

        timestamp_ms = mention.timestamp_ms
        previous_activation = last_activation_ms.get(definition.id)
        previous_event = last_event_ms.get(definition.id)
        if previous_event is not None and timestamp_ms - previous_event < DEDUPE_MS:
            continue
        if previous_activation is not None and timestamp_ms - previous_activation < definition.cooldown_ms:
            continue

        window_start = timestamp_ms
        window_end = timestamp_ms + window_ms
        event_type = (
            AlbionAbilityEventType.ULTIMATE_ACTIVATION
            if definition.is_ultimate
            else AlbionAbilityEventType.ACTIVATION
        )
        events.append(
            AlbionAbilityEvent(
                ability_id=definition.id,
                ability_name=definition.name,
                event_type=event_type,
                timestamp_ms=timestamp_ms,
                window_start_ms=window_start,
                window_end_ms=window_end,
                confidence=round(min(max(mention.confidence, 0.0), 1.0), 3),
                is_ultimate=definition.is_ultimate,
                cooldown_ms=definition.cooldown_ms,
                metadata={
                    "matched_text": mention.text,
                    "source": mention.source,
                    "category": definition.category,
                },
            ),
        )
        events.append(
            AlbionAbilityEvent(
                ability_id=definition.id,
                ability_name=definition.name,
                event_type=AlbionAbilityEventType.COOLDOWN_START,
                timestamp_ms=timestamp_ms,
                window_start_ms=window_start,
                window_end_ms=window_end,
                confidence=round(min(max(mention.confidence, 0.0), 1.0), 3),
                is_ultimate=definition.is_ultimate,
                cooldown_ms=definition.cooldown_ms,
                metadata={"matched_text": mention.text, "source": mention.source},
            ),
        )
        ready_ms = timestamp_ms + definition.cooldown_ms
        events.append(
            AlbionAbilityEvent(
                ability_id=definition.id,
                ability_name=definition.name,
                event_type=AlbionAbilityEventType.COOLDOWN_READY,
                timestamp_ms=ready_ms,
                window_start_ms=ready_ms,
                window_end_ms=ready_ms + window_ms,
                confidence=round(min(max(mention.confidence * 0.9, 0.0), 1.0), 3),
                is_ultimate=definition.is_ultimate,
                cooldown_ms=definition.cooldown_ms,
                metadata={"projected": True, "source": mention.source},
            ),
        )
        last_activation_ms[definition.id] = timestamp_ms
        last_event_ms[definition.id] = timestamp_ms

    return sorted(events, key=lambda item: (item.timestamp_ms, item.ability_id, item.event_type.value))


def build_event_type_counts(events: list[AlbionAbilityEvent]) -> dict[str, int]:
    counts = {event_type.value: 0 for event_type in AlbionAbilityEventType}
    for event in events:
        counts[event.event_type.value] += 1
    return counts


def build_ability_counts(events: list[AlbionAbilityEvent]) -> dict[str, int]:
    counts: dict[str, int] = {}
    for event in events:
        if event.event_type not in {
            AlbionAbilityEventType.ACTIVATION,
            AlbionAbilityEventType.ULTIMATE_ACTIVATION,
        }:
            continue
        counts[event.ability_id] = counts.get(event.ability_id, 0) + 1
    return counts


def group_events_into_windows(
    events: list[AlbionAbilityEvent],
    *,
    timestamps: list[int],
    window_ms: int,
    source_fingerprint: str,
    catalog_id: str,
) -> list[AlbionAbilityFrameWindow]:
    windows: list[AlbionAbilityFrameWindow] = []
    for timestamp_ms in timestamps:
        window_start = timestamp_ms
        window_end = timestamp_ms + window_ms
        window_events = [
            event
            for event in events
            if window_start <= event.timestamp_ms < window_end
            or (
                event.event_type == AlbionAbilityEventType.COOLDOWN_READY
                and window_start <= event.timestamp_ms < window_end
            )
        ]
        windows.append(
            AlbionAbilityFrameWindow(
                window_start_ms=window_start,
                window_end_ms=window_end,
                cache_key=build_window_cache_key(
                    source_fingerprint=source_fingerprint,
                    catalog_id=catalog_id,
                    window_start_ms=window_start,
                    window_end_ms=window_end,
                ),
                catalog_id=catalog_id,
                event_count=len(window_events),
                events=window_events,
            ),
        )
    return windows


def run_albion_ability_pipeline(
    *,
    source_fingerprint: str,
    duration_ms: int,
    frame_rate: float,
    sample_interval_ms: int,
    window_ms: int,
    albion_ocr_payload: dict | None,
    m3_ocr_payload: dict | OcrAnalysisResult | None,
    catalog_id: str | None = None,
) -> AlbionAbilityAnalysisResult:
    catalog = get_catalog(catalog_id)
    mentions, reused_albion_ocr = resolve_ability_mentions(
        albion_ocr_payload=albion_ocr_payload,
        m3_ocr_payload=m3_ocr_payload,
        source_fingerprint=source_fingerprint,
        sample_interval_ms=sample_interval_ms,
        window_ms=window_ms,
    )
    events = build_ability_events(mentions, catalog=catalog, window_ms=window_ms)
    timestamps = sample_timestamps_ms(
        duration_ms,
        interval_ms=sample_interval_ms,
        max_frames=max(len({mention.timestamp_ms for mention in mentions}), 1),
    )
    if not timestamps:
        timestamps = [0]
    frame_windows = group_events_into_windows(
        events,
        timestamps=timestamps,
        window_ms=window_ms,
        source_fingerprint=source_fingerprint,
        catalog_id=catalog.id,
    )
    activation_count = sum(
        1
        for event in events
        if event.event_type
        in {AlbionAbilityEventType.ACTIVATION, AlbionAbilityEventType.ULTIMATE_ACTIVATION}
    )
    ultimate_count = sum(
        1 for event in events if event.event_type == AlbionAbilityEventType.ULTIMATE_ACTIVATION
    )
    cooldown_event_count = sum(
        1
        for event in events
        if event.event_type
        in {AlbionAbilityEventType.COOLDOWN_START, AlbionAbilityEventType.COOLDOWN_READY}
    )
    unique_abilities = sorted({event.ability_id for event in events})
    cache_key = build_detector_cache_key(
        source_fingerprint,
        frame_rate=frame_rate,
        catalog_id=catalog.id,
        catalog_token=catalog_cache_token(catalog),
        sample_interval_ms=sample_interval_ms,
        window_ms=window_ms,
        reused_albion_ocr=reused_albion_ocr,
    )
    if reused_albion_ocr and albion_ocr_payload is not None:
        ocr_cache_key = albion_ocr_payload.get("cache_key", "unknown")
        cache_key = f"{cache_key}:ocr:{ocr_cache_key}"

    return AlbionAbilityAnalysisResult(
        cache_key=cache_key,
        duration_ms=duration_ms,
        frame_rate=frame_rate,
        window_ms=window_ms,
        sample_interval_ms=sample_interval_ms,
        catalog_id=catalog.id,
        summary=AlbionAbilitySummary(
            frames_sampled=len(timestamps),
            window_count=len(frame_windows),
            mention_count=len(mentions),
            activation_count=activation_count,
            ultimate_count=ultimate_count,
            cooldown_event_count=cooldown_event_count,
            unique_ability_count=len(unique_abilities),
            catalog_id=catalog.id,
            by_ability=build_ability_counts(events),
            by_event_type=build_event_type_counts(events),
            reused_albion_ocr=reused_albion_ocr,
        ),
        frame_windows=frame_windows,
        events=events,
        unique_abilities=unique_abilities,
    )
