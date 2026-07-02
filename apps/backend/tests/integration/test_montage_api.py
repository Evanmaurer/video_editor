from __future__ import annotations

import pytest
from httpx import AsyncClient

from montage_backend.api import deps
from montage_backend.analysis.base import AnalysisModuleId
from montage_backend.models.domain import utc_now_iso
from montage_backend.models.domain.media import (
    ImportStatus,
    MediaItem,
    MediaRole,
    MediaType,
    ProcessingStatus,
    StorageMode,
)
from montage_backend.models.domain.montage_plan import (
    MontageEffect,
    MontageEffectType,
    MontagePlanClip,
    MontagePlanStatus,
    MontageTransition,
    TransitionType,
)


async def _create_project(client: AsyncClient, project_root) -> str:
    create = await client.post(
        "/api/v1/projects",
        json={
            "name": "Montage Test",
            "root_path": str(project_root),
            "width": 1920,
            "height": 1080,
            "frame_rate": 60,
            "target_game": "albion",
        },
    )
    assert create.status_code == 201
    return create.json()["id"]


@pytest.mark.asyncio
async def test_montage_plan_crud(client: AsyncClient, tmp_path):
    project_id = await _create_project(client, tmp_path / "montage-project")

    modules = await client.get(f"/api/v1/projects/{project_id}/montage/modules")
    assert modules.status_code == 200
    assert modules.json() == [
        {"module_id": "draft"},
        {"module_id": "effects"},
        {"module_id": "feedback"},
        {"module_id": "highlights"},
        {"module_id": "music_sync"},
        {"module_id": "pacing"},
        {"module_id": "scoring"},
        {"module_id": "transitions"},
    ]

    create = await client.post(
        f"/api/v1/projects/{project_id}/montage/plans",
        json={
            "name": "PvP Draft",
            "random_seed": 12345,
            "target_duration_ms": 60000,
            "pacing_profile": "balanced",
        },
    )
    assert create.status_code == 201
    plan = create.json()
    plan_id = plan["id"]
    assert plan["status"] == "draft"
    assert plan["metadata"]["random_seed"] == 12345
    assert plan["metadata"]["pacing_profile"] == "balanced"

    get = await client.get(f"/api/v1/projects/{project_id}/montage/plans/{plan_id}")
    assert get.status_code == 200
    assert get.json()["name"] == "PvP Draft"

    clip = MontagePlanClip(
        id="plan-clip-1",
        media_id="media-1",
        order=0,
        source_start_ms=1000,
        source_end_ms=4000,
        source_start_frame=60,
        source_end_frame=240,
        timeline_start_ms=0,
        timeline_end_ms=3000,
        clip_score=88.0,
        playback_speed=1.0,
        transition_in=MontageTransition(type=TransitionType.HARD_CUT, confidence=1.0),
        transition_out=MontageTransition(type=TransitionType.FLASH, duration_ms=120, confidence=0.8),
        effects=[
            MontageEffect(
                id="fx-1",
                type=MontageEffectType.MOTION_BLUR,
                confidence=0.7,
                reasoning="Action emphasis",
            ),
        ],
        confidence=0.9,
        reasoning="Strong highlight candidate",
    )

    update = await client.put(
        f"/api/v1/projects/{project_id}/montage/plans/{plan_id}",
        json={
            "status": MontagePlanStatus.READY.value,
            "clips": [clip.model_dump(mode="json")],
            "overall_confidence": 0.87,
            "overall_reasoning": "Balanced first draft",
        },
    )
    assert update.status_code == 200
    body = update.json()
    assert body["status"] == "ready"
    assert body["version"] == 2
    assert len(body["clips"]) == 1
    assert body["clips"][0]["clip_score"] == pytest.approx(88.0)
    assert body["duration_ms"] == 3000

    listing = await client.get(f"/api/v1/projects/{project_id}/montage/plans")
    assert listing.status_code == 200
    summaries = listing.json()
    assert len(summaries) == 1
    assert summaries[0]["clip_count"] == 1

    delete = await client.delete(f"/api/v1/projects/{project_id}/montage/plans/{plan_id}")
    assert delete.status_code == 204

    missing = await client.get(f"/api/v1/projects/{project_id}/montage/plans/{plan_id}")
    assert missing.status_code == 404


