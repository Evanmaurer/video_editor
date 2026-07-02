from __future__ import annotations

from dataclasses import dataclass, field

from montage_backend.analysis.albion.engagement.pipeline import extract_fight_durations


@dataclass
class AlbionSearchableEvent:
    event_type: str
    timestamp_ms: int
    label: str
    search_text: str
    metadata: dict = field(default_factory=dict)


@dataclass
class AlbionClipSearchDocument:
    media_id: str
    file_name: str | None
    duration_ms: int
    kill_count: int = 0
    death_count: int = 0
    fight_count: int = 0
    bomb_count: int = 0
    sustained_combat_ms: int = 0
    highlight_score: float = 0.0
    engagement_types: list[str] = field(default_factory=list)
    primary_engagement: str | None = None
    ability_names: list[str] = field(default_factory=list)
    events: list[AlbionSearchableEvent] = field(default_factory=list)
    search_blob: str = ""


def _append_event(
    events: list[AlbionSearchableEvent],
    *,
    event_type: str,
    timestamp_ms: int,
    label: str,
    search_text: str = "",
    metadata: dict | None = None,
) -> None:
    events.append(
        AlbionSearchableEvent(
            event_type=event_type,
            timestamp_ms=timestamp_ms,
            label=label,
            search_text=search_text or label,
            metadata=metadata or {},
        ),
    )


def _payload_dict(detector_results: dict, detector_id: str) -> dict:
    detector_result = detector_results.get(detector_id)
    if not isinstance(detector_result, dict):
        return {}
    payload = detector_result.get("payload")
    return payload if isinstance(payload, dict) else {}


def build_clip_search_document(
    *,
    media_id: str,
    file_name: str | None,
    albion_payload: dict,
) -> AlbionClipSearchDocument:
    detector_results = albion_payload.get("detector_results", {})
    if not isinstance(detector_results, dict):
        detector_results = {}

    combat_payload = _payload_dict(detector_results, "combat")
    bomb_payload = _payload_dict(detector_results, "bomb")
    engagement_payload = _payload_dict(detector_results, "engagement")
    ability_payload = _payload_dict(detector_results, "ability")
    ocr_payload = _payload_dict(detector_results, "ocr")
    highlight_payload = _payload_dict(detector_results, "highlight")

    combat_summary = combat_payload.get("summary", {})
    bomb_summary = bomb_payload.get("summary", {})
    engagement_summary = engagement_payload.get("summary", {})
    highlight_summary = highlight_payload.get("summary", {})

    events: list[AlbionSearchableEvent] = []

    for entry in combat_payload.get("entries", []):
        if not isinstance(entry, dict):
            continue
        _append_event(
            events,
            event_type=str(entry.get("event_type", "combat")),
            timestamp_ms=int(entry.get("timestamp_ms", 0)),
            label=str(entry.get("label", "")),
            search_text=str(entry.get("search_text", entry.get("label", ""))),
            metadata=dict(entry.get("metadata", {})),
        )

    for bomb_event in bomb_payload.get("events", []):
        if not isinstance(bomb_event, dict):
            continue
        _append_event(
            events,
            event_type="bomb",
            timestamp_ms=int(bomb_event.get("timestamp_ms", 0)),
            label="Bomb",
            search_text=str(bomb_event.get("search_text", "bomb")),
            metadata={
                "bomb_score": bomb_event.get("bomb_score"),
                "kill_count": bomb_event.get("kill_count"),
            },
        )

    for ability_event in ability_payload.get("events", []):
        if not isinstance(ability_event, dict):
            continue
        ability_name = str(ability_event.get("ability_name", ""))
        _append_event(
            events,
            event_type="ability",
            timestamp_ms=int(ability_event.get("timestamp_ms", 0)),
            label=ability_name or "Ability",
            search_text=" ".join(
                part
                for part in (
                    ability_name,
                    str(ability_event.get("event_type", "")),
                    str(ability_event.get("ability_id", "")),
                )
                if part
            ),
            metadata={"ability_id": ability_event.get("ability_id", "")},
        )

    for mention in ocr_payload.get("mentions", []):
        if not isinstance(mention, dict):
            continue
        _append_event(
            events,
            event_type="ocr",
            timestamp_ms=int(mention.get("timestamp_ms", 0)),
            label=str(mention.get("text", "")),
            search_text=str(mention.get("text", "")),
            metadata=dict(mention.get("metadata", {})),
        )

    engagement_types = [
        str(tag.get("engagement_type", ""))
        for tag in engagement_payload.get("tags", [])
        if isinstance(tag, dict) and tag.get("engagement_type")
    ]
    ability_names = sorted(
        {
            str(event.get("ability_name", ""))
            for event in ability_payload.get("events", [])
            if isinstance(event, dict) and event.get("ability_name")
        }
        - {""},
    )

    search_parts = [
        file_name or "",
        " ".join(engagement_types),
        str(engagement_summary.get("primary_engagement", "")),
        " ".join(ability_names),
        " ".join(event.search_text for event in events),
        str(highlight_summary.get("explanation", "")),
    ]

    return AlbionClipSearchDocument(
        media_id=media_id,
        file_name=file_name,
        duration_ms=int(albion_payload.get("duration_ms", 0)),
        kill_count=int(combat_summary.get("kill_count", 0)),
        death_count=int(combat_summary.get("death_count", 0)),
        fight_count=int(combat_summary.get("fight_count", 0)),
        bomb_count=int(bomb_summary.get("bomb_count", 0)),
        sustained_combat_ms=max(extract_fight_durations(combat_payload), default=0),
        highlight_score=float(
            highlight_payload.get("highlight_score", highlight_summary.get("highlight_score", 0.0)),
        ),
        engagement_types=engagement_types,
        primary_engagement=engagement_summary.get("primary_engagement"),
        ability_names=ability_names,
        events=events,
        search_blob=" ".join(part.lower() for part in search_parts if part).strip(),
    )
