from __future__ import annotations

import re
from enum import Enum

from pydantic import BaseModel, Field

from montage_backend.analysis.ocr.engine import OcrEngine, RawOcrDetection
from montage_backend.analysis.scene_detection import ms_to_frame

GUILD_TAG_RE = re.compile(r"^\[([^\]]+)\]")
PLAYER_LINE_RE = re.compile(r"^\[([^\]]+)\]\s+([A-Za-z0-9_\- ]+)$")
DAMAGE_NUMBER_RE = re.compile(r"^[\d,\.]+\s*[kKmM]?$")
COMBAT_KEYWORD_RE = re.compile(r"\b(killed|slain|defeated|loot|victory|assist)\b", re.IGNORECASE)
CHAT_LINE_RE = re.compile(r"^[A-Za-z0-9_\-]{2,16}:\s+.+")
HUD_LABEL_RE = re.compile(r"^[A-Z0-9 %\-\+\/\.]{2,24}$")


class OcrTextCategory(str, Enum):
    HUD = "hud_text"
    COMBAT = "combat_text"
    PLAYER_NAME = "player_name"
    GUILD_NAME = "guild_name"
    CHAT = "chat"
    DAMAGE_NUMBER = "damage_number"
    UNKNOWN = "unknown"


class OcrBoundingBox(BaseModel):
    x: int
    y: int
    width: int
    height: int


class OcrDetection(BaseModel):
    text: str
    category: OcrTextCategory
    timestamp_ms: int
    frame: int
    confidence: float = Field(ge=0.0, le=1.0)
    bbox: OcrBoundingBox | None = None
    metadata: dict = Field(default_factory=dict)


class OcrAnalysisSummary(BaseModel):
    frames_sampled: int
    detection_count: int
    unique_text_count: int
    engine_id: str
    engine_version: str
    by_category: dict[str, int] = Field(default_factory=dict)


class OcrAnalysisResult(BaseModel):
    analyzer_version: str
    cache_key: str
    duration_ms: int
    frame_rate: float
    sample_interval_ms: int
    summary: OcrAnalysisSummary
    detections: list[OcrDetection] = Field(default_factory=list)
    unique_texts: list[str] = Field(default_factory=list)


def normalize_ocr_text(text: str) -> str:
    return " ".join(text.strip().split()).lower()


def classify_ocr_text(text: str) -> OcrTextCategory:
    cleaned = " ".join(text.strip().split())
    if not cleaned:
        return OcrTextCategory.UNKNOWN

    if DAMAGE_NUMBER_RE.match(cleaned):
        return OcrTextCategory.DAMAGE_NUMBER

    if COMBAT_KEYWORD_RE.search(cleaned):
        return OcrTextCategory.COMBAT

    if CHAT_LINE_RE.match(cleaned):
        return OcrTextCategory.CHAT

    guild_match = GUILD_TAG_RE.match(cleaned)
    if guild_match is not None:
        if " killed " in cleaned.lower() or " slain " in cleaned.lower():
            return OcrTextCategory.COMBAT
        if PLAYER_LINE_RE.match(cleaned):
            return OcrTextCategory.PLAYER_NAME
        return OcrTextCategory.GUILD_NAME

    if HUD_LABEL_RE.match(cleaned):
        return OcrTextCategory.HUD

    if cleaned.istitle() and 2 <= len(cleaned.split()) <= 3:
        return OcrTextCategory.PLAYER_NAME

    if len(cleaned) >= 24 and " " in cleaned:
        return OcrTextCategory.CHAT

    return OcrTextCategory.UNKNOWN


def sample_timestamps_ms(
    duration_ms: int,
    *,
    interval_ms: int,
    max_frames: int,
) -> list[int]:
    if duration_ms <= 0:
        return [0]
    timestamps = list(range(0, duration_ms, max(interval_ms, 1)))
    if not timestamps:
        timestamps = [0]
    if timestamps[-1] < duration_ms - 1:
        timestamps.append(max(0, duration_ms - 1))
    return timestamps[:max_frames]


def raw_to_detection(
    raw: RawOcrDetection,
    *,
    timestamp_ms: int,
    frame_rate: float,
) -> OcrDetection:
    bbox = None
    if raw.width > 0 and raw.height > 0:
        bbox = OcrBoundingBox(x=raw.x, y=raw.y, width=raw.width, height=raw.height)
    category = classify_ocr_text(raw.text)
    metadata: dict = {}
    guild_match = GUILD_TAG_RE.match(raw.text.strip())
    if guild_match is not None:
        metadata["guild_tag"] = guild_match.group(1)
    return OcrDetection(
        text=raw.text.strip(),
        category=category,
        timestamp_ms=timestamp_ms,
        frame=ms_to_frame(timestamp_ms, frame_rate),
        confidence=round(min(max(raw.confidence, 0.0), 1.0), 3),
        bbox=bbox,
        metadata=metadata,
    )


def dedupe_detections(detections: list[OcrDetection]) -> list[OcrDetection]:
    best_by_text: dict[str, OcrDetection] = {}
    for detection in detections:
        key = normalize_ocr_text(detection.text)
        if not key:
            continue
        existing = best_by_text.get(key)
        if existing is None or detection.confidence > existing.confidence:
            best_by_text[key] = detection
    return sorted(best_by_text.values(), key=lambda item: (item.timestamp_ms, item.text))


def build_category_counts(detections: list[OcrDetection]) -> dict[str, int]:
    counts: dict[str, int] = {category.value: 0 for category in OcrTextCategory}
    for detection in detections:
        counts[detection.category.value] += 1
    return counts


def build_ocr_analysis_result(
    *,
    analyzer_version: str,
    cache_key: str,
    duration_ms: int,
    frame_rate: float,
    sample_interval_ms: int,
    frames_sampled: int,
    engine: OcrEngine,
    detections: list[OcrDetection],
) -> OcrAnalysisResult:
    deduped = dedupe_detections(detections)
    summary = OcrAnalysisSummary(
        frames_sampled=frames_sampled,
        detection_count=len(detections),
        unique_text_count=len(deduped),
        engine_id=engine.engine_id,
        engine_version=engine.version,
        by_category=build_category_counts(detections),
    )
    return OcrAnalysisResult(
        analyzer_version=analyzer_version,
        cache_key=cache_key,
        duration_ms=duration_ms,
        frame_rate=frame_rate,
        sample_interval_ms=sample_interval_ms,
        summary=summary,
        detections=detections,
        unique_texts=[item.text for item in deduped],
    )
