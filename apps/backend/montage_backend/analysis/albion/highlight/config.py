from __future__ import annotations

import json
from functools import lru_cache
from pathlib import Path
from typing import Any

from pydantic import BaseModel, Field

from montage_backend.analysis.albion.highlight.albion_highlight_analysis import DEFAULT_WINDOW_MS

PACKAGE_CONFIG_DIR = Path(__file__).resolve().parent / "presets"
REPO_CONFIG_DIR = Path(__file__).resolve().parents[6] / "ai" / "plugins" / "albion" / "highlights"


class AlbionHighlightConfig(BaseModel):
    id: str = "albion-highlight-default"
    version: str = "1.0"
    sample_interval_ms: int = Field(default=2000, ge=250)
    window_ms: int = Field(default=DEFAULT_WINDOW_MS, ge=250)
    max_moments: int = Field(default=12, ge=1)
    bomb_quality_weight: float = Field(default=0.14, ge=0.0, le=1.0)
    kill_count_weight: float = Field(default=0.12, ge=0.0, le=1.0)
    team_fight_intensity_weight: float = Field(default=0.10, ge=0.0, le=1.0)
    player_survival_weight: float = Field(default=0.06, ge=0.0, le=1.0)
    damage_spike_weight: float = Field(default=0.08, ge=0.0, le=1.0)
    healing_spike_weight: float = Field(default=0.05, ge=0.0, le=1.0)
    visual_clarity_weight: float = Field(default=0.06, ge=0.0, le=1.0)
    motion_weight: float = Field(default=0.08, ge=0.0, le=1.0)
    audio_intensity_weight: float = Field(default=0.07, ge=0.0, le=1.0)
    fight_duration_weight: float = Field(default=0.08, ge=0.0, le=1.0)
    ocr_events_weight: float = Field(default=0.08, ge=0.0, le=1.0)
    ability_combination_weight: float = Field(default=0.08, ge=0.0, le=1.0)
    kill_reference_count: int = Field(default=5, ge=1)
    fight_duration_reference_ms: int = Field(default=15000, ge=1000)
    motion_threshold: float = Field(default=0.35, ge=0.0, le=1.0)
    audio_peak_threshold: float = Field(default=0.4, ge=0.0, le=1.0)
    healing_keywords: list[str] = Field(
        default_factory=lambda: ["healed", "healing", "regeneration", "lifesteal"],
    )


BUILTIN_CONFIG = AlbionHighlightConfig()


def _parse_config_payload(payload: dict[str, Any]) -> AlbionHighlightConfig:
    healing_keywords = payload.get("healing_keywords")
    return AlbionHighlightConfig(
        id=str(payload.get("id", "albion-highlight-custom")),
        version=str(payload.get("version", "1.0")),
        sample_interval_ms=int(payload.get("sample_interval_ms", 2000)),
        window_ms=int(payload.get("window_ms", DEFAULT_WINDOW_MS)),
        max_moments=int(payload.get("max_moments", 12)),
        bomb_quality_weight=float(payload.get("bomb_quality_weight", 0.14)),
        kill_count_weight=float(payload.get("kill_count_weight", 0.12)),
        team_fight_intensity_weight=float(payload.get("team_fight_intensity_weight", 0.10)),
        player_survival_weight=float(payload.get("player_survival_weight", 0.06)),
        damage_spike_weight=float(payload.get("damage_spike_weight", 0.08)),
        healing_spike_weight=float(payload.get("healing_spike_weight", 0.05)),
        visual_clarity_weight=float(payload.get("visual_clarity_weight", 0.06)),
        motion_weight=float(payload.get("motion_weight", 0.08)),
        audio_intensity_weight=float(payload.get("audio_intensity_weight", 0.07)),
        fight_duration_weight=float(payload.get("fight_duration_weight", 0.08)),
        ocr_events_weight=float(payload.get("ocr_events_weight", 0.08)),
        ability_combination_weight=float(payload.get("ability_combination_weight", 0.08)),
        kill_reference_count=int(payload.get("kill_reference_count", 5)),
        fight_duration_reference_ms=int(payload.get("fight_duration_reference_ms", 15000)),
        motion_threshold=float(payload.get("motion_threshold", 0.35)),
        audio_peak_threshold=float(payload.get("audio_peak_threshold", 0.4)),
        healing_keywords=list(healing_keywords)
        if isinstance(healing_keywords, list)
        else BUILTIN_CONFIG.healing_keywords,
    )


def _load_config_file(path: Path) -> AlbionHighlightConfig | None:
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


def get_highlight_config(config_id: str | None = None) -> AlbionHighlightConfig:
    if config_id is None or config_id == BUILTIN_CONFIG.id:
        return BUILTIN_CONFIG
    for directory in (PACKAGE_CONFIG_DIR, REPO_CONFIG_DIR):
        for suffix in (".json", ".yaml", ".yml"):
            loaded = _load_config_file(directory / f"{config_id}{suffix}")
            if loaded is not None:
                return loaded
    return BUILTIN_CONFIG


def config_cache_token(config: AlbionHighlightConfig) -> str:
    return f"{config.id}@{config.version}"


def factor_weights(config: AlbionHighlightConfig) -> list[tuple[str, str, float]]:
    return [
        ("bomb_quality", "Bomb quality", config.bomb_quality_weight),
        ("kill_count", "Kill count", config.kill_count_weight),
        ("team_fight_intensity", "Team fight intensity", config.team_fight_intensity_weight),
        ("player_survival", "Player survival", config.player_survival_weight),
        ("damage_spikes", "Damage spikes", config.damage_spike_weight),
        ("healing_spikes", "Healing spikes", config.healing_spike_weight),
        ("visual_clarity", "Visual clarity", config.visual_clarity_weight),
        ("motion", "Motion", config.motion_weight),
        ("audio_intensity", "Audio intensity", config.audio_intensity_weight),
        ("fight_duration", "Fight duration", config.fight_duration_weight),
        ("ocr_events", "OCR events", config.ocr_events_weight),
        ("ability_combinations", "Ability combinations", config.ability_combination_weight),
    ]