@pytest.mark.asyncio
async def test_clip_scoring_api(client: AsyncClient, tmp_path):
    project_root = tmp_path / "montage-scoring-project"
    project_id = await _create_project(client, project_root)

    source = project_root / "media" / "originals" / "clip-a.mp4"
    source.parent.mkdir(parents=True, exist_ok=True)
    source.write_bytes(b"fake")

    media_service = deps.get_media_service()
    media = MediaItem(
        id="clip-a",
        project_id=project_id,
        file_path=str(source),
        file_name="clip-a.mp4",
        source_path=str(source),
        media_type=MediaType.VIDEO,
        role=MediaRole.CLIP,
        storage_mode=StorageMode.COPY,
        import_status=ImportStatus.READY,
        proxy_status=ProcessingStatus.READY,
        waveform_status=ProcessingStatus.READY,
        scene_status=ProcessingStatus.READY,
        metadata_status=ProcessingStatus.READY,
        duration_ms=8000,
        frame_rate=60.0,
        width=1920,
        height=1080,
        tags=[],
        is_favorite=False,
        created_at=utc_now_iso(),
        updated_at=utc_now_iso(),
    )

    session_factory = await media_service._project_service._ensure_project_db(project_root)
    async with session_factory() as session:
        await media_service._repo.create(session, media)

    analysis_service = deps.get_analysis_service()
    _, session_factory = await analysis_service._project_session(project_id)

    from montage_backend.models.domain.metadata import MetadataFeatureKey
    from montage_backend.repositories.metadata_repo import MetadataRepository

    metadata_repo = MetadataRepository()
    async with session_factory() as session:
        await metadata_repo.upsert_feature(
            session,
            media_id="clip-a",
            feature_key=MetadataFeatureKey.VISUAL,
            status=ProcessingStatus.READY,
            payload={
                "motion_score": 0.75,
                "camera_movement": {"label": "fast", "pan": 0.2, "zoom": 0.0, "shake": 0.4},
                "brightness": {"mean": 140, "min": 0, "max": 255, "std": 10},
                "color_histogram": {"bins": 16, "r": [], "g": [], "b": []},
                "blur_score": 0.1,
                "sharpness": 0.85,
            },
            source_fingerprint="fp-score-a",
            confidence=0.9,
        )
        await analysis_service._repo.upsert_cache(
            session,
            media_id="clip-a",
            module_id=AnalysisModuleId.MOTION.value,
            analyzer_version="motion-analyzer-v1.0",
            cache_key="motion:test",
            status=ProcessingStatus.READY,
            payload={
                "analyzer_version": "motion-analyzer-v1.0",
                "cache_key": "motion:test",
                "frame_rate": 60.0,
                "duration_ms": 8000,
                "window_ms": 1000,
                "sample_stride_frames": 30,
                "summary": {
                    "overall_motion_score": 0.75,
                    "dominant_movement_class": "fast",
                    "static_ratio": 0.1,
                    "slow_ratio": 0.3,
                    "fast_ratio": 0.6,
                    "average_shake": 0.4,
                    "average_pan": 0.2,
                },
                "windows": [],
            },
            source_fingerprint="fp-score-a",
            confidence=0.9,
        )

    empty_scores = await client.get(f"/api/v1/projects/{project_id}/montage/scores")
    assert empty_scores.status_code == 200
    assert empty_scores.json()["clip_count"] == 0

    score = await client.get(f"/api/v1/projects/{project_id}/media/clip-a/montage/score")
    assert score.status_code == 200
    body = score.json()
    assert body["media_id"] == "clip-a"
    assert 0.0 <= body["montage_score"] <= 100.0
    assert body["scorer_version"] == "clip-scorer-v1.0"
    assert "Montage score" in body["reasoning"]
    assert body["breakdown"]["motion"]["score"] == pytest.approx(75.0)

    listed = await client.get(f"/api/v1/projects/{project_id}/montage/scores")
    assert listed.status_code == 200
    listed_body = listed.json()
    assert listed_body["clip_count"] == 1
    assert listed_body["scores"][0]["media_id"] == "clip-a"

    refresh = await client.post(f"/api/v1/projects/{project_id}/montage/scores/refresh")
    assert refresh.status_code == 200
    assert refresh.json()["clip_count"] == 1


