from __future__ import annotations

from montage_backend.analysis.albion.annotation.albion_timeline_annotation import (
    ALBION_ANNOTATION_ENGINE_VERSION,
    AlbionTimelineMarkerType,
)
from montage_backend.analysis.albion.annotation.pipeline import (
    build_annotation_cache_key,
    build_recommendations,
    build_timeline_markers_from_albion_payload,
    dedupe_markers,
)
from montage_backend.analysis.albion.annotation.albion_timeline_annotation import AlbionTimelineMarker


def _sample_albion_payload() -> dict:
    return {
        "cache_key": "albion:annotation-test",
        "duration_ms": 8000,
        "frame_rate": 60.0,
        "detector_results": {
            "combat": {
                "payload": {
                    "entries": [
                        {
                            "event_type": "kill",
                            "timestamp_ms": 4000,
                            "label": "Kill: Enemy",
                            "confidence": 0.9,
                            "metadata": {},
                        },
                        {
                            "event_type": "fight_start",
                            "timestamp_ms": 3200,
                            "label": "Fight start",
                            "confidence": 0.7,
                            "metadata": {},
                        },
                    ],
                },
            },
            "bomb": {
                "payload": {
                    "events": [
                        {
                            "timestamp_ms": 4000,
                            "reasoning": "Bomb detected: 5 kills",
                            "confidence": 0.84,
                            "bomb_score": 8.4,
                            "kill_count": 5,
                            "window_end_ms": 4500,
                        },
                    ],
                },
            },
            "ability": {
                "payload": {
                    "events": [
                        {
                            "ability_name": "Grovekeeper",
                            "ability_id": "grovekeeper",
                            "event_type": "ultimate_activation",
                            "timestamp_ms": 3950,
                            "confidence": 0.8,
                        },
                    ],
                },
            },
            "engagement": {
                "payload": {
                    "summary": {"primary_engagement": "zvz"},
                },
            },
            "highlight": {
                "payload": {
                    "highlight_score": 78.4,
                    "explanation": "Strong ZvZ bomb with multiple kills.",
                    "moments": [{"timestamp_ms": 4000, "moment_type": "bomb"}],
                },
            },
        },
    }


def test_build_annotation_cache_key():
    key = build_annotation_cache_key("fp-test", albion_cache_key="albion:annotation-test")
    assert key.startswith(ALBION_ANNOTATION_ENGINE_VERSION)
    assert "fp-test" in key
    assert "albion:annotation-test" in key


def test_build_timeline_markers_from_albion_payload():
    result = build_timeline_markers_from_albion_payload(
        source_fingerprint="fp-test",
        albion_payload=_sample_albion_payload(),
    )
    assert result.engine_version == ALBION_ANNOTATION_ENGINE_VERSION
    assert result.duration_ms == 8000
    assert result.summary.reused_albion_combat is True
    assert result.summary.reused_albion_bomb is True
    assert result.summary.reused_albion_ability is True
    assert result.summary.primary_engagement == "zvz"
    assert result.summary.highlight_score == 78.4

    marker_types = {marker.marker_type for marker in result.markers}
    assert AlbionTimelineMarkerType.KILL in marker_types
    assert AlbionTimelineMarkerType.BOMB in marker_types
    assert AlbionTimelineMarkerType.ABILITY in marker_types
    assert AlbionTimelineMarkerType.FIGHT_START in marker_types
    assert AlbionTimelineMarkerType.ENGAGEMENT in marker_types
    assert AlbionTimelineMarkerType.HIGHLIGHT in marker_types

    bomb = next(m for m in result.markers if m.marker_type == AlbionTimelineMarkerType.BOMB)
    assert bomb.timestamp_ms == 4000
    assert bomb.color == "#e74c3c"
    assert bomb.seek_ms == 4000


def test_dedupe_markers_collapses_near_duplicate_types():
    markers = [
        AlbionTimelineMarker(
            marker_id="a",
            marker_type=AlbionTimelineMarkerType.KILL,
            timestamp_ms=4000,
            seek_ms=4000,
            label="Kill",
            color="#3498db",
            confidence=0.9,
            reasoning="kill",
            search_text="kill",
        ),
        AlbionTimelineMarker(
            marker_id="b",
            marker_type=AlbionTimelineMarkerType.KILL,
            timestamp_ms=4100,
            seek_ms=4100,
            label="Kill",
            color="#3498db",
            confidence=0.8,
            reasoning="kill",
            search_text="kill",
        ),
    ]
    deduped = dedupe_markers(markers)
    assert len(deduped) == 1


def test_build_recommendations_includes_highlight_and_bomb():
    result = build_timeline_markers_from_albion_payload(
        source_fingerprint="fp-test",
        albion_payload=_sample_albion_payload(),
    )
    recommendations = build_recommendations(
        highlight_payload=_sample_albion_payload()["detector_results"]["highlight"]["payload"],
        engagement_payload=_sample_albion_payload()["detector_results"]["engagement"]["payload"],
        markers=result.markers,
    )
    labels = {item.label for item in recommendations}
    assert any("Highlight" in label for label in labels)
    assert any("bomb" in label.lower() for label in labels)
