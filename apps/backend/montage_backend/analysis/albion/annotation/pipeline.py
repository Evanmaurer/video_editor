from __future__ import annotations

from montage_backend.analysis.albion.annotation.albion_timeline_annotation import (
    ALBION_ANNOTATION_ENGINE_VERSION,
    MARKER_COLORS,
    AlbionTimelineAnnotationResult,
    AlbionTimelineAnnotationSummary,
    AlbionTimelineMarker,
    AlbionTimelineMarkerType,
    AlbionTimelineRecommendation,
)
from montage_backend.analysis.albion.ability.albion_ability_analysis import AlbionAbilityEventType
from montage_backend.analysis.albion.combat.albion_combat_analysis import AlbionCombatEventType

DEDUPE_MS = 800


def build_annotation_cache_key(source_fingerprint: str, *, albion_cache_key: str) -> str:
    return f"{ALBION_ANNOTATION_ENGINE_VERSION}:{source_fingerprint}:albion:{albion_cache_key}"


def _normalize_search_text(*parts: str) -> str:
    return " ".join(part.strip().lower() for part in parts if part.strip())


def _payload_dict(detector_results: dict, detector_id: str) -> dict:
    detector_result = detector_results.get(detector_id)
    if not isinstance(detector_result, dict):
        return {}
    payload = detector_result.get("payload")
    return payload if isinstance(payload, dict) else {}


def _make_marker(
    *,
    marker_id: str,
    marker_type: AlbionTimelineMarkerType,
    timestamp_ms: int,
    label: str,
    reasoning: str,
    confidence: float = 0.7,
    end_ms: int | None = None,
    metadata: dict | None = None,
) -> AlbionTimelineMarker:
    return AlbionTimelineMarker(
        marker_id=marker_id,
        marker_type=marker_type,
        timestamp_ms=timestamp_ms,
        end_ms=end_ms,
        seek_ms=timestamp_ms,
        label=label,
        color=MARKER_COLORS[marker_type.value],
        confidence=round(min(max(confidence, 0.0), 1.0), 3),
        reasoning=reasoning,
        search_text=_normalize_search_text(marker_type.value, label, reasoning),
        metadata=metadata or {},
    )


def dedupe_markers(markers: list[AlbionTimelineMarker]) -> list[AlbionTimelineMarker]:
    if not markers:
        return []
    sorted_markers = sorted(markers, key=lambda item: (item.timestamp_ms, item.marker_type.value))
    kept: list[AlbionTimelineMarker] = []
    for marker in sorted_markers:
        if any(
            existing.marker_type == marker.marker_type
            and abs(existing.timestamp_ms - marker.timestamp_ms) < DEDUPE_MS
            for existing in kept
        ):
            continue
        kept.append(marker)
    return sorted(kept, key=lambda item: item.timestamp_ms)


def build_recommendations(
    *,
    highlight_payload: dict,
    engagement_payload: dict,
    markers: list[AlbionTimelineMarker],
) -> list[AlbionTimelineRecommendation]:
    recommendations: list[AlbionTimelineRecommendation] = []
    highlight_score = float(highlight_payload.get("highlight_score", 0.0))
    explanation = str(highlight_payload.get("explanation", ""))
    if highlight_score > 0 and explanation:
        anchor_ms = 0
        highlight_moments = highlight_payload.get("moments", [])
        if highlight_moments:
            anchor_ms = int(highlight_moments[0].get("timestamp_ms", 0))
        recommendations.append(
            AlbionTimelineRecommendation(
                recommendation_id=f"recommendation:highlight:{anchor_ms}",
                timestamp_ms=anchor_ms,
                seek_ms=anchor_ms,
                label=f"Highlight {highlight_score:.0f}/100",
                reasoning=explanation,
                confidence=min(0.98, 0.5 + highlight_score / 140.0),
            ),
        )

    primary_engagement = engagement_payload.get("summary", {}).get("primary_engagement")
    if primary_engagement:
        engagement_ms = next(
            (marker.timestamp_ms for marker in markers if marker.marker_type == AlbionTimelineMarkerType.KILL),
            0,
        )
        recommendations.append(
            AlbionTimelineRecommendation(
                recommendation_id=f"recommendation:engagement:{engagement_ms}",
                timestamp_ms=engagement_ms,
                seek_ms=engagement_ms,
                label=f"Primary engagement: {primary_engagement}",
                reasoning=f"Clip classified as {primary_engagement} from cached Albion engagement tags.",
                confidence=0.75,
            ),
        )

    bomb_marker = next(
        (marker for marker in markers if marker.marker_type == AlbionTimelineMarkerType.BOMB),
        None,
    )
    if bomb_marker is not None:
        recommendations.append(
            AlbionTimelineRecommendation(
                recommendation_id=f"recommendation:bomb:{bomb_marker.timestamp_ms}",
                timestamp_ms=bomb_marker.timestamp_ms,
                seek_ms=bomb_marker.timestamp_ms,
                label="Jump to bomb moment",
                reasoning=bomb_marker.reasoning,
                confidence=bomb_marker.confidence,
            ),
        )
    return recommendations