@pytest.mark.asyncio
async def test_clip_highlights_api(client: AsyncClient, tmp_path):
    project_root = tmp_path / "montage-highlights-project"
    project_id = await _create_project(client, project_root)

    source = project_root / "media" / "originals" / "clip-hl.mp4"
    source.parent.mkdir(parents=True, exist_ok=True)
    source.write_bytes(b"fake")

    media_service = deps.get_media_service()
    media = MediaItem(
        id="clip-hl",
        project_id=project_id,
        file_path=str(source),
        file_name="clip-hl.mp4",
        source_path=str(source),
        media_type=MediaType.VIDEO,
        role=MediaRole.CLIP,
        storage_mode=StorageMode.COPY,
        import_status=ImportStatus.READY,
        proxy_status=ProcessingStatus.READY,
        waveform_status=ProcessingStatus.READY,
        scene_status=ProcessingStatus.READY,
        metadata_status=ProcessingStatus.READY,
        duration_ms=12000,
        frame_rate=60.0,
        width=1920,
        height=1080,
        tags=[],
        is_favorite=False,
        created_at=utc_now_iso(),
        updated_at=utc_now_iso(),
    )

    session_factory = await media_service._project_service._ensure_project_db(project_root)
    async with session_factory() as session:
        await media_service._repo.create(session, media)

    analysis_service = deps.get_analysis_service()
    _, session_factory = await analysis_service._project_session(project_id)

    from montage_backend.models.domain.metadata import MetadataFeatureKey
    from montage_backend.repositories.metadata_repo import MetadataRepository

    metadata_repo = MetadataRepository()
    async with session_factory() as session:
        await metadata_repo.upsert_feature(
            session,
            media_id="clip-hl",
            feature_key=MetadataFeatureKey.VISUAL,
            status=ProcessingStatus.READY,
            payload={
                "motion_score": 0.8,
                "camera_movement": {"label": "fast", "pan": 0.3, "zoom": 0.0, "shake": 0.5},
                "brightness": {"mean": 140, "min": 0, "max": 255, "std": 10},
                "color_histogram": {"bins": 16, "r": [], "g": [], "b": []},
                "blur_score": 0.1,
                "sharpness": 0.85,
            },
            source_fingerprint="fp-hl-api",
            confidence=0.9,
        )
        await analysis_service._repo.upsert_cache(
            session,
            media_id="clip-hl",
            module_id=AnalysisModuleId.MOTION.value,
            analyzer_version="motion-analyzer-v1.0",
            cache_key="motion:test",
            status=ProcessingStatus.READY,
            payload={
                "analyzer_version": "motion-analyzer-v1.0",
                "cache_key": "motion:test",
                "frame_rate": 60.0,
                "duration_ms": 12000,
                "window_ms": 1000,
                "sample_stride_frames": 30,
                "summary": {
                    "overall_motion_score": 0.8,
                    "dominant_movement_class": "fast",
                    "static_ratio": 0.1,
                    "slow_ratio": 0.2,
                    "fast_ratio": 0.7,
                    "average_shake": 0.5,
                    "average_pan": 0.3,
                },
                "windows": [
                    {
                        "start_ms": 4000,
                        "end_ms": 5000,
                        "start_frame": 240,
                        "end_frame": 300,
                        "duration_ms": 1000,
                        "motion_score": 0.88,
                        "motion_intensity": 0.82,
                        "movement_class": "fast",
                        "camera_movement": {"pan": 0.3, "zoom": 0.1, "shake": 0.5},
                        "confidence": 0.9,
                    },
                ],
            },
            source_fingerprint="fp-hl-api",
            confidence=0.9,
        )
        await analysis_service._repo.upsert_cache(
            session,
            media_id="clip-hl",
            module_id=AnalysisModuleId.AUDIO.value,
            analyzer_version="audio-analyzer-v1.0",
            cache_key="audio:test",
            status=ProcessingStatus.READY,
            payload={
                "analyzer_version": "audio-analyzer-v1.0",
                "cache_key": "audio:test",
                "duration_ms": 12000,
                "sample_count": 1000,
                "window_ms": 1000,
                "has_audio": True,
                "summary": {
                    "dynamic_range_db": 18.0,
                    "silence_ratio": 0.1,
                    "peak_count": 2,
                    "beat_count": 1,
                },
                "events": [
                    {
                        "timestamp_ms": 4500,
                        "event_type": "peak",
                        "value": 0.85,
                        "confidence": 0.9,
                        "metadata": {},
                    },
                ],
                "loudness_windows": [],
                "peaks": [],
            },
            source_fingerprint="fp-hl-api",
            confidence=0.9,
        )

    empty = await client.get(f"/api/v1/projects/{project_id}/montage/highlights")
    assert empty.status_code == 200
    assert empty.json()["clip_count"] == 0

    highlights = await client.get(
        f"/api/v1/projects/{project_id}/media/clip-hl/montage/highlights",
    )
    assert highlights.status_code == 200
    body = highlights.json()
    assert body["media_id"] == "clip-hl"
    assert body["detector_version"] == "highlight-detector-v1.0"
    assert body["highlight_count"] >= 1
    segment = body["highlights"][0]
    assert segment["end_ms"] > segment["start_ms"]
    assert 0.0 <= segment["score"] <= 100.0
    assert 0.0 <= segment["confidence"] <= 1.0

    listed = await client.get(f"/api/v1/projects/{project_id}/montage/highlights")
    assert listed.status_code == 200
    assert listed.json()["clip_count"] == 1

    refresh = await client.post(f"/api/v1/projects/{project_id}/montage/highlights/refresh")
    assert refresh.status_code == 200
    assert refresh.json()["clip_count"] == 1


