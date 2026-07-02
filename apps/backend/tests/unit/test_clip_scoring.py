from __future__ import annotations

import pytest

from montage_backend.analysis.base import AnalysisModuleId
from montage_backend.analysis.clip_analysis_aggregation import build_clip_analysis_record
from montage_backend.models.domain import utc_now_iso
from montage_backend.models.domain.analysis import AnalysisModuleCacheRecord
from montage_backend.models.domain.media import (
    ImportStatus,
    MediaItem,
    MediaRole,
    MediaType,
    ProcessingStatus,
    StorageMode,
)
from montage_backend.models.domain.metadata import MetadataFeatureKey, MetadataFeatureRecord
from montage_backend.montage.base import MontagePlanContext, MontagePlanState
from montage_backend.montage.clip_scoring import (
    build_cache_key,
    compute_confidence,
    compute_montage_score,
    score_clip_analysis,
    score_motion,
)
from montage_backend.montage.modules.scoring import ClipScoringModule
from montage_backend.montage.registry import build_default_montage_registry
from montage_backend.services.analysis_service import AnalysisService


def _media() -> MediaItem:
    now = utc_now_iso()
    return MediaItem(
        id="media-score-1",
        project_id="project-1",
        file_path="/tmp/highlight.mp4",
        file_name="highlight.mp4",
        media_type=MediaType.VIDEO,
        role=MediaRole.CLIP,
        storage_mode=StorageMode.COPY,
        import_status=ImportStatus.READY,
        proxy_status=ProcessingStatus.READY,
        waveform_status=ProcessingStatus.READY,
        scene_status=ProcessingStatus.READY,
        metadata_status=ProcessingStatus.READY,
        duration_ms=8000,
        width=1920,
        height=1080,
        frame_rate=60.0,
        created_at=now,
        updated_at=now,
    )


def _cache(module_id: str, *, payload: dict):
    now = utc_now_iso()
    return AnalysisModuleCacheRecord(
        id=f"cache-{module_id}",
        media_id="media-score-1",
        module_id=module_id,
        analyzer_version=f"{module_id}-v1",
        cache_key=f"{module_id}:test",
        status=ProcessingStatus.READY,
        payload=payload,
        confidence=0.9,
        source_fingerprint="fp-score",
        created_at=now,
        updated_at=now,
    )


def _rich_analysis_record():
    scene_payload = {
        "analyzer_version": "scene-analyzer-v1.0",
        "cache_key": "scene:test",
        "frame_rate": 60.0,
        "frame_count": 480,
        "duration_ms": 8000,
        "events": [],
        "segments": [
            {
                "start_frame": 0,
                "end_frame": 119,
                "start_ms": 0,
                "end_ms": 2000,
                "duration_ms": 2000,
                "confidence": 1.0,
            },
            {
                "start_frame": 120,
                "end_frame": 239,
                "start_ms": 2000,
                "end_ms": 4000,
                "duration_ms": 2000,
                "confidence": 1.0,
            },
        ],
    }
    motion_payload = {
        "analyzer_version": "motion-analyzer-v1.0",
        "cache_key": "motion:test",
        "frame_rate": 60.0,
        "duration_ms": 8000,
        "window_ms": 1000,
        "sample_stride_frames": 30,
        "summary": {
            "overall_motion_score": 0.82,
            "dominant_movement_class": "fast",
            "static_ratio": 0.1,
            "slow_ratio": 0.2,
            "fast_ratio": 0.7,
            "average_shake": 0.55,
            "average_pan": 0.3,
        },
        "windows": [],
    }
    audio_payload = {
        "analyzer_version": "audio-analyzer-v1.0",
        "cache_key": "audio:test",
        "duration_ms": 8000,
        "has_audio": True,
        "summary": {
            "peak_count": 6,
            "silence_ratio": 0.15,
            "dynamic_range_db": 18.0,
            "average_rms_db": -18.0,
        },
        "peaks": [],
        "silence_regions": [],
    }
    ocr_payload = {
        "analyzer_version": "ocr-analyzer-v1.0",
        "cache_key": "ocr:test",
        "duration_ms": 8000,
        "frame_rate": 60.0,
        "sample_interval_ms": 500,
        "summary": {
            "frames_sampled": 16,
            "detection_count": 12,
            "unique_text_count": 5,
            "engine_id": "tesseract",
            "engine_version": "1.0",
            "by_category": {"combat_text": 2, "damage_number": 3},
        },
        "detections": [],
        "unique_texts": [],
    }
    metadata_records = [
        MetadataFeatureRecord(
            media_id="media-score-1",
            feature_key=MetadataFeatureKey.VISUAL,
            status=ProcessingStatus.READY,
            payload={
                "motion_score": 0.82,
                "camera_movement": {"label": "fast", "pan": 0.3, "zoom": 0.1, "shake": 0.55},
                "brightness": {"mean": 138, "min": 0, "max": 255, "std": 12},
                "color_histogram": {"bins": 16, "r": [], "g": [], "b": []},
                "blur_score": 0.08,
                "sharpness": 0.86,
            },
            source_fingerprint="fp-score",
            created_at=utc_now_iso(),
            updated_at=utc_now_iso(),
        ),
    ]
    metadata = AnalysisService._build_metadata_summary("media-score-1", metadata_records)
    return build_clip_analysis_record(
        project_id="project-1",
        media=_media(),
        metadata=metadata,
        caches=[
            _cache(AnalysisModuleId.SCENE.value, payload=scene_payload),
            _cache(AnalysisModuleId.MOTION.value, payload=motion_payload),
            _cache(AnalysisModuleId.AUDIO.value, payload=audio_payload),
            _cache(AnalysisModuleId.OCR.value, payload=ocr_payload),
        ],
        embedding_vector_count=0,
        source_fingerprint="fp-score",
    )


def test_score_motion_prefers_motion_module():
    record = _rich_analysis_record()
    score, reasoning, available = score_motion(record)
    assert available is True
    assert score == pytest.approx(82.0)
    assert "0.82" in reasoning


def test_score_clip_analysis_returns_weighted_score_and_reasoning():
    record = _rich_analysis_record()
    score = score_clip_analysis(
        project_id="project-1",
        media_id="media-score-1",
        record=record,
        file_name="highlight.mp4",
        updated_at=utc_now_iso(),
    )
    assert 0.0 <= score.montage_score <= 100.0
    assert score.confidence >= 0.8
    assert "Montage score" in score.reasoning
    assert score.breakdown.motion.score == pytest.approx(82.0)
    assert score.cache_key == build_cache_key("fp-score")
    assert compute_montage_score(score.breakdown) == pytest.approx(score.montage_score)


def test_compute_confidence_from_availability():
    assert compute_confidence([True, True, False, True]) == pytest.approx(0.75)


@pytest.mark.asyncio
async def test_clip_scoring_module_plan():
    record = _rich_analysis_record()
    module = ClipScoringModule()
    ctx = MontagePlanContext(
        project_id="project-1",
        plan_id="plan-1",
        random_seed=99,
        extras={"clip_records": [record]},
    )
    output = await module.plan(ctx, MontagePlanState())
    assert output.module_id == "scoring"
    assert output.payload["clip_count"] == 1
    assert output.payload["scores"][0]["montage_score"] >= 0.0


def test_default_registry_registers_scoring():
    registry = build_default_montage_registry()
    module = registry.get("scoring")
    assert module.module_id.value == "scoring"
