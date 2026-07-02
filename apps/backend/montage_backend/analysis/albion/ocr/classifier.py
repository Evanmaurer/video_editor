from __future__ import annotations

import re

from montage_backend.analysis.albion.ocr.albion_ocr_analysis import AlbionOcrCategory
from montage_backend.analysis.albion.ocr.lexicon import DEFAULT_ABILITY_NAMES, DEFAULT_ZONE_NAMES

GUILD_TAG_RE = re.compile(r"^\[([^\]]+)\]\s*$")
GUILD_PLAYER_RE = re.compile(r"^\[([^\]]+)\]\s+([A-Za-z0-9_\- ]+)$")
ALLIANCE_GUILD_PLAYER_RE = re.compile(r"^\[([^\]]+)\]\s*\[([^\]]+)\]\s+(.+)$")
DAMAGE_NUMBER_RE = re.compile(r"^[\d,\.]+\s*[kKmM]?$")
HEALING_NUMBER_RE = re.compile(r"^\+[\d,\.]+\s*[kKmM]?$")
HEALING_PHRASE_RE = re.compile(r"(?i)\b(healed|healing|restored)\b")
KILL_MESSAGE_RE = re.compile(r"(?i)\b(killed|slain|defeated|executed)\b")
DEATH_MESSAGE_RE = re.compile(r"(?i)\b(you died|has been killed|was killed by|executed by)\b")
LOOT_MESSAGE_RE = re.compile(r"(?i)\b(loot|received|collected|item acquired|picked up)\b")
ZONE_PREFIX_RE = re.compile(r"(?i)^(zone|area|region):\s*(.+)$")


def normalize_albion_text(text: str) -> str:
    return " ".join(text.strip().split()).lower()


def _matches_lexicon(text: str, lexicon: frozenset[str]) -> bool:
    normalized = normalize_albion_text(text)
    if normalized in lexicon:
        return True
    return any(entry in normalized for entry in lexicon if len(entry) >= 4)


def classify_albion_text(text: str) -> AlbionOcrCategory:
    cleaned = " ".join(text.strip().split())
    if not cleaned:
        return AlbionOcrCategory.UNKNOWN

    normalized = normalize_albion_text(cleaned)

    if DEATH_MESSAGE_RE.search(cleaned):
        return AlbionOcrCategory.DEATH_MESSAGE

    if LOOT_MESSAGE_RE.search(cleaned):
        return AlbionOcrCategory.LOOT_NOTIFICATION

    if KILL_MESSAGE_RE.search(cleaned):
        return AlbionOcrCategory.KILL_MESSAGE

    if HEALING_NUMBER_RE.match(cleaned) or HEALING_PHRASE_RE.search(cleaned):
        return AlbionOcrCategory.HEALING_NUMBER

    if DAMAGE_NUMBER_RE.match(cleaned):
        return AlbionOcrCategory.DAMAGE_NUMBER

    zone_match = ZONE_PREFIX_RE.match(cleaned)
    if zone_match is not None and _matches_lexicon(zone_match.group(2), DEFAULT_ZONE_NAMES):
        return AlbionOcrCategory.ZONE_NAME
    if _matches_lexicon(cleaned, DEFAULT_ZONE_NAMES):
        return AlbionOcrCategory.ZONE_NAME

    if _matches_lexicon(cleaned, DEFAULT_ABILITY_NAMES):
        return AlbionOcrCategory.ABILITY_NAME

    alliance_match = ALLIANCE_GUILD_PLAYER_RE.match(cleaned)
    if alliance_match is not None:
        if KILL_MESSAGE_RE.search(cleaned):
            return AlbionOcrCategory.KILL_MESSAGE
        return AlbionOcrCategory.PLAYER_NAME

    guild_only = GUILD_TAG_RE.match(cleaned)
    if guild_only is not None:
        return AlbionOcrCategory.GUILD_TAG

    guild_player = GUILD_PLAYER_RE.match(cleaned)
    if guild_player is not None:
        if KILL_MESSAGE_RE.search(cleaned):
            return AlbionOcrCategory.KILL_MESSAGE
        return AlbionOcrCategory.PLAYER_NAME

    if cleaned.istitle() and 1 <= len(cleaned.split()) <= 3 and cleaned.isascii():
        return AlbionOcrCategory.PLAYER_NAME

    return AlbionOcrCategory.UNKNOWN


def extract_albion_metadata(text: str, category: AlbionOcrCategory) -> dict:
    metadata: dict = {}
    cleaned = " ".join(text.strip().split())

    alliance_match = ALLIANCE_GUILD_PLAYER_RE.match(cleaned)
    if alliance_match is not None:
        metadata["alliance_tag"] = alliance_match.group(1)
        metadata["guild_tag"] = alliance_match.group(2)
        metadata["player_name"] = alliance_match.group(3).strip()
        return metadata

    guild_player = GUILD_PLAYER_RE.match(cleaned)
    if guild_player is not None:
        metadata["guild_tag"] = guild_player.group(1)
        metadata["player_name"] = guild_player.group(2).strip()
        return metadata

    guild_only = GUILD_TAG_RE.match(cleaned)
    if guild_only is not None:
        metadata["guild_tag"] = guild_only.group(1)
        return metadata

    if category == AlbionOcrCategory.ALLIANCE_TAG:
        metadata["alliance_tag"] = cleaned.strip("[]")

    if category in {AlbionOcrCategory.DAMAGE_NUMBER, AlbionOcrCategory.HEALING_NUMBER}:
        metadata["numeric_value"] = cleaned.replace(",", "").lstrip("+")

    if category == AlbionOcrCategory.ABILITY_NAME:
        metadata["ability_name"] = cleaned

    if category == AlbionOcrCategory.ZONE_NAME:
        metadata["zone_name"] = cleaned

    return metadata
