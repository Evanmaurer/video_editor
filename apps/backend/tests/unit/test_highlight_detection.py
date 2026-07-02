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
from montage_backend.montage.base import MontagePlanContext, MontagePlanState
from montage_backend.montage.highlight_detection import (
    build_cache_key,
    collect_signal_points,
    detect_clip_highlights,
    merge_intervals,
)
from montage_backend.montage.modules.highlights import HighlightDetectionModule
from montage_backend.montage.registry import build_default_montage_registry


def _media() -> MediaItem:
    now = utc_now_iso()
    return MediaItem(
        id="media-hl-1",
        project_id="project-1",
        file_path="/tmp/fight.mp4",
        file_name="fight.mp4",
        media_type=MediaType.VIDEO,
        role=MediaRole.CLIP,
        storage_mode=StorageMode.COPY,
        import_status=ImportStatus.READY,
        proxy_status=ProcessingStatus.READY,
        waveform_status=ProcessingStatus.READY,
        scene_status=ProcessingStatus.READY,
        metadata_status=ProcessingStatus.READY,
        duration_ms=12000,
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
        media_id="media-hl-1",
        module_id=module_id,
        analyzer_version=f"{module_id}-v1",
        cache_key=f"{module_id}:test",
        status=ProcessingStatus.READY,
        payload=payload,
        confidence=0.9,
        source_fingerprint="fp-hl",
        created_at=now,
        updated_at=now,
    )


def _action_record():
    motion_payload = {
        "analyzer_version": "motion-analyzer-v1.0",
        "cache_key": "motion:test",
        "frame_rate": 60.0,
        "duration_ms": 12000,
        "window_ms": 1000,
        "sample_stride_frames": 30,
        "summary": {
            "overall_motion_score": 0.78,
            "dominant_movement_class": "fast",
            "static_ratio": 0.1,
            "slow_ratio": 0.2,
            "fast_ratio": 0.7,
            "average_shake": 0.5,
            "average_pan": 0.3,
        },
        "windows": [
            {
                "start_ms": 3000,
                "end_ms": 4000,
                "start_frame": 180,
                "end_frame": 240,
                "duration_ms": 1000,
                "motion_score": 0.85,
                "motion_intensity": 0.8,
                "movement_class": "fast",
                "camera_movement": {"pan": 0.3, "zoom": 0.1, "shake": 0.5},
                "confidence": 0.9,
            },
            {
                "start_ms": 8000,
                "end_ms": 9000,
                "start_frame": 480,
                "end_frame": 540,
                "duration_ms": 1000,
                "motion_score": 0.72,
                "motion_intensity": 0.7,
                "movement_class": "fast",
                "camera_movement": {"pan": 0.2, "zoom": 0.0, "shake": 0.4},
                "confidence": 0.88,
            },
        ],
    }
    audio_payload = {
        "analyzer_version": "audio-analyzer-v1.0",
        "cache_key": "audio:test",
        "duration_ms": 12000,
        "sample_count": 1000,
        "window_ms": 1000,
        "has_audio": True,
        "summary": {
            "dynamic_range_db": 20.0,
            "silence_ratio": 0.1,
            "peak_count": 3,
            "beat_count": 2,
        },
        "events": [
            {
                "timestamp_ms": 3500,
                "event_type": "peak",
                "value": 0.9,
                "confidence": 0.95,
                "metadata": {},
            },
            {
                "timestamp_ms": 8200,
                "event_type": "beat",
                "value": 0.7,
                "confidence": 0.8,
                "metadata": {},
            },
        ],
        "loudness_windows": [],
        "peaks": [],
    }
    ocr_payload = {
        "analyzer_version": "ocr-analyzer-v1.0",
        "cache_key": "ocr:test",
        "duration_ms": 12000,
        "frame_rate": 60.0,
        "sample_interval_ms": 500,
        "summary": {
            "frames_sampled": 24,
            "detection_count": 4,
            "unique_text_count": 3,
            "engine_id": "tesseract",
            "engine_version": "1.0",
            "by_category": {"combat_text": 2, "damage_number": 1},
        },
        "detections": [
            {
                "text": "Slain",
                "category": "combat_text",
                "timestamp_ms": 3600,
                "frame": 216,
                "confidence": 0.92,
            },
            {
                "text": "1.2k",
                "category": "damage_number",
                "timestamp_ms": 3650,
                "frame": 219,
                "confidence": 0.88,
            },
        ],
        "unique_texts": [],
    }
    return build_clip_analysis_record(
        project_id="project-1",
        media=_media(),
        metadata=None,
        caches=[
            _cache(AnalysisModuleId.MOTION.value, payload=motion_payload),
            _cache(AnalysisModuleId.AUDIO.value, payload=audio_payload),
            _cache(AnalysisModuleId.OCR.value, payload=ocr_payload),
        ],
        embedding_vector_count=0,
        source_fingerprint="fp-hl",
    )


def test_collect_signal_points_from_motion_audio_and_ocr():
    record = _action_record()
    points = collect_signal_points(record)
    keys = {point.signal_key for point in points}
    assert "motion" in keys
    assert "audio" in keys
    assert "ocr" in keys
    assert len(points) >= 5


def test_merge_intervals_combines_nearby_windows():
    from montage_backend.montage.highlight_detection import TimeInterval

    merged = merge_intervals(
        [
            TimeInterval(start_ms=3000, end_ms=4500),
            TimeInterval(start_ms=4700, end_ms=6200),
        ],
    )
    assert len(merged) == 1
    assert merged[0].start_ms == 3000
    assert merged[0].end_ms == 6200


def test_detect_clip_highlights_returns_scored_segments():
    record = _action_record()
    result = detect_clip_highlights(
        project_id="project-1",
        media_id="media-hl-1",
        record=record,
        file_name="fight.mp4",
        updated_at=utc_now_iso(),
    )
    assert result.highlight_count >= 1
    assert result.cache_key == build_cache_key("fp-hl")
    top = result.highlights[0]
    assert top.start_ms >= 0
    assert top.end_ms > top.start_ms
    assert 0.0 <= top.score <= 100.0
    assert 0.0 <= top.confidence <= 1.0
    assert top.reasoning
    assert top.signals


def test_detect_clip_highlights_separates_distant_action():
    record = _action_record()
    result = detect_clip_highlights(
        project_id="project-1",
        media_id="media-hl-1",
        record=record,
        updated_at=utc_now_iso(),
    )
    assert result.highlight_count >= 2


@pytest.mark.asyncio
async def test_highlight_detection_module_plan():
    record = _action_record()
    module = HighlightDetectionModule()
    ctx = MontagePlanContext(
        project_id="project-1",
        plan_id="plan-1",
        random_seed=42,
        extras={"clip_records": [record]},
    )
    output = await module.plan(ctx, MontagePlanState())
    assert output.module_id == "highlights"
    assert output.payload["highlight_count"] >= 1
    assert output.payload["clips"][0]["highlight_count"] >= 1


def test_default_registry_registers_highlights():
    registry = build_default_montage_registry()
    module = registry.get("highlights")
    assert module.module_id.value == "highlights"
