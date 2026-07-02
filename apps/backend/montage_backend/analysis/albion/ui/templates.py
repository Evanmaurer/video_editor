from __future__ import annotations

import json
from functools import lru_cache
from pathlib import Path
from typing import Any

from pydantic import BaseModel, Field

from montage_backend.analysis.albion.ui.albion_ui_analysis import AlbionUiElementType

PACKAGE_TEMPLATE_DIR = Path(__file__).resolve().parent / "presets"
REPO_TEMPLATE_DIR = (
    Path(__file__).resolve().parents[6] / "ai" / "plugins" / "albion" / "templates"
)


class AlbionUiRegionTemplate(BaseModel):
    element_type: AlbionUiElementType
    x: float = Field(ge=0.0, le=1.0)
    y: float = Field(ge=0.0, le=1.0)
    width: float = Field(gt=0.0, le=1.0)
    height: float = Field(gt=0.0, le=1.0)
    detector: str = "auto"


class AlbionUiTemplate(BaseModel):
    id: str
    game_id: str = "albion"
    resolution: tuple[int, int]
    ui_scale: float = 1.0
    regions: dict[str, AlbionUiRegionTemplate] = Field(default_factory=dict)
    thresholds: dict[str, float | int] = Field(default_factory=dict)


def _region(
    element_type: AlbionUiElementType,
    x: float,
    y: float,
    width: float,
    height: float,
    *,
    detector: str = "auto",
) -> AlbionUiRegionTemplate:
    return AlbionUiRegionTemplate(
        element_type=element_type,
        x=x,
        y=y,
        width=width,
        height=height,
        detector=detector,
    )


_DEFAULT_1080P_REGIONS = {
    "kill_feed": _region(AlbionUiElementType.KILL_FEED, 0.78, 0.05, 0.20, 0.40, detector="edge_density"),
    "party_frame": _region(
        AlbionUiElementType.PARTY_FRAME,
        0.0,
        0.12,
        0.16,
        0.55,
        detector="stack_contours",
    ),
    "minimap": _region(AlbionUiElementType.MINIMAP, 0.78, 0.72, 0.22, 0.28, detector="edge_density"),
    "health_bar": _region(
        AlbionUiElementType.HEALTH_BAR,
        0.40,
        0.90,
        0.20,
        0.05,
        detector="color_bars",
    ),
    "ability_bar": _region(
        AlbionUiElementType.ABILITY_BAR,
        0.35,
        0.85,
        0.30,
        0.10,
        detector="edge_density",
    ),
    "chat_panel": _region(AlbionUiElementType.CHAT_PANEL, 0.0, 0.55, 0.28, 0.30, detector="panel_edges"),
    "resource_bar": _region(
        AlbionUiElementType.RESOURCE_BAR,
        0.35,
        0.96,
        0.30,
        0.03,
        detector="color_bars",
    ),
}

BUILTIN_TEMPLATES: dict[str, AlbionUiTemplate] = {
    "albion_1080p_default": AlbionUiTemplate(
        id="albion_1080p_default",
        resolution=(1920, 1080),
        ui_scale=1.0,
        regions=_DEFAULT_1080P_REGIONS,
        thresholds={
            "bomb_min_kills": 3,
            "bomb_kill_window_ms": 2000,
            "wipe_min_deaths": 5,
            "wipe_window_ms": 3000,
            "engagement_min_duration_ms": 5000,
        },
    ),
    "albion_1440p_default": AlbionUiTemplate(
        id="albion_1440p_default",
        resolution=(2560, 1440),
        ui_scale=1.0,
        regions=dict(_DEFAULT_1080P_REGIONS),
    ),
    "albion_1080p_125": AlbionUiTemplate(
        id="albion_1080p_125",
        resolution=(1920, 1080),
        ui_scale=1.25,
        regions=dict(_DEFAULT_1080P_REGIONS),
    ),
    "albion_1080p_150": AlbionUiTemplate(
        id="albion_1080p_150",
        resolution=(1920, 1080),
        ui_scale=1.5,
        regions=dict(_DEFAULT_1080P_REGIONS),
    ),
}


def _parse_template_payload(payload: dict[str, Any]) -> AlbionUiTemplate:
    regions: dict[str, AlbionUiRegionTemplate] = {}
    for name, region in payload.get("regions", {}).items():
        element_type = AlbionUiElementType(region.get("element_type", name))
        regions[name] = AlbionUiRegionTemplate(
            element_type=element_type,
            x=float(region["x"]),
            y=float(region["y"]),
            width=float(region["width"]),
            height=float(region["height"]),
            detector=str(region.get("detector", "auto")),
        )
    resolution = payload.get("resolution", [1920, 1080])
    return AlbionUiTemplate(
        id=str(payload["id"]),
        game_id=str(payload.get("game_id", "albion")),
        resolution=(int(resolution[0]), int(resolution[1])),
        ui_scale=float(payload.get("ui_scale", 1.0)),
        regions=regions,
        thresholds={key: value for key, value in payload.get("thresholds", {}).items()},
    )


def _load_template_file(path: Path) -> AlbionUiTemplate | None:
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
    return _parse_template_payload(payload)


@lru_cache(maxsize=16)
def list_template_ids() -> tuple[str, ...]:
    ids = set(BUILTIN_TEMPLATES)
    for directory in (PACKAGE_TEMPLATE_DIR, REPO_TEMPLATE_DIR):
        if not directory.exists():
            continue
        for path in directory.glob("*"):
            if path.suffix.lower() in {".json", ".yaml", ".yml"}:
                ids.add(path.stem)
    return tuple(sorted(ids))


def get_template(template_id: str) -> AlbionUiTemplate | None:
    builtin = BUILTIN_TEMPLATES.get(template_id)
    if builtin is not None:
        return builtin
    for directory in (PACKAGE_TEMPLATE_DIR, REPO_TEMPLATE_DIR):
        for suffix in (".json", ".yaml", ".yml"):
            loaded = _load_template_file(directory / f"{template_id}{suffix}")
            if loaded is not None:
                return loaded
    return None


def resolve_template(
    *,
    frame_width: int,
    frame_height: int,
    template_id: str | None = None,
) -> AlbionUiTemplate:
    if template_id:
        explicit = get_template(template_id)
        if explicit is not None:
            return explicit

    candidates = [get_template(item) for item in list_template_ids()]
    templates = [item for item in candidates if item is not None]
    if not templates:
        return BUILTIN_TEMPLATES["albion_1080p_default"]

    def score(template: AlbionUiTemplate) -> float:
        target_w, target_h = template.resolution
        size_delta = abs(target_w - frame_width) + abs(target_h - frame_height)
        aspect_delta = abs((target_w / target_h) - (frame_width / max(frame_height, 1)))
        scale_penalty = abs(template.ui_scale - 1.0) * 500.0
        default_penalty = 0.0 if template.id.endswith("_default") else 25.0
        return size_delta + aspect_delta * 1000.0 + scale_penalty + default_penalty

    return min(templates, key=score)


def region_to_pixels(
    region: AlbionUiRegionTemplate,
    *,
    frame_width: int,
    frame_height: int,
) -> tuple[int, int, int, int]:
    x = int(frame_width * region.x)
    y = int(frame_height * region.y)
    width = max(int(frame_width * region.width), 1)
    height = max(int(frame_height * region.height), 1)
    return x, y, width, height