@pytest.mark.asyncio
async def test_music_sync_api(client: AsyncClient, tmp_path):
    project_root = tmp_path / "montage-music-sync-project"
    project_id = await _create_project(client, project_root)

    source = project_root / "media" / "originals" / "track.mp3"
    source.parent.mkdir(parents=True, exist_ok=True)
    source.write_bytes(b"fake-audio")

    media_service = deps.get_media_service()
    media = MediaItem(
        id="track-1",
        project_id=project_id,
        file_path=str(source),
        file_name="track.mp3",
        source_path=str(source),
        media_type=MediaType.AUDIO,
        role=MediaRole.MUSIC,
        storage_mode=StorageMode.COPY,
        import_status=ImportStatus.READY,
        proxy_status=ProcessingStatus.READY,
        waveform_status=ProcessingStatus.READY,
        scene_status=ProcessingStatus.PENDING,
        metadata_status=ProcessingStatus.READY,
        duration_ms=30000,
        frame_rate=0.0,
        tags=[],
        is_favorite=False,
        created_at=utc_now_iso(),
        updated_at=utc_now_iso(),
    )

    session_factory = await media_service._project_service._ensure_project_db(project_root)
    async with session_factory() as session:
        await media_service._repo.create(session, media)

    analysis_service = deps.get_analysis_service()
    _, session_factory = await analysis_service._project_session(project_id)

    from montage_backend.models.domain.metadata import MetadataFeatureKey
    from montage_backend.repositories.metadata_repo import MetadataRepository

    metadata_repo = MetadataRepository()
    async with session_factory() as session:
        await metadata_repo.upsert_feature(
            session,
            media_id="track-1",
            feature_key=MetadataFeatureKey.AUDIO,
            status=ProcessingStatus.READY,
            payload={
                "loudness_lufs": -16.0,
                "mean_volume_db": -18.0,
                "max_volume_db": -3.0,
                "peaks": [0.2, 0.8, 0.3],
                "silence_regions": [],
                "beat_markers": [{"timestamp_ms": 5000, "strength": 0.8}],
                "speech": {"has_speech": False, "speech_ratio": 0.0, "confidence": 0.9},
            },
            source_fingerprint="fp-track",
            confidence=0.9,
        )
        await analysis_service._repo.upsert_cache(
            session,
            media_id="track-1",
            module_id=AnalysisModuleId.AUDIO.value,
            analyzer_version="audio-analyzer-v1.0",
            cache_key="audio:test",
            status=ProcessingStatus.READY,
            payload={
                "analyzer_version": "audio-analyzer-v1.0",
                "cache_key": "audio:test",
                "duration_ms": 30000,
                "sample_count": 1000,
                "window_ms": 1000,
                "has_audio": True,
                "summary": {
                    "dynamic_range_db": 20.0,
                    "silence_ratio": 0.05,
                    "peak_count": 4,
                    "beat_count": 3,
                    "tempo_bpm": 128.0,
                    "music_probability": 0.85,
                    "voice_probability": 0.05,
                },
                "events": [
                    {
                        "timestamp_ms": 5000,
                        "event_type": "beat",
                        "value": 0.85,
                        "confidence": 0.9,
                        "metadata": {"strength": 0.85},
                    },
                ],
                "loudness_windows": [
                    {
                        "start_ms": 0,
                        "end_ms": 5000,
                        "duration_ms": 5000,
                        "loudness_db": -20.0,
                        "dynamic_range_db": 8.0,
                        "music_probability": 0.5,
                        "voice_probability": 0.1,
                        "confidence": 0.8,
                    },
                    {
                        "start_ms": 5000,
                        "end_ms": 10000,
                        "duration_ms": 5000,
                        "loudness_db": -12.0,
                        "dynamic_range_db": 14.0,
                        "music_probability": 0.82,
                        "voice_probability": 0.05,
                        "confidence": 0.88,
                    },
                    {
                        "start_ms": 10000,
                        "end_ms": 15000,
                        "duration_ms": 5000,
                        "loudness_db": -10.0,
                        "dynamic_range_db": 16.0,
                        "music_probability": 0.86,
                        "voice_probability": 0.04,
                        "confidence": 0.9,
                    },
                    {
                        "start_ms": 15000,
                        "end_ms": 20000,
                        "duration_ms": 5000,
                        "loudness_db": -6.0,
                        "dynamic_range_db": 20.0,
                        "music_probability": 0.9,
                        "voice_probability": 0.03,
                        "confidence": 0.92,
                    },
                ],
                "peaks": [],
            },
            source_fingerprint="fp-track",
            confidence=0.9,
        )

    empty = await client.get(f"/api/v1/projects/{project_id}/montage/music-sync")
    assert empty.status_code == 200
    assert empty.json()["track_count"] == 0

    sync = await client.get(f"/api/v1/projects/{project_id}/media/track-1/montage/music-sync")
    assert sync.status_code == 200
    body = sync.json()
    assert body["media_id"] == "track-1"
    assert body["sync_version"] == "music-sync-v1.0"
    assert body["tempo_bpm"] == pytest.approx(128.0)
    assert len(body["beat_markers"]) >= 1
    assert len(body["cut_suggestions"]) >= 1
    assert "BPM" in body["reasoning"]

    listed = await client.get(f"/api/v1/projects/{project_id}/montage/music-sync")
    assert listed.status_code == 200
    assert listed.json()["track_count"] == 1

    refresh = await client.post(f"/api/v1/projects/{project_id}/montage/music-sync/refresh")
    assert refresh.status_code == 200
    assert refresh.json()["track_count"] == 1


