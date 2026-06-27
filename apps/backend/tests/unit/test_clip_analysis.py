from __future__ import annotations

import pytest

from montage_backend.analysis.base import AnalysisModuleId
from montage_backend.analysis.clip_analysis_aggregation import (
    aggregate_overall_status,
    build_clip_analysis_record,
    build_clip_analysis_summary,
    build_module_status_map,
    build_project_analysis_overview,
    compute_readiness,
)
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
from montage_backend.models.domain.metadata import (
    MetadataFeatureKey,
    MetadataFeatureRecord,
)


def _media() -> MediaItem:
    now = utc_now_iso()
    return MediaItem(
        id="media-1",
        project_id="project-1",
        file_path="/tmp/video.mp4",
        file_name="video.mp4",
        media_type=MediaType.VIDEO,
        role=MediaRole.CLIP,
        storage_mode=StorageMode.COPY,
        import_status=ImportStatus.READY,
        proxy_status=ProcessingStatus.READY,
        waveform_status=ProcessingStatus.READY,
        scene_status=ProcessingStatus.READY,
        metadata_status=ProcessingStatus.READY,
        duration_ms=5000,
        width=1920,
        height=1080,
        frame_rate=60.0,
        codec="h264",
        frame_count=300,
        file_size_bytes=1000,
        proxy_path="/tmp/proxy.mp4",
        thumbnail_path="/tmp/thumb.jpg",
        waveform_path="/tmp/waveform.dat",
        created_at=now,
        updated_at=now,
    )


def _cache(module_id: str, *, status: ProcessingStatus = ProcessingStatus.READY, payload: dict | None = None):
    now = utc_now_iso()
    return AnalysisModuleCacheRecord(
        id=f"cache-{module_id}",
        media_id="media-1",
        module_id=module_id,
        analyzer_version=f"{module_id}-v1",
        cache_key=f"{module_id}:test",
        status=status,
        payload=payload or {},
        confidence=0.9,
        source_fingerprint="fp-1",
        created_at=now,
        updated_at=now,
    )


def _metadata_records() -> list[MetadataFeatureRecord]:
    now = utc_now_iso()
    return [
        MetadataFeatureRecord(
            media_id="media-1",
            feature_key=MetadataFeatureKey.VISUAL,
            status=ProcessingStatus.READY,
            payload={
                "motion_score": 0.5,
                "camera_movement": {"label": "static", "pan": 0.1, "zoom": 0.0, "shake": 0.0},
                "brightness": {"mean": 128, "min": 0, "max": 255, "std": 10},
                "color_histogram": {"bins": 16, "r": [], "g": [], "b": []},
                "blur_score": 0.1,
                "sharpness": 0.8,
            },
            source_fingerprint="fp-1",
            created_at=now,
            updated_at=now,
        ),
    ]


def test_compute_readiness_partial_modules():
    statuses = build_module_status_map(
        [
            _cache(AnalysisModuleId.SCENE.value),
            _cache(AnalysisModuleId.MOTION.value, status=ProcessingStatus.PENDING),
        ],
    )
    readiness, ready, total = compute_readiness(statuses)
    assert total == 6
    assert ready == 1
    assert readiness == pytest.approx(1 / 6)


def test_aggregate_overall_status_processing_when_partial():
    statuses = build_module_status_map([_cache(AnalysisModuleId.SCENE.value)])
    overall = aggregate_overall_status(
        import_status=ImportStatus.READY,
        module_statuses=statuses,
        metadata_status=ProcessingStatus.READY,
    )
    assert overall == ProcessingStatus.PROCESSING


