from __future__ import annotations

import json
from functools import lru_cache
from pathlib import Path
from typing import Any

from pydantic import BaseModel, Field

from montage_backend.analysis.albion.combat.albion_combat_analysis import DEFAULT_WINDOW_MS

PACKAGE_CONFIG_DIR = Path(__file__).resolve().parent / "presets"
REPO_CONFIG_DIR = Path(__file__).resolve().parents[6] / "ai" / "plugins" / "albion" / "combat"


class AlbionCombatConfig(BaseModel):
    id: str = "albion-combat-default"
    version: str = "1.0"
    fight_activity_threshold: float = Field(default=0.35, ge=0.0, le=1.0)
    fight_min_duration_ms: int = Field(default=3000, ge=500)
    fight_gap_ms: int = Field(default=5000, ge=500)
    retreat_gap_ms: int = Field(default=4000, ge=500)
    sample_interval_ms: int = Field(default=2000, ge=250)
    window_ms: int = Field(default=DEFAULT_WINDOW_MS, ge=250)


BUILTIN_CONFIG = AlbionCombatConfig()


def _parse_config_payload(payload: dict[str, Any]) -> AlbionCombatConfig:
    return AlbionCombatConfig(
        id=str(payload.get("id", "albion-combat-custom")),
        version=str(payload.get("version", "1.0")),
        fight_activity_threshold=float(payload.get("fight_activity_threshold", 0.35)),
        fight_min_duration_ms=int(payload.get("fight_min_duration_ms", 3000)),
        fight_gap_ms=int(payload.get("fight_gap_ms", 5000)),
        retreat_gap_ms=int(payload.get("retreat_gap_ms", 4000)),
        sample_interval_ms=int(payload.get("sample_interval_ms", 2000)),
        window_ms=int(payload.get("window_ms", DEFAULT_WINDOW_MS)),
    )


def _load_config_file(path: Path) -> AlbionCombatConfig | None:
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
    return _parse_config_payload(payload)


@lru_cache(maxsize=8)
def list_config_ids() -> tuple[str, ...]:
    ids = {BUILTIN_CONFIG.id}
    for directory in (PACKAGE_CONFIG_DIR, REPO_CONFIG_DIR):
        if not directory.exists():
            continue
        for path in directory.glob("*"):
            if path.suffix.lower() in {".json", ".yaml", ".yml"}:
                ids.add(path.stem.replace("_config", ""))
    return tuple(sorted(ids))


def get_combat_config(config_id: str | None = None) -> AlbionCombatConfig:
    if config_id is None or config_id == BUILTIN_CONFIG.id:
        return BUILTIN_CONFIG
    for directory in (PACKAGE_CONFIG_DIR, REPO_CONFIG_DIR):
        for suffix in (".json", ".yaml", ".yml"):
            loaded = _load_config_file(directory / f"{config_id}{suffix}")
            if loaded is not None:
                return loaded
    return BUILTIN_CONFIG


def config_cache_token(config: AlbionCombatConfig) -> str:
    return f"{config.id}@{config.version}"