@pytest.mark.asyncio
async def test_plan_transitions_api(client: AsyncClient, tmp_path):
    project_id = await _create_project(client, tmp_path / "montage-transitions-project")

    create = await client.post(
        f"/api/v1/projects/{project_id}/montage/plans",
        json={
            "name": "Transition Draft",
            "random_seed": 777,
            "pacing_profile": "aggressive",
        },
    )
    assert create.status_code == 201
    plan_id = create.json()["id"]

    clip_a = MontagePlanClip(
        id="clip-a",
        media_id="media-a",
        order=0,
        source_start_ms=0,
        source_end_ms=3000,
        timeline_start_ms=0,
        timeline_end_ms=3000,
        clip_score=88.0,
        confidence=0.9,
        reasoning="High action opener",
    )
    clip_b = MontagePlanClip(
        id="clip-b",
        media_id="media-b",
        order=1,
        source_start_ms=0,
        source_end_ms=2500,
        timeline_start_ms=3000,
        timeline_end_ms=5500,
        clip_score=92.0,
        confidence=0.91,
        reasoning="Peak fight moment",
    )

    update = await client.put(
        f"/api/v1/projects/{project_id}/montage/plans/{plan_id}",
        json={
            "clips": [clip_a.model_dump(mode="json"), clip_b.model_dump(mode="json")],
            "music": {
                "media_id": "music-track",
                "bpm": 128.0,
                "beat_markers_ms": [3000],
                "confidence": 0.9,
                "reasoning": "Test track",
            },
        },
    )
    assert update.status_code == 200

    transitions = await client.get(
        f"/api/v1/projects/{project_id}/montage/plans/{plan_id}/transitions",
    )
    assert transitions.status_code == 200
    body = transitions.json()
    assert body["plan_id"] == plan_id
    assert body["engine_version"] == "transition-engine-v1.0"
    assert body["junction_count"] == 1
    assert body["recommendations"][0]["timeline_ms"] == 3000
    assert body["recommendations"][0]["transition_out"]["type"] in {
        "flash",
        "whip",
        "hard_cut",
        "motion_blur",
        "speed_ramp",
        "zoom",
        "crossfade",
        "fade",
    }

    refresh = await client.post(
        f"/api/v1/projects/{project_id}/montage/plans/{plan_id}/transitions/refresh",
        params={"apply": "true"},
    )
    assert refresh.status_code == 200

    plan = await client.get(f"/api/v1/projects/{project_id}/montage/plans/{plan_id}")
    assert plan.status_code == 200
    plan_body = plan.json()
    assert plan_body["clips"][0]["transition_out"] is not None
    assert plan_body["clips"][1]["transition_in"] is not None
    assert plan_body["version"] >= 3


@pytest.mark.asyncio
async def test_plan_pacing_api(client: AsyncClient, tmp_path):
    project_id = await _create_project(client, tmp_path / "montage-pacing-project")

    create = await client.post(
        f"/api/v1/projects/{project_id}/montage/plans",
        json={
            "name": "Pacing Draft",
            "random_seed": 555,
            "target_duration_ms": 8000,
            "pacing_profile": "aggressive",
        },
    )
    assert create.status_code == 201
    plan_id = create.json()["id"]

    clip_a = MontagePlanClip(
        id="pace-a",
        media_id="media-a",
        order=0,
        source_start_ms=0,
        source_end_ms=6000,
        timeline_start_ms=0,
        timeline_end_ms=3000,
        clip_score=90.0,
        confidence=0.9,
        reasoning="Opener",
    )
    clip_b = MontagePlanClip(
        id="pace-b",
        media_id="media-b",
        order=1,
        source_start_ms=0,
        source_end_ms=6000,
        timeline_start_ms=3000,
        timeline_end_ms=6000,
        clip_score=85.0,
        confidence=0.88,
        reasoning="Follow-up",
    )

    update = await client.put(
        f"/api/v1/projects/{project_id}/montage/plans/{plan_id}",
        json={"clips": [clip_a.model_dump(mode="json"), clip_b.model_dump(mode="json")]},
    )
    assert update.status_code == 200

    pacing = await client.get(f"/api/v1/projects/{project_id}/montage/plans/{plan_id}/pacing")
    assert pacing.status_code == 200
    body = pacing.json()
    assert body["plan_id"] == plan_id
    assert body["engine_version"] == "pacing-engine-v1.0"
    assert body["pacing_profile"] == "aggressive"
    assert body["clip_count"] == 2
    assert body["total_duration_ms"] == pytest.approx(8000, abs=2000)
    assert body["recommendations"][1]["timeline_start_ms"] == body["recommendations"][0]["timeline_end_ms"]

    refresh = await client.post(
        f"/api/v1/projects/{project_id}/montage/plans/{plan_id}/pacing/refresh",
        params={"apply": "true"},
    )
    assert refresh.status_code == 200

    plan = await client.get(f"/api/v1/projects/{project_id}/montage/plans/{plan_id}")
    assert plan.status_code == 200
    plan_body = plan.json()
    assert plan_body["clips"][0]["timeline_end_ms"] == refresh.json()["recommendations"][0]["timeline_end_ms"]
    assert plan_body["duration_ms"] == refresh.json()["total_duration_ms"]


