from __future__ import annotations

import math
from enum import Enum

from pydantic import BaseModel, Field

from montage_backend.analysis.embedding.engine import EmbeddingEngine
from montage_backend.models.domain import new_uuid


class EmbeddingScopeType(str, Enum):
    CLIP = "clip"
    SCENE = "scene"
    KEYFRAME = "keyframe"


class SceneSegmentRef(BaseModel):
    start_ms: int
    end_ms: int
    index: int


class EmbeddingVectorRecord(BaseModel):
    id: str
    scope_type: EmbeddingScopeType
    scope_id: str
    timestamp_ms: int | None = None
    start_ms: int | None = None
    end_ms: int | None = None
    vector: list[float]
    dimensions: int


class EmbeddingAnalysisSummary(BaseModel):
    model_id: str
    dimensions: int
    clip_embedding_id: str | None = None
    scene_count: int = 0
    keyframe_count: int = 0
    total_embeddings: int = 0


class EmbeddingAnalysisResult(BaseModel):
    analyzer_version: str
    cache_key: str
    duration_ms: int
    frame_rate: float
    summary: EmbeddingAnalysisSummary
    embedding_ids: list[str] = Field(default_factory=list)
    embeddings: list[EmbeddingVectorRecord] = Field(default_factory=list)


class EmbeddingMatch(BaseModel):
    embedding_id: str
    media_id: str
    scope_type: EmbeddingScopeType
    scope_id: str
    similarity: float = Field(ge=-1.0, le=1.0)
    timestamp_ms: int | None = None
    start_ms: int | None = None
    end_ms: int | None = None


class SemanticSearchRequest(BaseModel):
    query: str
    scope_type: EmbeddingScopeType = EmbeddingScopeType.CLIP
    top_k: int = Field(default=10, ge=1, le=100)


class SemanticSearchResponse(BaseModel):
    query: str
    model_id: str
    matches: list[EmbeddingMatch] = Field(default_factory=list)


def cosine_similarity(left: list[float], right: list[float]) -> float:
    if len(left) != len(right) or not left:
        return 0.0
    dot = sum(a * b for a, b in zip(left, right, strict=True))
    left_norm = math.sqrt(sum(a * a for a in left))
    right_norm = math.sqrt(sum(b * b for b in right))
    if left_norm <= 0 or right_norm <= 0:
        return 0.0
    return round(dot / (left_norm * right_norm), 6)


def keyframe_timestamps(duration_ms: int, *, interval_ms: int, max_frames: int) -> list[int]:
    if duration_ms <= 0:
        return [0]
    timestamps = list(range(0, duration_ms, max(interval_ms, 1)))
    if timestamps[-1] < duration_ms - 1:
        timestamps.append(max(0, duration_ms - 1))
    return timestamps[:max_frames]


def scene_segment_refs(segments: list[dict] | None, duration_ms: int) -> list[SceneSegmentRef]:
    if segments:
        refs: list[SceneSegmentRef] = []
        for index, segment in enumerate(segments):
            refs.append(
                SceneSegmentRef(
                    start_ms=int(segment["start_ms"]),
                    end_ms=int(segment["end_ms"]),
                    index=index,
                ),
            )
        return refs

    fallback: list[SceneSegmentRef] = []
    window_ms = max(duration_ms // 4, 1000)
    start_ms = 0
    index = 0
    while start_ms < duration_ms:
        end_ms = min(start_ms + window_ms, duration_ms)
        fallback.append(SceneSegmentRef(start_ms=start_ms, end_ms=end_ms, index=index))
        if end_ms >= duration_ms:
            break
        start_ms = end_ms
        index += 1
    return fallback


def build_embedding_records(
    *,
    media_id: str,
    engine: EmbeddingEngine,
    clip_vector: list[float],
    scene_vectors: list[tuple[SceneSegmentRef, list[float]]],
    keyframe_vectors: list[tuple[int, list[float]]],
) -> list[EmbeddingVectorRecord]:
    records: list[EmbeddingVectorRecord] = [
        EmbeddingVectorRecord(
            id=new_uuid(),
            scope_type=EmbeddingScopeType.CLIP,
            scope_id=media_id,
            timestamp_ms=None,
            start_ms=0,
            end_ms=None,
            vector=clip_vector,
            dimensions=engine.dimensions,
        ),
    ]

    for segment, vector in scene_vectors:
        records.append(
            EmbeddingVectorRecord(
                id=new_uuid(),
                scope_type=EmbeddingScopeType.SCENE,
                scope_id=f"scene-{segment.index}",
                timestamp_ms=(segment.start_ms + segment.end_ms) // 2,
                start_ms=segment.start_ms,
                end_ms=segment.end_ms,
                vector=vector,
                dimensions=engine.dimensions,
            ),
        )

    for timestamp_ms, vector in keyframe_vectors:
        records.append(
            EmbeddingVectorRecord(
                id=new_uuid(),
                scope_type=EmbeddingScopeType.KEYFRAME,
                scope_id=f"keyframe-{timestamp_ms}",
                timestamp_ms=timestamp_ms,
                start_ms=timestamp_ms,
                end_ms=timestamp_ms,
                vector=vector,
                dimensions=engine.dimensions,
            ),
        )

    return records


def build_embedding_analysis_result(
    *,
    analyzer_version: str,
    cache_key: str,
    duration_ms: int,
    frame_rate: float,
    engine: EmbeddingEngine,
    records: list[EmbeddingVectorRecord],
) -> EmbeddingAnalysisResult:
    clip_id = next((record.id for record in records if record.scope_type == EmbeddingScopeType.CLIP), None)
    scene_count = sum(1 for record in records if record.scope_type == EmbeddingScopeType.SCENE)
    keyframe_count = sum(1 for record in records if record.scope_type == EmbeddingScopeType.KEYFRAME)
    summary = EmbeddingAnalysisSummary(
        model_id=engine.model_id,
        dimensions=engine.dimensions,
        clip_embedding_id=clip_id,
        scene_count=scene_count,
        keyframe_count=keyframe_count,
        total_embeddings=len(records),
    )
    return EmbeddingAnalysisResult(
        analyzer_version=analyzer_version,
        cache_key=cache_key,
        duration_ms=duration_ms,
        frame_rate=frame_rate,
        summary=summary,
        embedding_ids=[record.id for record in records],
        embeddings=records,
    )


def cache_payload_from_result(result: EmbeddingAnalysisResult) -> dict:
    payload = result.model_dump()
    payload.pop("embeddings", None)
    return payload
