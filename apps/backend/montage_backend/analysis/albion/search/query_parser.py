from __future__ import annotations

import re

from montage_backend.analysis.albion.search.albion_search_analysis import AlbionSearchFilters

NUMBER_WORDS = {
    "zero": 0,
    "one": 1,
    "two": 2,
    "three": 3,
    "four": 4,
    "five": 5,
    "six": 6,
    "seven": 7,
    "eight": 8,
    "nine": 9,
    "ten": 10,
}

ENGAGEMENT_ALIASES: dict[str, list[str]] = {
    "zvz": ["zvz", "zerg", "large scale", "large-scale"],
    "ganking": ["gank", "ganking"],
    "gathering": ["gather", "gathering", "harvest", "harvesting"],
    "roaming": ["roam", "roaming"],
    "dungeon": ["dungeon", "dg"],
    "open_world_pvp": ["open world", "open-world", "open world pvp", "open-world pvp"],
}

EVENT_ALIASES: dict[str, list[str]] = {
    "bomb": ["bomb", "bombs", "bombing"],
    "kill": ["kill", "kills", "kill feed", "kill notification", "kill notifications"],
    "death": ["death", "deaths", "died"],
    "fight_start": ["fight start", "fight started", "combat start"],
    "fight_end": ["fight end", "fight ended", "combat end"],
    "ability": ["ability", "abilities", "ultimate", "ultimates"],
}


def _parse_min_kills(text: str) -> int | None:
    patterns = [
        r"(?:at least|>=|more than|over)\s*(\d+)\s+kills?",
        r"(\d+)\s+or\s+more\s+kills?",
        r"(?:find|show).*?(\d+)\s+or\s+more\s+kill",
        r"(\d+)\+\s+kills?",
    ]
    for pattern in patterns:
        match = re.search(pattern, text)
        if match:
            return int(match.group(1))

    word_patterns = [
        r"(one|two|three|four|five|six|seven|eight|nine|ten)\s+or\s+more\s+kills?",
        r"(one|two|three|four|five|six|seven|eight|nine|ten)\s+or\s+more\s+kill(?:\s+notifications?)?",
    ]
    for pattern in word_patterns:
        match = re.search(pattern, text)
        if match:
            return NUMBER_WORDS[match.group(1)]
    return None


def _parse_fight_duration_ms(text: str) -> int | None:
    patterns = [
        r"(?:longer than|over|more than)\s*(\d+)\s*(?:seconds|second|secs|sec|s)\b",
        r"(\d+)\s*(?:seconds|second|secs|sec|s)\s+(?:or\s+longer|fight|fights|combat)",
        r"fights?\s+lasting\s+(?:longer than|over)\s*(\d+)\s*(?:seconds|second|secs|sec|s)\b",
    ]
    for pattern in patterns:
        match = re.search(pattern, text)
        if match:
            return int(match.group(1)) * 1000
    return None


def _is_valid_ability_candidate(candidate: str) -> bool:
    lowered = candidate.strip(" .").lower()
    if not lowered:
        return False
    blocked_phrases = (
        "kill",
        "notification",
        "more",
        "or more",
        "clip",
        "fight",
        "bomb",
        "second",
        "duration",
    )
    if any(phrase in lowered for phrase in blocked_phrases):
        return False
    if lowered in {"kill", "kills", "bomb", "bombs", "fight", "fights", "clip", "clips"}:
        return False
    return True


def _parse_ability_name(text: str) -> str | None:
    patterns = [
        r"(?:involving|using)\s+([a-zA-Z][\w'-]{2,40})",
        r"(?:ability|abilities)\s+(?:named|called)\s+([a-zA-Z][\w\s'-]{2,40})",
        r"clips?\s+containing\s+([a-zA-Z][\w'-]{2,40})",
    ]
    for pattern in patterns:
        match = re.search(pattern, text, flags=re.IGNORECASE)
        if match:
            candidate = match.group(1).strip(" .")
            if candidate.lower().endswith(" ability"):
                candidate = candidate[: -len(" ability")].strip()
            if _is_valid_ability_candidate(candidate):
                return candidate
    return None


def _append_unique(values: list[str], value: str) -> None:
    if value not in values:
        values.append(value)


def parse_albion_search_query(
    query: str,
    *,
    explicit: AlbionSearchFilters | None = None,
) -> AlbionSearchFilters:
    filters = explicit.model_copy(deep=True) if explicit is not None else AlbionSearchFilters()
    lowered = query.strip().lower()
    if not lowered:
        return filters

    for engagement_type, aliases in ENGAGEMENT_ALIASES.items():
        if any(alias in lowered for alias in aliases):
            _append_unique(filters.engagement_types, engagement_type)

    for event_type, aliases in EVENT_ALIASES.items():
        if any(alias in lowered for alias in aliases):
            _append_unique(filters.event_types, event_type)

    if "bomb" in lowered or "bombs" in lowered:
        filters.has_bomb = True

    min_kills = _parse_min_kills(lowered)
    if min_kills is not None:
        filters.min_kills = max(filters.min_kills or 0, min_kills)

    fight_duration_ms = _parse_fight_duration_ms(lowered)
    if fight_duration_ms is not None:
        current = filters.min_fight_duration_ms or 0
        filters.min_fight_duration_ms = max(current, fight_duration_ms)

    ability_name = _parse_ability_name(query)
    if ability_name and not filters.ability_name and filters.min_kills is None:
        filters.ability_name = ability_name

    highlight_match = re.search(r"highlight(?:\s+score)?\s+(?:above|over|>=)\s*(\d+)", lowered)
    if highlight_match:
        current = filters.min_highlight_score or 0.0
        filters.min_highlight_score = max(current, float(highlight_match.group(1)))

    stripped = query.strip()
    if (
        stripped
        and not filters.engagement_types
        and not filters.event_types
        and filters.has_bomb is None
        and filters.min_kills is None
        and filters.min_fight_duration_ms is None
        and filters.ability_name is None
        and filters.min_highlight_score is None
    ):
        filters.free_text = stripped

    return filters