async def _seed_clip_motion_analysis(
    *,
    project_id: str,
    project_root,
    media_id: str,
    file_name: str,
    motion_score: float,
    shake: float,
    fast_ratio: float,
) -> None:
    source = project_root / "media" / "originals" / file_name
    source.parent.mkdir(parents=True, exist_ok=True)
    source.write_bytes(b"fake")

    media_service = deps.get_media_service()
    media = MediaItem(
        id=media_id,
        project_id=project_id,
        file_path=str(source),
        file_name=file_name,
        source_path=str(source),
        media_type=MediaType.VIDEO,
        role=MediaRole.CLIP,
        storage_mode=StorageMode.COPY,
        import_status=ImportStatus.READY,
        proxy_status=ProcessingStatus.READY,
        waveform_status=ProcessingStatus.READY,
        scene_status=ProcessingStatus.READY,
        metadata_status=ProcessingStatus.READY,
        duration_ms=8000,
        frame_rate=60.0,
        width=1920,
        height=1080,
        tags=[],
        is_favorite=False,
        created_at=utc_now_iso(),
        updated_at=utc_now_iso(),
    )

    session_factory = await media_service._project_service._ensure_project_db(project_root)
    async with session_factory() as session:
        await media_service._repo.create(session, media)

    analysis_service = deps.get_analysis_service()
    _, session_factory = await analysis_service._project_session(project_id)

    from montage_backend.models.domain.metadata import MetadataFeatureKey
    from montage_backend.repositories.metadata_repo import MetadataRepository

    metadata_repo = MetadataRepository()
    async with session_factory() as session:
        await metadata_repo.upsert_feature(
            session,
            media_id=media_id,
            feature_key=MetadataFeatureKey.VISUAL,
            status=ProcessingStatus.READY,
            payload={
                "motion_score": motion_score,
                "camera_movement": {"label": "fast", "pan": 0.2, "zoom": 0.1, "shake": shake},
                "brightness": {"mean": 140, "min": 0, "max": 255, "std": 10},
                "color_histogram": {"bins": 16, "r": [], "g": [], "b": []},
                "blur_score": 0.1,
                "sharpness": 0.85,
            },
            source_fingerprint=f"fp-{media_id}",
            confidence=0.9,
        )
        await analysis_service._repo.upsert_cache(
            session,
            media_id=media_id,
            module_id=AnalysisModuleId.MOTION.value,
            analyzer_version="motion-analyzer-v1.0",
            cache_key=f"motion:{media_id}",
            status=ProcessingStatus.READY,
            payload={
                "analyzer_version": "motion-analyzer-v1.0",
                "cache_key": f"motion:{media_id}",
                "frame_rate": 60.0,
                "duration_ms": 8000,
                "window_ms": 1000,
                "sample_stride_frames": 30,
                "summary": {
                    "overall_motion_score": motion_score,
                    "dominant_movement_class": "fast",
                    "static_ratio": 0.1,
                    "slow_ratio": 0.2,
                    "fast_ratio": fast_ratio,
                    "average_shake": shake,
                    "average_pan": 0.2,
                },
                "windows": [],
            },
            source_fingerprint=f"fp-{media_id}",
            confidence=0.9,
        )


@pytest.mark.asyncio
async def test_plan_effects_api(client: AsyncClient, tmp_path):
    project_root = tmp_path / "montage-effects-project"
    project_id = await _create_project(client, project_root)

    await _seed_clip_motion_analysis(
        project_id=project_id,
        project_root=project_root,
        media_id="fx-media-a",
        file_name="fx-a.mp4",
        motion_score=0.82,
        shake=0.25,
        fast_ratio=0.7,
    )

    create = await client.post(
        f"/api/v1/projects/{project_id}/montage/plans",
        json={
            "name": "Effects Draft",
            "random_seed": 777,
            "pacing_profile": "aggressive",
        },
    )
    assert create.status_code == 201
    plan_id = create.json()["id"]

    clip = MontagePlanClip(
        id="fx-clip-a",
        media_id="fx-media-a",
        order=0,
        source_start_ms=0,
        source_end_ms=5000,
        timeline_start_ms=0,
        timeline_end_ms=3000,
        clip_score=92.0,
        confidence=0.92,
        reasoning="Highlight opener",
    )

    update = await client.put(
        f"/api/v1/projects/{project_id}/montage/plans/{plan_id}",
        json={"clips": [clip.model_dump(mode="json")]},
    )
    assert update.status_code == 200

    effects = await client.get(f"/api/v1/projects/{project_id}/montage/plans/{plan_id}/effects")
    assert effects.status_code == 200
    body = effects.json()
    assert body["plan_id"] == plan_id
    assert body["engine_version"] == "effects-engine-v1.0"
    assert body["pacing_profile"] == "aggressive"
    assert body["clip_count"] == 1
    assert len(body["recommendations"][0]["effects"]) >= 1
    assert 0.0 <= body["recommendations"][0]["effects"][0]["confidence"] <= 1.0

    refresh = await client.post(
        f"/api/v1/projects/{project_id}/montage/plans/{plan_id}/effects/refresh",
        params={"apply": "true"},
    )
    assert refresh.status_code == 200

    plan = await client.get(f"/api/v1/projects/{project_id}/montage/plans/{plan_id}")
    assert plan.status_code == 200
    plan_body = plan.json()
    assert len(plan_body["clips"][0]["effects"]) == len(refresh.json()["recommendations"][0]["effects"])
    assert plan_body["clips"][0]["effects"][0]["type"] in {
        "speed_ramp",
        "camera_shake",
        "zoom_punch",
        "color_grade",
        "motion_blur",
        "glow",
        "sharpen",
        "vignette",
    }


