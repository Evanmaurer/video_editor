from __future__ import annotations

import json
from functools import lru_cache
from pathlib import Path
from typing import Any

from pydantic import BaseModel, Field

PACKAGE_CATALOG_DIR = Path(__file__).resolve().parent / "presets"
REPO_CATALOG_DIR = Path(__file__).resolve().parents[6] / "ai" / "plugins" / "albion" / "abilities"


class AlbionAbilityDefinition(BaseModel):
    id: str
    name: str
    aliases: list[str] = Field(default_factory=list)
    cooldown_ms: int = 15000
    is_ultimate: bool = False
    category: str = "general"


class AlbionAbilityCatalog(BaseModel):
    id: str
    game_id: str = "albion"
    version: str = "1.0"
    abilities: list[AlbionAbilityDefinition] = Field(default_factory=list)


def _definition(
    ability_id: str,
    name: str,
    *,
    cooldown_ms: int = 15000,
    is_ultimate: bool = False,
    aliases: list[str] | None = None,
    category: str = "general",
) -> AlbionAbilityDefinition:
    alias_set = {name.lower(), *(aliases or [])}
    return AlbionAbilityDefinition(
        id=ability_id,
        name=name,
        aliases=sorted(alias_set),
        cooldown_ms=cooldown_ms,
        is_ultimate=is_ultimate,
        category=category,
    )


BUILTIN_CATALOG = AlbionAbilityCatalog(
    id="albion-abilities-default",
    abilities=[
        _definition("galatine_pair", "Galatine Pair", cooldown_ms=20000, category="melee"),
        _definition("meteor", "Meteor", cooldown_ms=120000, is_ultimate=True, category="fire"),
        _definition("thunderstorm", "Thunderstorm", cooldown_ms=90000, is_ultimate=True, category="nature"),
        _definition("avalon_blink", "Avalon Blink", cooldown_ms=25000, category="arcane"),
        _definition("brimstone_falls", "Brimstone Falls", cooldown_ms=35000, category="fire"),
        _definition("crystal_leech", "Crystal Leech", cooldown_ms=18000, category="arcane"),
        _definition("dark_blessing", "Dark Blessing", cooldown_ms=22000, category="cursed"),
        _definition("enchanted_strike", "Enchanted Strike", cooldown_ms=12000, category="melee"),
        _definition("energy_beam", "Energy Beam", cooldown_ms=28000, category="arcane"),
        _definition("frost_nova", "Frost Nova", cooldown_ms=24000, category="frost"),
        _definition("grovekeeper", "Grovekeeper", cooldown_ms=110000, is_ultimate=True, category="nature"),
        _definition("hand_of_nature", "Hand of Nature", cooldown_ms=30000, category="nature"),
        _definition("heavy_smash", "Heavy Smash", cooldown_ms=14000, category="melee"),
        _definition("heroic_strike", "Heroic Strike", cooldown_ms=10000, category="melee"),
        _definition("holy_smite", "Holy Smite", cooldown_ms=16000, category="holy"),
        _definition("ice_shard", "Ice Shard", cooldown_ms=8000, category="frost"),
        _definition("judgment", "Judgment", cooldown_ms=100000, is_ultimate=True, category="holy"),
        _definition("locus_of_power", "Locus of Power", cooldown_ms=95000, is_ultimate=True, category="arcane"),
        _definition("mighty_swing", "Mighty Swing", cooldown_ms=13000, category="melee"),
        _definition("morganas_curse", "Morgana's Curse", cooldown_ms=32000, aliases=["morgana's curse"], category="cursed"),
        _definition("poison_thorns", "Poison Thorns", cooldown_ms=17000, category="nature"),
        _definition("purge", "Purge", cooldown_ms=26000, category="holy"),
        _definition("redemption", "Redemption", cooldown_ms=105000, is_ultimate=True, category="holy"),
        _definition("sandstorm", "Sandstorm", cooldown_ms=88000, is_ultimate=True, category="earth"),
        _definition("shield_slam", "Shield Slam", cooldown_ms=15000, category="melee"),
        _definition("smite", "Smite", cooldown_ms=9000, category="holy"),
        _definition("spirit_walk", "Spirit Walk", cooldown_ms=21000, category="nature"),
        _definition("stone_fist", "Stone Fist", cooldown_ms=19000, category="earth"),
        _definition("sword_slash", "Sword Slash", cooldown_ms=7000, category="melee"),
        _definition("wind_wall", "Wind Wall", cooldown_ms=45000, category="nature"),
    ],
)


def _parse_catalog_payload(payload: dict[str, Any]) -> AlbionAbilityCatalog:
    abilities = [
        AlbionAbilityDefinition(
            id=str(item["id"]),
            name=str(item["name"]),
            aliases=[str(alias).lower() for alias in item.get("aliases", [])],
            cooldown_ms=int(item.get("cooldown_ms", 15000)),
            is_ultimate=bool(item.get("is_ultimate", False)),
            category=str(item.get("category", "general")),
        )
        for item in payload.get("abilities", [])
    ]
    for ability in abilities:
        normalized_aliases = {ability.name.lower(), *(alias.lower() for alias in ability.aliases)}
        ability.aliases = sorted(normalized_aliases)
    return AlbionAbilityCatalog(
        id=str(payload.get("id", "albion-abilities-custom")),
        game_id=str(payload.get("game_id", "albion")),
        version=str(payload.get("version", "1.0")),
        abilities=abilities,
    )


def _load_catalog_file(path: Path) -> AlbionAbilityCatalog | None:
    if not path.exists():
        return None
    text = path.read_text(encoding="utf-8")
    if path.suffix.lower() in {".yaml", ".yml"}:
        try:
            import yaml
        except ImportError:
            return None
        payload = yaml.safe_load(text)
    else:
        payload = json.loads(text)
    if not isinstance(payload, dict):
        return None
    return _parse_catalog_payload(payload)


@lru_cache(maxsize=8)
def list_catalog_ids() -> tuple[str, ...]:
    ids = {BUILTIN_CATALOG.id}
    for directory in (PACKAGE_CATALOG_DIR, REPO_CATALOG_DIR):
        if not directory.exists():
            continue
        for path in directory.glob("*"):
            if path.suffix.lower() in {".json", ".yaml", ".yml"}:
                ids.add(path.stem.replace("_catalog", ""))
    return tuple(sorted(ids))


def get_catalog(catalog_id: str | None = None) -> AlbionAbilityCatalog:
    if catalog_id is None or catalog_id == BUILTIN_CATALOG.id:
        return BUILTIN_CATALOG
    for directory in (PACKAGE_CATALOG_DIR, REPO_CATALOG_DIR):
        for suffix in (".json", ".yaml", ".yml"):
            loaded = _load_catalog_file(directory / f"{catalog_id}{suffix}")
            if loaded is not None:
                return loaded
    if catalog_id == "default":
        loaded = _load_catalog_file(REPO_CATALOG_DIR / "default.json")
        if loaded is not None:
            return loaded
    return BUILTIN_CATALOG


def catalog_cache_token(catalog: AlbionAbilityCatalog) -> str:
    return f"{catalog.id}@{catalog.version}:{len(catalog.abilities)}"
