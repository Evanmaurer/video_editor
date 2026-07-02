from __future__ import annotations

from montage_backend.analysis.albion.search.engine import search_albion_clips
from montage_backend.analysis.albion.search.index import build_clip_search_document
from montage_backend.analysis.albion.search.query_parser import parse_albion_search_query


def _sample_albion_payload(
    *,
    kill_count: int = 5,
    bomb_count: int = 1,
    primary_engagement: str = "zvz",
    ability_name: str | None = None,
    sustained_combat_ms: int = 0,
    highlight_score: float = 38.3,
) -> dict:
    ability_events = []
    if ability_name:
        ability_events.append(
            {
                "ability_name": ability_name,
                "ability_id": ability_name.lower().replace(" ", "_"),
                "event_type": "ultimate_activation",
                "timestamp_ms": 3950,
            },
        )
    fight_entries = []
    if sustained_combat_ms > 0:
        fight_entries.extend(
            [
                {
                    "event_type": "fight_start",
                    "timestamp_ms": 1000,
                    "label": "Fight started",
                    "search_text": "fight_start combat",
                    "metadata": {"fight_end_ms": 1000 + sustained_combat_ms},
                },
                {
                    "event_type": "fight_end",
                    "timestamp_ms": 1000 + sustained_combat_ms,
                    "label": "Fight ended",
                    "search_text": "fight_end combat",
                    "metadata": {"fight_start_ms": 1000},
                },
            ],
        )
    return {
        "duration_ms": 8000,
        "detector_results": {
            "combat": {
                "payload": {
                    "summary": {
                        "kill_count": kill_count,
                        "death_count": 0,
                        "fight_count": 1 if sustained_combat_ms > 0 else 0,
                    },
                    "entries": [
                        *fight_entries,
                        {
                            "event_type": "kill",
                            "timestamp_ms": 4000,
                            "label": "Kill: Enemy",
                            "search_text": "kill enemy",
                            "metadata": {},
                        },
                    ],
                },
            },
            "bomb": {
                "payload": {
                    "summary": {"bomb_count": bomb_count, "top_bomb_score": 8.4},
                    "events": [
                        {
                            "timestamp_ms": 4000,
                            "search_text": "bomb coordinated",
                            "bomb_score": 8.4,
                            "kill_count": kill_count,
                        },
                    ]
                    if bomb_count > 0
                    else [],
                },
            },
            "engagement": {
                "payload": {
                    "summary": {"primary_engagement": primary_engagement},
                    "tags": [{"engagement_type": primary_engagement, "score": 8.6}],
                },
            },
            "ability": {
                "payload": {
                    "summary": {
                        "activation_count": len(ability_events),
                        "ultimate_count": len(ability_events),
                        "unique_ability_count": len(ability_events),
                    },
                    "events": ability_events,
                },
            },
            "highlight": {
                "payload": {
                    "highlight_score": highlight_score,
                    "summary": {"highlight_score": highlight_score, "explanation": "test"},
                },
            },
        },
    }


def test_parse_bomb_and_zvz_queries():
    bomb_filters = parse_albion_search_query("Show all bomb clips.")
    assert bomb_filters.has_bomb is True
    assert "bomb" in bomb_filters.event_types

    zvz_filters = parse_albion_search_query("Find every ZvZ fight.")
    assert "zvz" in zvz_filters.engagement_types


def test_parse_kill_count_and_fight_duration_queries():
    kill_filters = parse_albion_search_query("Find clips with three or more kill notifications.")
    assert kill_filters.min_kills == 3
    assert kill_filters.ability_name is None

    numeric_kill_filters = parse_albion_search_query("Find clips with 3 or more kills.")
    assert numeric_kill_filters.min_kills == 3
    assert numeric_kill_filters.ability_name is None

    duration_filters = parse_albion_search_query("Show fights lasting longer than 30 seconds.")
    assert duration_filters.min_fight_duration_ms == 30000


def test_parse_ability_name_query():
    filters = parse_albion_search_query("Show kills involving Galatine.")
    assert filters.ability_name == "Galatine"


def test_build_clip_search_document_indexes_cached_metadata():
    document = build_clip_search_document(
        media_id="media-1",
        file_name="zvz-clip.mp4",
        albion_payload=_sample_albion_payload(ability_name="Grovekeeper"),
    )
    assert document.kill_count == 5
    assert document.bomb_count == 1
    assert document.primary_engagement == "zvz"
    assert "Grovekeeper" in document.ability_names
    assert any(event.event_type == "bomb" for event in document.events)


def test_search_bomb_clips_uses_cached_metadata_only():
    documents = [
        build_clip_search_document(
            media_id="media-bomb",
            file_name="bomb-clip.mp4",
            albion_payload=_sample_albion_payload(),
        ),
        build_clip_search_document(
            media_id="media-quiet",
            file_name="quiet-clip.mp4",
            albion_payload=_sample_albion_payload(kill_count=0, bomb_count=0, primary_engagement="gathering"),
        ),
    ]
    result = search_albion_clips(documents, query="Show all bomb clips.")
    assert result.used_cached_metadata_only is True
    assert result.match_count == 1
    assert result.matches[0].media_id == "media-bomb"
    assert result.matches[0].bomb_count == 1


def test_search_filters_by_engagement_kill_count_and_ability():
    documents = [
        build_clip_search_document(
            media_id="media-zvz",
            file_name="zvz.mp4",
            albion_payload=_sample_albion_payload(ability_name="Grovekeeper"),
        ),
        build_clip_search_document(
            media_id="media-gank",
            file_name="gank.mp4",
            albion_payload=_sample_albion_payload(
                kill_count=2,
                bomb_count=0,
                primary_engagement="ganking",
                highlight_score=22.0,
            ),
        ),
    ]

    zvz = search_albion_clips(documents, query="Find every ZvZ fight.")
    assert any(match.media_id == "media-zvz" for match in zvz.matches)

    kills = search_albion_clips(documents, query="Find clips with three or more kill notifications.")
    assert kills.match_count == 1
    assert all(match.kill_count >= 3 for match in kills.matches)

    ability = search_albion_clips(documents, query="Show all clips containing Grovekeeper.")
    assert any(match.media_id == "media-zvz" for match in ability.matches)


def test_search_filters_by_fight_duration():
    documents = [
        build_clip_search_document(
            media_id="media-long",
            file_name="long-fight.mp4",
            albion_payload=_sample_albion_payload(sustained_combat_ms=35000),
        ),
        build_clip_search_document(
            media_id="media-short",
            file_name="short-fight.mp4",
            albion_payload=_sample_albion_payload(sustained_combat_ms=4000),
        ),
    ]
    result = search_albion_clips(documents, query="Show fights lasting longer than 30 seconds.")
    assert result.match_count == 1
    assert result.matches[0].media_id == "media-long"
    assert result.matches[0].sustained_combat_ms >= 30000