@pytest.mark.asyncio
async def test_plan_draft_generate_api(client: AsyncClient, tmp_path):
    project_root = tmp_path / "montage-draft-project"
    project_id = await _create_project(client, project_root)

    await _seed_clip_motion_analysis(
        project_id=project_id,
        project_root=project_root,
        media_id="draft-clip-a",
        file_name="draft-a.mp4",
        motion_score=0.85,
        shake=0.35,
        fast_ratio=0.65,
    )
    await _seed_clip_motion_analysis(
        project_id=project_id,
        project_root=project_root,
        media_id="draft-clip-b",
        file_name="draft-b.mp4",
        motion_score=0.72,
        shake=0.25,
        fast_ratio=0.5,
    )

    create = await client.post(
        f"/api/v1/projects/{project_id}/montage/plans",
        json={
            "name": "Auto Draft",
            "random_seed": 4242,
            "target_duration_ms": 15000,
            "pacing_profile": "aggressive",
        },
    )
    assert create.status_code == 201
    plan_id = create.json()["id"]

    generate = await client.post(
        f"/api/v1/projects/{project_id}/montage/plans/{plan_id}/draft/generate",
        params={"apply": "true", "refresh_sources": "true"},
    )
    assert generate.status_code == 200
    body = generate.json()
    assert body["plan_id"] == plan_id
    assert body["engine_version"] == "draft-generator-v1.0"
    assert body["clip_count"] >= 1
    assert body["title_card"]["type"] == "title"
    assert body["ending_card"]["type"] == "ending"

    plan = await client.get(f"/api/v1/projects/{project_id}/montage/plans/{plan_id}")
    assert plan.status_code == 200
    plan_body = plan.json()
    assert plan_body["status"] == "ready"
    assert len(plan_body["clips"]) == body["clip_count"]
    assert plan_body["title_card"] is not None
    assert plan_body["ending_card"] is not None
    assert plan_body["clips"][0]["source_end_ms"] > plan_body["clips"][0]["source_start_ms"]
    if len(plan_body["clips"]) > 1:
        assert plan_body["clips"][1]["transition_in"] is not None or plan_body["clips"][0]["transition_out"] is not None
    assert len(plan_body["clips"][0]["effects"]) >= 1
    assert plan_body["overall_confidence"] > 0.0

    draft = await client.get(f"/api/v1/projects/{project_id}/montage/plans/{plan_id}/draft")
    assert draft.status_code == 200
    assert draft.json()["clip_count"] == body["clip_count"]


