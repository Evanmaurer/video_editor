from __future__ import annotations

import json
from functools import lru_cache
from pathlib import Path
from typing import Any

from pydantic import BaseModel, Field

from montage_backend.analysis.albion.engagement.albion_engagement_analysis import DEFAULT_WINDOW_MS

PACKAGE_CONFIG_DIR = Path(__file__).resolve().parent / "presets"
REPO_CONFIG_DIR = Path(__file__).resolve().parents[6] / "ai" / "plugins" / "albion" / "engagement"


class AlbionEngagementConfig(BaseModel):
    id: str = "albion-engagement-default"
    version: str = "1.0"
    engagement_min_duration_ms: int = Field(default=5000, ge=1000)
    sample_interval_ms: int = Field(default=2000, ge=250)
    window_ms: int = Field(default=DEFAULT_WINDOW_MS, ge=250)
    min_tag_confidence: float = Field(default=0.35, ge=0.0, le=1.0)
    zvz_min_kills: int = Field(default=4, ge=1)
    zvz_min_bombs: int = Field(default=1, ge=0)
    ganking_max_kills: int = Field(default=3, ge=1)
    ganking_max_span_ms: int = Field(default=20000, ge=1000)
    gathering_max_kills: int = Field(default=0, ge=0)
    gathering_max_motion_score: float = Field(default=0.3, ge=0.0, le=1.0)
    dungeon_min_sustained_combat_ms: int = Field(default=5000, ge=1000)
    dungeon_max_kills: int = Field(default=4, ge=1)
    roaming_max_kills: int = Field(default=0, ge=0)
    gathering_keywords: list[str] = Field(
        default_factory=lambda: [
            "harvested",
            "gathered",
            "mining",
            "chopped",
            "picked",
            "fishing",
            "collected",
        ],
    )


BUILTIN_CONFIG = AlbionEngagementConfig()


def _parse_config_payload(payload: dict[str, Any]) -> AlbionEngagementConfig:
    keywords = payload.get("gathering_keywords")
    return AlbionEngagementConfig(
        id=str(payload.get("id", "albion-engagement-custom")),
        version=str(payload.get("version", "1.0")),
        engagement_min_duration_ms=int(payload.get("engagement_min_duration_ms", 5000)),
        sample_interval_ms=int(payload.get("sample_interval_ms", 2000)),
        window_ms=int(payload.get("window_ms", DEFAULT_WINDOW_MS)),
        min_tag_confidence=float(payload.get("min_tag_confidence", 0.35)),
        zvz_min_kills=int(payload.get("zvz_min_kills", 4)),
        zvz_min_bombs=int(payload.get("zvz_min_bombs", 1)),
        ganking_max_kills=int(payload.get("ganking_max_kills", 3)),
        ganking_max_span_ms=int(payload.get("ganking_max_span_ms", 20000)),
        gathering_max_kills=int(payload.get("gathering_max_kills", 0)),
        gathering_max_motion_score=float(payload.get("gathering_max_motion_score", 0.3)),
        dungeon_min_sustained_combat_ms=int(payload.get("dungeon_min_sustained_combat_ms", 5000)),
        dungeon_max_kills=int(payload.get("dungeon_max_kills", 4)),
        roaming_max_kills=int(payload.get("roaming_max_kills", 0)),
        gathering_keywords=list(keywords) if isinstance(keywords, list) else BUILTIN_CONFIG.gathering_keywords,
    )


def _load_config_file(path: Path) -> AlbionEngagementConfig | None:
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


def get_engagement_config(config_id: str | None = None) -> AlbionEngagementConfig:
    if config_id is None or config_id == BUILTIN_CONFIG.id:
        return BUILTIN_CONFIG
    for directory in (PACKAGE_CONFIG_DIR, REPO_CONFIG_DIR):
        for suffix in (".json", ".yaml", ".yml"):
            loaded = _load_config_file(directory / f"{config_id}{suffix}")
            if loaded is not None:
                return loaded
    return BUILTIN_CONFIG


def config_cache_token(config: AlbionEngagementConfig) -> str:
    return f"{config.id}@{config.version}"