def build_timeline_markers_from_albion_payload(
    *,
    source_fingerprint: str,
    albion_payload: dict,
) -> AlbionTimelineAnnotationResult:
    detector_results = albion_payload.get("detector_results", {})
    if not isinstance(detector_results, dict):
        detector_results = {}

    combat_payload = _payload_dict(detector_results, "combat")
    bomb_payload = _payload_dict(detector_results, "bomb")
    engagement_payload = _payload_dict(detector_results, "engagement")
    ability_payload = _payload_dict(detector_results, "ability")
    ocr_payload = _payload_dict(detector_results, "ocr")
    highlight_payload = _payload_dict(detector_results, "highlight")

    markers: list[AlbionTimelineMarker] = []

    for index, entry in enumerate(combat_payload.get("entries", [])):
        if not isinstance(entry, dict):
            continue
        event_type = str(entry.get("event_type", ""))
        timestamp_ms = int(entry.get("timestamp_ms", 0))
        if event_type == AlbionCombatEventType.KILL.value:
            marker_type = AlbionTimelineMarkerType.KILL
        elif event_type == AlbionCombatEventType.FIGHT_START.value:
            marker_type = AlbionTimelineMarkerType.FIGHT_START
        elif event_type == AlbionCombatEventType.FIGHT_END.value:
            marker_type = AlbionTimelineMarkerType.FIGHT_END
        else:
            continue
        markers.append(
            _make_marker(
                marker_id=f"marker:{marker_type.value}:{timestamp_ms}:{index}",
                marker_type=marker_type,
                timestamp_ms=timestamp_ms,
                label=str(entry.get("label", marker_type.value)),
                reasoning=str(entry.get("label", marker_type.value)),
                confidence=float(entry.get("confidence", 0.65)),
                metadata=dict(entry.get("metadata", {})),
            ),
        )

    for index, event in enumerate(bomb_payload.get("events", [])):
        if not isinstance(event, dict):
            continue
        timestamp_ms = int(event.get("timestamp_ms", 0))
        markers.append(
            _make_marker(
                marker_id=f"marker:bomb:{timestamp_ms}:{index}",
                marker_type=AlbionTimelineMarkerType.BOMB,
                timestamp_ms=timestamp_ms,
                label="Bomb",
                reasoning=str(event.get("reasoning", "Bomb detected")),
                confidence=float(event.get("confidence", 0.75)),
                end_ms=int(event.get("window_end_ms", timestamp_ms)),
                metadata={
                    "bomb_score": event.get("bomb_score"),
                    "kill_count": event.get("kill_count"),
                },
            ),
        )

    for index, event in enumerate(ability_payload.get("events", [])):
        if not isinstance(event, dict):
            continue
        event_type = str(event.get("event_type", ""))
        if event_type not in {
            AlbionAbilityEventType.ACTIVATION.value,
            AlbionAbilityEventType.ULTIMATE_ACTIVATION.value,
        }:
            continue
        timestamp_ms = int(event.get("timestamp_ms", 0))
        ability_name = str(event.get("ability_name", "Ability"))
        markers.append(
            _make_marker(
                marker_id=f"marker:ability:{timestamp_ms}:{index}",
                marker_type=AlbionTimelineMarkerType.ABILITY,
                timestamp_ms=timestamp_ms,
                label=ability_name,
                reasoning=f"{ability_name} {event_type.replace('_', ' ')}",
                confidence=float(event.get("confidence", 0.6)),
                metadata={"ability_id": event.get("ability_id", "")},
            ),
        )

    for index, mention in enumerate(ocr_payload.get("mentions", [])):
        if not isinstance(mention, dict):
            continue
        timestamp_ms = int(mention.get("timestamp_ms", 0))
        text = str(mention.get("text", ""))
        markers.append(
            _make_marker(
                marker_id=f"marker:ocr:{timestamp_ms}:{index}",
                marker_type=AlbionTimelineMarkerType.OCR,
                timestamp_ms=timestamp_ms,
                label=text[:48] or "OCR",
                reasoning=text,
                confidence=float(mention.get("confidence", 0.55)),
                metadata=dict(mention.get("metadata", {})),
            ),
        )

    primary_engagement = engagement_payload.get("summary", {}).get("primary_engagement")
    if primary_engagement:
        engagement_ms = next(
            (marker.timestamp_ms for marker in markers if marker.marker_type == AlbionTimelineMarkerType.KILL),
            0,
        )
        markers.append(
            _make_marker(
                marker_id=f"marker:engagement:{engagement_ms}",
                marker_type=AlbionTimelineMarkerType.ENGAGEMENT,
                timestamp_ms=engagement_ms,
                label=str(primary_engagement),
                reasoning="Primary engagement classification for clip",
                confidence=0.8,
                metadata={"engagement_type": primary_engagement},
            ),
        )

    highlight_score = float(
        highlight_payload.get("highlight_score", highlight_payload.get("summary", {}).get("highlight_score", 0.0)),
    )
    if highlight_score > 0:
        highlight_moments = highlight_payload.get("moments", [])
        highlight_ms = int(highlight_moments[0].get("timestamp_ms", 0)) if highlight_moments else 0
        markers.append(
            _make_marker(
                marker_id=f"marker:highlight:{highlight_ms}",
                marker_type=AlbionTimelineMarkerType.HIGHLIGHT,
                timestamp_ms=highlight_ms,
                label=f"Highlight {highlight_score:.0f}",
                reasoning=str(highlight_payload.get("explanation", "Albion highlight score")),
                confidence=min(0.98, 0.5 + highlight_score / 140.0),
                metadata={"highlight_score": highlight_score},
            ),
        )

    markers = dedupe_markers(markers)
    recommendations = build_recommendations(
        highlight_payload=highlight_payload,
        engagement_payload=engagement_payload,
        markers=markers,
    )

    for index, recommendation in enumerate(recommendations):
        markers.append(
            _make_marker(
                marker_id=f"marker:recommendation:{recommendation.timestamp_ms}:{index}",
                marker_type=AlbionTimelineMarkerType.RECOMMENDATION,
                timestamp_ms=recommendation.timestamp_ms,
                label=recommendation.label,
                reasoning=recommendation.reasoning,
                confidence=recommendation.confidence,
                metadata={"recommendation_id": recommendation.recommendation_id},
            ),
        )

    markers = dedupe_markers(markers)
    by_marker_type: dict[str, int] = {}
    for marker in markers:
        key = marker.marker_type.value
        by_marker_type[key] = by_marker_type.get(key, 0) + 1

    albion_cache_key = str(albion_payload.get("cache_key", "unknown"))
    return AlbionTimelineAnnotationResult(
        cache_key=build_annotation_cache_key(source_fingerprint, albion_cache_key=albion_cache_key),
        duration_ms=int(albion_payload.get("duration_ms", 0)),
        frame_rate=float(albion_payload.get("frame_rate", 0.0)),
        summary=AlbionTimelineAnnotationSummary(
            marker_count=len(markers),
            recommendation_count=len(recommendations),
            highlight_score=highlight_score or None,
            primary_engagement=str(primary_engagement) if primary_engagement else None,
            by_marker_type=by_marker_type,
            reused_albion_combat=bool(combat_payload),
            reused_albion_bomb=bool(bomb_payload),
            reused_albion_engagement=bool(engagement_payload),
            reused_albion_ability=bool(ability_payload),
            reused_albion_ocr=bool(ocr_payload),
            reused_albion_highlight=bool(highlight_payload),
        ),
        markers=markers,
        recommendations=recommendations,
    )