@pytest.mark.asyncio
async def test_plan_timeline_apply_api(client: AsyncClient, tmp_path):
    project_root = tmp_path / "montage-timeline-apply-project"
    project_id = await _create_project(client, project_root)

    await _seed_clip_motion_analysis(
        project_id=project_id,
        project_root=project_root,
        media_id="timeline-clip-a",
        file_name="timeline-a.mp4",
        motion_score=0.82,
        shake=0.3,
        fast_ratio=0.6,
    )

    create = await client.post(
        f"/api/v1/projects/{project_id}/montage/plans",
        json={
            "name": "Timeline Apply Draft",
            "random_seed": 9090,
            "target_duration_ms": 12000,
            "pacing_profile": "balanced",
        },
    )
    assert create.status_code == 201
    plan_id = create.json()["id"]

    generate = await client.post(
        f"/api/v1/projects/{project_id}/montage/plans/{plan_id}/draft/generate",
        params={"apply": "true", "refresh_sources": "true"},
    )
    assert generate.status_code == 200

    active = await client.get(f"/api/v1/projects/{project_id}/timelines/active")
    assert active.status_code == 200
    timeline_id = active.json()["id"]

    apply = await client.post(
        f"/api/v1/projects/{project_id}/montage/plans/{plan_id}/timeline/apply",
        params={"timeline_id": timeline_id},
    )
    assert apply.status_code == 200
    body = apply.json()
    assert body["plan_id"] == plan_id
    assert body["timeline_id"] == timeline_id
    assert body["engine_version"] == "timeline-generator-v1.0"
    assert body["clip_count"] >= 1
    assert body["duration_ms"] > 0

    timeline = await client.get(f"/api/v1/projects/{project_id}/timelines/{timeline_id}")
    assert timeline.status_code == 200
    timeline_body = timeline.json()
    video_track = next(track for track in timeline_body["tracks"] if track["name"] == "Video 1")
    assert len(video_track["clips"]) >= 1
    assert video_track["clips"][0]["ai"]["montage_plan_id"] == plan_id
    assert timeline_body["metadata"]["montage_plan_id"] == plan_id

    plan = await client.get(f"/api/v1/projects/{project_id}/montage/plans/{plan_id}")
    assert plan.status_code == 200
    assert plan.json()["status"] == "applied"
    assert plan.json()["applied_timeline_id"] == timeline_id

    application = await client.get(
        f"/api/v1/projects/{project_id}/montage/plans/{plan_id}/timeline-application",
    )
    assert application.status_code == 200
    assert application.json()["timeline_id"] == timeline_id

    manual = timeline_body.copy()
    manual["tracks"][0]["clips"].append(
        {
            "id": "manual-edit",
            "media_item_id": "foreign-media",
            "track_id": manual["tracks"][0]["id"],
            "start_ms": 9000,
            "end_ms": 10000,
            "source_in_ms": 0,
            "source_out_ms": 1000,
            "speed": 1.0,
            "opacity": 1.0,
        },
    )
    manual["metadata"] = {"user_edit": True}
    save = await client.put(
        f"/api/v1/projects/{project_id}/timelines/{timeline_id}",
        json=manual,
    )
    assert save.status_code == 200

    blocked = await client.post(
        f"/api/v1/projects/{project_id}/montage/plans/{plan_id}/timeline/apply",
        params={"timeline_id": timeline_id},
    )
    assert blocked.status_code == 409

    confirmed = await client.post(
        f"/api/v1/projects/{project_id}/montage/plans/{plan_id}/timeline/apply",
        params={"timeline_id": timeline_id, "confirm_overwrite": "true"},
    )
    assert confirmed.status_code == 200
    assert confirmed.json()["overwritten"] is True


@pytest.mark.asyncio
async def test_plan_feedback_api(client: AsyncClient, tmp_path):
    project_root = tmp_path / "montage-feedback-project"
    project_id = await _create_project(client, project_root)

    await _seed_clip_motion_analysis(
        project_id=project_id,
        project_root=project_root,
        media_id="feedback-clip-a",
        file_name="feedback-a.mp4",
        motion_score=0.8,
        shake=0.28,
        fast_ratio=0.55,
    )

    create = await client.post(
        f"/api/v1/projects/{project_id}/montage/plans",
        json={
            "name": "Feedback Draft",
            "random_seed": 5151,
            "target_duration_ms": 10000,
            "pacing_profile": "balanced",
        },
    )
    assert create.status_code == 201
    plan_id = create.json()["id"]

    generate = await client.post(
        f"/api/v1/projects/{project_id}/montage/plans/{plan_id}/draft/generate",
        params={"apply": "true", "refresh_sources": "true"},
    )
    assert generate.status_code == 200

    feedback = await client.get(f"/api/v1/projects/{project_id}/montage/plans/{plan_id}/feedback")
    assert feedback.status_code == 200
    body = feedback.json()
    assert body["plan_id"] == plan_id
    assert body["quality"] is not None
    assert len(body["quality"]["estimates"]) == 5
    assert body["quality"]["engine_version"] == "feedback-engine-v1.0"

    submit = await client.post(
        f"/api/v1/projects/{project_id}/montage/plans/{plan_id}/feedback",
        json={"action": "more_aggressive", "comment": "Punch it up"},
    )
    assert submit.status_code == 200
    submit_body = submit.json()
    assert len(submit_body["events"]) == 1
    assert submit_body["events"][0]["action"] == "more_aggressive"
    assert submit_body["feedback_preferences"]["preferred_profile"] == "aggressive"

    analyze = await client.post(
        f"/api/v1/projects/{project_id}/montage/plans/{plan_id}/feedback/analyze",
    )
    assert analyze.status_code == 200
    assert analyze.json()["overall_score"] > 0.0

    regen = await client.post(
        f"/api/v1/projects/{project_id}/montage/plans/{plan_id}/feedback/regenerate",
        params={"action": "improve_pacing"},
    )
    assert regen.status_code == 200
    regen_body = regen.json()
    assert regen_body["plan_id"] == plan_id
    assert regen_body["quality"]["estimates"]
    assert regen_body["plan_status"] in {"ready", "draft"}