def test_build_clip_analysis_summary_includes_assets_and_video():
    scene_payload = {
        "analyzer_version": "scene-analyzer-v1.0",
        "cache_key": "scene:test",
        "frame_rate": 60.0,
        "frame_count": 300,
        "duration_ms": 5000,
        "events": [],
        "segments": [{"start_frame": 0, "end_frame": 59, "start_ms": 0, "end_ms": 1000, "duration_ms": 1000, "confidence": 1.0}],
    }
    motion_payload = {
        "analyzer_version": "motion-analyzer-v1.0",
        "cache_key": "motion:test",
        "frame_rate": 60.0,
        "duration_ms": 5000,
        "window_ms": 1000,
        "sample_stride_frames": 30,
        "summary": {
            "overall_motion_score": 0.72,
            "dominant_movement_class": "slow",
            "static_ratio": 0.2,
            "slow_ratio": 0.6,
            "fast_ratio": 0.2,
            "average_shake": 0.1,
            "average_pan": 0.2,
        },
        "windows": [],
    }
    caches = [
        _cache(AnalysisModuleId.SCENE.value, payload=scene_payload),
        _cache(AnalysisModuleId.MOTION.value, payload=motion_payload),
    ]
    metadata = None
    from montage_backend.services.analysis_service import AnalysisService

    metadata = AnalysisService._build_metadata_summary("media-1", _metadata_records())

    summary = build_clip_analysis_summary(
        project_id="project-1",
        media=_media(),
        metadata=metadata,
        caches=caches,
        embedding_vector_count=3,
        source_fingerprint="fp-1",
    )
    assert summary.scene_count == 1
    assert summary.overall_motion_score == pytest.approx(0.72)
    assert summary.assets.waveform_path == "/tmp/waveform.dat"
    assert summary.video.frame_rate == 60.0
    assert summary.has_metadata is True
    assert summary.modules[AnalysisModuleId.SCENE.value].status == ProcessingStatus.READY


def test_build_clip_analysis_record_includes_module_payloads():
    scene_payload = {
        "analyzer_version": "scene-analyzer-v1.0",
        "cache_key": "scene:test",
        "frame_rate": 60.0,
        "frame_count": 300,
        "duration_ms": 5000,
        "events": [],
        "segments": [],
    }
    record = build_clip_analysis_record(
        project_id="project-1",
        media=_media(),
        metadata=None,
        caches=[_cache(AnalysisModuleId.SCENE.value, payload=scene_payload)],
        embedding_vector_count=0,
        source_fingerprint="fp-1",
    )
    assert record.scene is not None
    assert record.motion is None
    assert record.summary.media_id == "media-1"
    assert record.versions.module_versions[AnalysisModuleId.SCENE.value] == "scene-v1"


def test_build_project_analysis_overview_counts():
    now = utc_now_iso()
    from montage_backend.models.domain.clip_analysis import (
        ClipAnalysisSummary,
        ClipAssetSnapshot,
        ClipProcessingSnapshot,
        ClipVideoSnapshot,
    )

    summaries = [
        ClipAnalysisSummary(
            media_id="m1",
            project_id="p1",
            overall_status=ProcessingStatus.READY,
            readiness=1.0,
            modules_ready=6,
            modules_total=6,
            processing=ClipProcessingSnapshot(
                import_status=ImportStatus.READY,
                proxy_status=ProcessingStatus.READY,
                waveform_status=ProcessingStatus.READY,
                scene_cache_status=ProcessingStatus.READY,
                metadata_status=ProcessingStatus.READY,
            ),
            assets=ClipAssetSnapshot(),
            video=ClipVideoSnapshot(),
            updated_at=now,
            created_at=now,
        ),
        ClipAnalysisSummary(
            media_id="m2",
            project_id="p1",
            overall_status=ProcessingStatus.PENDING,
            readiness=0.0,
            modules_ready=0,
            modules_total=6,
            processing=ClipProcessingSnapshot(
                import_status=ImportStatus.READY,
                proxy_status=ProcessingStatus.PENDING,
                waveform_status=ProcessingStatus.PENDING,
                scene_cache_status=ProcessingStatus.PENDING,
                metadata_status=ProcessingStatus.PENDING,
            ),
            assets=ClipAssetSnapshot(),
            video=ClipVideoSnapshot(),
            updated_at=now,
            created_at=now,
        ),
    ]
    overview = build_project_analysis_overview("p1", summaries)
    assert overview.clip_count == 2
    assert overview.analysis_ready_count == 1
    assert overview.analysis_pending_count == 1
