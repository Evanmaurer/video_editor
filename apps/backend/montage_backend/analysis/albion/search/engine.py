from __future__ import annotations

from montage_backend.analysis.albion.search.albion_search_analysis import (
    AlbionSearchEventMatch,
    AlbionSearchFilters,
    AlbionSearchMatch,
    AlbionSearchResponse,
)
from montage_backend.analysis.albion.search.index import AlbionClipSearchDocument, AlbionSearchableEvent
from montage_backend.analysis.albion.search.query_parser import parse_albion_search_query


def _normalize(value: str) -> str:
    return value.strip().lower()


def _event_matches_filters(event: AlbionSearchableEvent, filters: AlbionSearchFilters) -> bool:
    if filters.event_types:
        allowed = {_normalize(value) for value in filters.event_types}
        if _normalize(event.event_type) not in allowed:
            return False
    if filters.ability_name:
        needle = _normalize(filters.ability_name)
        haystack = _normalize(" ".join((event.label, event.search_text, str(event.metadata.get("ability_id", "")))))
        if needle not in haystack:
            return False
    if filters.free_text:
        needle = _normalize(filters.free_text)
        haystack = _normalize(" ".join((event.label, event.search_text)))
        if needle not in haystack:
            return False
    return True


def _collect_matched_events(document: AlbionClipSearchDocument, filters: AlbionSearchFilters) -> list[AlbionSearchableEvent]:
    matched = [event for event in document.events if _event_matches_filters(event, filters)]
    if filters.has_bomb and document.bomb_count > 0:
        for event in document.events:
            if event.event_type == "bomb" and event not in matched:
                matched.append(event)
    return matched


def _clip_matches_filters(document: AlbionClipSearchDocument, filters: AlbionSearchFilters) -> bool:
    if filters.has_bomb is True and document.bomb_count <= 0:
        return False
    if filters.min_kills is not None and document.kill_count < filters.min_kills:
        return False
    if filters.min_fight_duration_ms is not None and document.sustained_combat_ms < filters.min_fight_duration_ms:
        return False
    if filters.min_highlight_score is not None and document.highlight_score < filters.min_highlight_score:
        return False
    if filters.engagement_types:
        clip_types = {_normalize(value) for value in document.engagement_types}
        if document.primary_engagement:
            clip_types.add(_normalize(str(document.primary_engagement)))
        if not any(_normalize(value) in clip_types for value in filters.engagement_types):
            return False

    matched_events = _collect_matched_events(document, filters)
    if filters.event_types or filters.ability_name:
        if not matched_events and not (filters.has_bomb and document.bomb_count > 0):
            return False
    if filters.free_text and _normalize(filters.free_text) not in document.search_blob and not matched_events:
        return False
    return True


def _build_reasoning(document: AlbionClipSearchDocument, filters: AlbionSearchFilters) -> str:
    parts: list[str] = []
    if document.bomb_count > 0:
        parts.append(f"{document.bomb_count} bomb(s)")
    if document.kill_count > 0:
        parts.append(f"{document.kill_count} kill(s)")
    if document.primary_engagement:
        parts.append(f"engagement={document.primary_engagement}")
    if document.highlight_score > 0:
        parts.append(f"highlight={document.highlight_score:.1f}")
    if filters.ability_name:
        parts.append(f"ability match for {filters.ability_name}")
    return ", ".join(parts) or "matched cached Albion metadata"


def _score_clip(document: AlbionClipSearchDocument, filters: AlbionSearchFilters, matched_events: list[AlbionSearchableEvent]) -> float:
    score = min(100.0, document.highlight_score * 0.45)
    score += min(30.0, document.kill_count * 4.0)
    score += min(20.0, document.bomb_count * 10.0)
    score += min(10.0, len(matched_events) * 2.5)
    if filters.engagement_types and document.primary_engagement:
        if _normalize(str(document.primary_engagement)) in {_normalize(value) for value in filters.engagement_types}:
            score += 8.0
    if filters.ability_name:
        needle = _normalize(filters.ability_name)
        if any(needle in _normalize(name) for name in document.ability_names):
            score += 12.0
    return round(min(score, 100.0), 1)


def search_albion_clips(
    documents: list[AlbionClipSearchDocument],
    *,
    query: str,
    explicit_filters: AlbionSearchFilters | None = None,
    limit: int = 50,
    clips_searched: int | None = None,
) -> AlbionSearchResponse:
    filters = parse_albion_search_query(query, explicit=explicit_filters)
    matches: list[AlbionSearchMatch] = []

    for document in documents:
        if not _clip_matches_filters(document, filters):
            continue
        matched_events = _collect_matched_events(document, filters)
        match_score = _score_clip(document, filters, matched_events)
        event_matches = [
            AlbionSearchEventMatch(
                event_type=event.event_type,
                timestamp_ms=event.timestamp_ms,
                label=event.label,
                search_text=event.search_text,
                metadata=event.metadata,
            )
            for event in sorted(matched_events, key=lambda item: item.timestamp_ms)[:12]
        ]
        matches.append(
            AlbionSearchMatch(
                media_id=document.media_id,
                file_name=document.file_name,
                match_score=match_score,
                confidence=round(min(0.98, 0.45 + match_score / 140.0), 3),
                reasoning=_build_reasoning(document, filters),
                highlight_score=document.highlight_score or None,
                primary_engagement=document.primary_engagement,
                kill_count=document.kill_count,
                bomb_count=document.bomb_count,
                sustained_combat_ms=document.sustained_combat_ms,
                matched_events=event_matches,
            ),
        )

    matches.sort(key=lambda item: (-item.match_score, item.media_id))
    limited = matches[:limit]
    return AlbionSearchResponse(
        query=query,
        parsed_filters=filters,
        match_count=len(limited),
        clips_searched=clips_searched if clips_searched is not None else len(documents),
        clips_with_albion_cache=len(documents),
        used_cached_metadata_only=True,
        matches=limited,
    )
