from __future__ import annotations

import json
from functools import lru_cache
from pathlib import Path
from typing import Any

from pydantic import BaseModel, Field

from montage_backend.analysis.albion.bomb.albion_bomb_analysis import DEFAULT_WINDOW_MS

PACKAGE_CONFIG_DIR = Path(__file__).resolve().parent / "presets"
REPO_CONFIG_DIR = Path(__file__).resolve().parents[6] / "ai" / "plugins" / "albion" / "bombs"


class AlbionBombConfig(BaseModel):
    id: str = "albion-bomb-default"
    version: str = "1.0"
    bomb_min_kills: int = Field(default=3, ge=1)
    bomb_kill_window_ms: int = Field(default=2000, ge=500)
    sample_interval_ms: int = Field(default=2000, ge=250)
    window_ms: int = Field(default=DEFAULT_WINDOW_MS, ge=250)
    motion_threshold: float = Field(default=0.35, ge=0.0, le=1.0)
    audio_peak_threshold: float = Field(default=0.4, ge=0.0, le=1.0)
    min_fusion_score: float = Field(default=0.45, ge=0.0, le=1.0)
    ocr_weight: float = Field(default=0.4, ge=0.0, le=1.0)
    motion_weight: float = Field(default=0.2, ge=0.0, le=1.0)
    audio_weight: float = Field(default=0.2, ge=0.0, le=1.0)
    ability_weight: float = Field(default=0.2, ge=0.0, le=1.0)


BUILTIN_CONFIG = AlbionBombConfig()


def _parse_config_payload(payload: dict[str, Any]) -> AlbionBombConfig:
    return AlbionBombConfig(
        id=str(payload.get("id", "albion-bomb-custom")),
        version=str(payload.get("version", "1.0")),
        bomb_min_kills=int(payload.get("bomb_min_kills", 3)),
        bomb_kill_window_ms=int(payload.get("bomb_kill_window_ms", 2000)),
        sample_interval_ms=int(payload.get("sample_interval_ms", 2000)),
        window_ms=int(payload.get("window_ms", DEFAULT_WINDOW_MS)),
        motion_threshold=float(payload.get("motion_threshold", 0.35)),
        audio_peak_threshold=float(payload.get("audio_peak_threshold", 0.4)),
        min_fusion_score=float(payload.get("min_fusion_score", 0.45)),
        ocr_weight=float(payload.get("ocr_weight", 0.4)),
        motion_weight=float(payload.get("motion_weight", 0.2)),
        audio_weight=float(payload.get("audio_weight", 0.2)),
        ability_weight=float(payload.get("ability_weight", 0.2)),
    )


def _load_config_file(path: Path) -> AlbionBombConfig | None:
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


def get_bomb_config(config_id: str | None = None) -> AlbionBombConfig:
    if config_id is None or config_id == BUILTIN_CONFIG.id:
        return BUILTIN_CONFIG
    for directory in (PACKAGE_CONFIG_DIR, REPO_CONFIG_DIR):
        for suffix in (".json", ".yaml", ".yml"):
            loaded = _load_config_file(directory / f"{config_id}{suffix}")
            if loaded is not None:
                return loaded
    return BUILTIN_CONFIG


def config_cache_token(config: AlbionBombConfig) -> str:
    return f"{config.id}@{config.version}"
