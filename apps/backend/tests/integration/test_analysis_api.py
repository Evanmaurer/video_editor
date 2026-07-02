from __future__ import annotations

import pytest
from httpx import AsyncClient

from montage_backend.api import deps
from montage_backend.models.domain import utc_now_iso
from montage_backend.models.domain.analysis import SceneTransitionType
from montage_backend.models.domain.media import (
    ImportStatus,
    MediaItem,
    MediaRole,
    MediaType,
    ProcessingStatus,
    StorageMode,
)
from montage_backend.services.analysis_service import AnalysisService


async def _create_project(client: AsyncClient, project_root) -> str:
    create = await client.post(
        "/api/v1/projects",
        json={
            "name": "Analysis Test",
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
async def test_analysis_modules_list(client: AsyncClient):
    response = await client.get("/api/v1/projects/proj-1/analysis/modules")
    assert response.status_code == 200
    modules = response.json()
    assert any(module["module_id"] == "scene" for module in modules)
    assert any(module["module_id"] == "motion" for module in modules)
    assert any(module["module_id"] == "audio" for module in modules)
    assert any(module["module_id"] == "ocr" for module in modules)
    assert any(module["module_id"] == "object" for module in modules)
    assert any(module["module_id"] == "embedding" for module in modules)
    assert any(module["module_id"] == "albion" for module in modules)


@pytest.mark.asyncio
async def test_albion_detectors_list(client: AsyncClient):
    response = await client.get("/api/v1/projects/proj-1/analysis/albion/detectors")
    assert response.status_code == 200
    detectors = response.json()
    assert any(item["detector_id"] == "framework_probe" for item in detectors)
    assert any(item["detector_id"] == "ocr" for item in detectors)
    assert any(item["detector_id"] == "ability" for item in detectors)
    assert any(item["detector_id"] == "combat" for item in detectors)
    assert any(item["detector_id"] == "bomb" for item in detectors)


@pytest.mark.asyncio
async def test_albion_analysis_query(client: AsyncClient, tmp_path):
    project_root = tmp_path / "albion-framework-project"
    project_id = await _create_project(client, project_root)

    source = project_root / "media" / "originals" / "media-albion.mp4"
    source.parent.mkdir(parents=True, exist_ok=True)
    source.write_bytes(b"fake")

    media = MediaItem(
        id="media-albion",
        project_id=project_id,
        file_path=str(source),
        file_name="media-albion.mp4",
        source_path=str(source),
        media_type=MediaType.VIDEO,
        role=MediaRole.CLIP,
        storage_mode=StorageMode.COPY,
        import_status=ImportStatus.READY,
        proxy_status=ProcessingStatus.READY,
        waveform_status=ProcessingStatus.READY,
        scene_status=ProcessingStatus.READY,
        metadata_status=ProcessingStatus.READY,
        duration_ms=5000,
        frame_rate=60.0,
        tags=[],
        is_favorite=False,
        created_at=utc_now_iso(),
        updated_at=utc_now_iso(),
    )
    media_service = deps.get_media_service()
    session_factory = await media_service._project_service._ensure_project_db(project_root)
    async with session_factory() as session:
        await media_service._repo.create(session, media)

    analysis_service: AnalysisService = deps.get_analysis_service()
    _, session_factory = await analysis_service._project_session(project_id)
    async with session_factory() as session:
        await analysis_service._repo.upsert_cache(
            session,
            media_id=media.id,
            module_id="albion",
            analyzer_version="albion-framework-v1.0",
            cache_key="albion:test",
            status=ProcessingStatus.READY,
            payload={
                "analyzer_version": "albion-framework-v1.0",
                "cache_key": "albion:test",
                "duration_ms": 5000,
                "frame_rate": 60.0,
                "summary": {
                    "detector_count": 1,
                    "event_count": 1,
                    "gpu_enabled": True,
                    "detector_ids": ["framework_probe"],
                },
                "detector_results": {
                    "framework_probe": {
                        "detector_id": "framework_probe",
                        "detector_version": "framework-probe-v1.0",
                        "cache_key": "framework_probe:test",
                        "confidence": 1.0,
                        "reasoning": "Framework probe validated",
                        "events": [
                            {
                                "event_type": "framework_probe",
                                "timestamp_ms": 0,
                                "confidence": 1.0,
                                "reasoning": "ok",
                                "metadata": {},
                            },
                        ],
                        "payload": {"initialized": True},
                    },
                },
                "detector_caches": {
                    "framework_probe": {
                        "detector_id": "framework_probe",
                        "detector_version": "framework-probe-v1.0",
                        "cache_key": "framework_probe:test",
                        "confidence": 1.0,
                        "reasoning": "Framework probe validated",
                        "event_count": 1,
                    },
                },
            },
            source_fingerprint="fp-albion",
            confidence=1.0,
            reasoning="test cache",
        )

    albion = await client.get(f"/api/v1/projects/{project_id}/media/{media.id}/analysis/albion")
    assert albion.status_code == 200
    body = albion.json()
    assert body is not None
    assert body["analyzer_version"] == "albion-framework-v1.0"
    assert body["summary"]["detector_count"] == 1
    assert "framework_probe" in body["detector_results"]


@pytest.mark.asyncio
async def test_albion_ocr_analysis_query(client: AsyncClient, tmp_path):
    project_root = tmp_path / "albion-ocr-project"
    project_id = await _create_project(client, project_root)

    source = project_root / "media" / "originals" / "media-albion-ocr.mp4"
    source.parent.mkdir(parents=True, exist_ok=True)
    source.write_bytes(b"fake")

    media = MediaItem(
        id="media-albion-ocr",
        project_id=project_id,
        file_path=str(source),
        file_name="media-albion-ocr.mp4",
        source_path=str(source),
        media_type=MediaType.VIDEO,
        role=MediaRole.CLIP,
        storage_mode=StorageMode.COPY,
        import_status=ImportStatus.READY,
        proxy_status=ProcessingStatus.READY,
        waveform_status=ProcessingStatus.READY,
        scene_status=ProcessingStatus.READY,
        metadata_status=ProcessingStatus.READY,
        duration_ms=4500,
        frame_rate=60.0,
        tags=[],
        is_favorite=False,
        created_at=utc_now_iso(),
        updated_at=utc_now_iso(),
    )
    media_service = deps.get_media_service()
    session_factory = await media_service._project_service._ensure_project_db(project_root)
    async with session_factory() as session:
        await media_service._repo.create(session, media)

    analysis_service: AnalysisService = deps.get_analysis_service()
    _, session_factory = await analysis_service._project_session(project_id)
    ocr_payload = {
        "detector_version": "albion-ocr-v1.0",
        "cache_key": "albion-ocr:test",
        "duration_ms": 4500,
        "frame_rate": 60.0,
        "window_ms": 1500,
        "sample_interval_ms": 1500,
        "summary": {
            "frames_sampled": 3,
            "window_count": 2,
            "detection_count": 3,
            "unique_text_count": 3,
            "engine_id": "fake",
            "engine_version": "test-1.0",
            "by_category": {
                "kill_message": 1,
                "damage_number": 1,
                "healing_number": 1,
            },
            "reused_m3_ocr": True,
        },
        "frame_windows": [
            {
                "window_start_ms": 0,
                "window_end_ms": 1500,
                "cache_key": "window:0-1500",
                "engine_id": "fake",
                "engine_version": "test-1.0",
                "detection_count": 2,
                "detections": [
                    {
                        "text": "[RAVER] PlayerOne killed [ENEMY] Target",
                        "category": "kill_message",
                        "timestamp_ms": 0,
                        "window_start_ms": 0,
                        "window_end_ms": 1500,
                        "confidence": 0.92,
                        "metadata": {"guild_tag": "RAVER"},
                    },
                    {
                        "text": "842k",
                        "category": "damage_number",
                        "timestamp_ms": 0,
                        "window_start_ms": 0,
                        "window_end_ms": 1500,
                        "confidence": 0.86,
                        "metadata": {"numeric_value": "842k"},
                    },
                ],
            },
            {
                "window_start_ms": 1500,
                "window_end_ms": 3000,
                "cache_key": "window:1500-3000",
                "engine_id": "fake",
                "engine_version": "test-1.0",
                "detection_count": 1,
                "detections": [
                    {
                        "text": "+1,240",
                        "category": "healing_number",
                        "timestamp_ms": 1500,
                        "window_start_ms": 1500,
                        "window_end_ms": 3000,
                        "confidence": 0.88,
                        "metadata": {"numeric_value": "1240"},
                    },
                ],
            },
        ],
        "detections": [],
        "unique_texts": ["[RAVER] PlayerOne killed [ENEMY] Target", "842k", "+1,240"],
    }
    async with session_factory() as session:
        await analysis_service._repo.upsert_cache(
            session,
            media_id=media.id,
            module_id="albion",
            analyzer_version="albion-framework-v1.0",
            cache_key="albion:ocr-test",
            status=ProcessingStatus.READY,
            payload={
                "analyzer_version": "albion-framework-v1.0",
                "cache_key": "albion:ocr-test",
                "duration_ms": 4500,
                "frame_rate": 60.0,
                "summary": {
                    "detector_count": 2,
                    "event_count": 1,
                    "gpu_enabled": True,
                    "detector_ids": ["framework_probe", "ocr"],
                },
                "detector_results": {
                    "ocr": {
                        "detector_id": "ocr",
                        "detector_version": "albion-ocr-v1.0",
                        "cache_key": "albion-ocr:test",
                        "confidence": 0.9,
                        "reasoning": "test",
                        "events": [],
                        "payload": ocr_payload,
                    },
                },
                "detector_caches": {},
            },
            source_fingerprint="fp-albion-ocr",
            confidence=0.9,
        )

    ocr = await client.get(f"/api/v1/projects/{project_id}/media/{media.id}/analysis/albion/ocr")
    assert ocr.status_code == 200
    body = ocr.json()
    assert body is not None
    assert body["detector_version"] == "albion-ocr-v1.0"
    assert body["summary"]["window_count"] == 2
    assert body["summary"]["by_category"]["kill_message"] == 1
    assert len(body["frame_windows"]) == 2
    assert body["frame_windows"][0]["cache_key"]


@pytest.mark.asyncio
async def test_albion_ui_analysis_query(client: AsyncClient, tmp_path):
    project_root = tmp_path / "albion-ui-project"
    project_id = await _create_project(client, project_root)

    source = project_root / "media" / "originals" / "media-albion-ui.mp4"
    source.parent.mkdir(parents=True, exist_ok=True)
    source.write_bytes(b"fake")

    media = MediaItem(
        id="media-albion-ui",
        project_id=project_id,
        file_path=str(source),
        file_name="media-albion-ui.mp4",
        source_path=str(source),
        media_type=MediaType.VIDEO,
        role=MediaRole.CLIP,
        storage_mode=StorageMode.COPY,
        import_status=ImportStatus.READY,
        proxy_status=ProcessingStatus.READY,
        waveform_status=ProcessingStatus.READY,
        scene_status=ProcessingStatus.READY,
        metadata_status=ProcessingStatus.READY,
        duration_ms=4500,
        frame_rate=60.0,
        tags=[],
        is_favorite=False,
        created_at=utc_now_iso(),
        updated_at=utc_now_iso(),
    )
    media_service = deps.get_media_service()
    session_factory = await media_service._project_service._ensure_project_db(project_root)
    async with session_factory() as session:
        await media_service._repo.create(session, media)

    analysis_service: AnalysisService = deps.get_analysis_service()
    _, session_factory = await analysis_service._project_session(project_id)
    ui_payload = {
        "detector_version": "albion-ui-v1.0",
        "cache_key": "albion-ui:test",
        "duration_ms": 4500,
        "frame_rate": 60.0,
        "window_ms": 2000,
        "sample_interval_ms": 2000,
        "template_id": "albion_1080p_default",
        "summary": {
            "frames_sampled": 2,
            "window_count": 2,
            "detection_count": 3,
            "unique_element_count": 3,
            "template_id": "albion_1080p_default",
            "engine_id": "template_heuristic",
            "engine_version": "1.0",
            "by_element": {
                "party_frame": 1,
                "minimap": 1,
                "health_bar": 1,
            },
            "reused_m3_object": True,
        },
        "frame_windows": [
            {
                "window_start_ms": 0,
                "window_end_ms": 2000,
                "cache_key": "window:0-2000",
                "template_id": "albion_1080p_default",
                "engine_id": "template_heuristic",
                "engine_version": "1.0",
                "detection_count": 2,
                "detections": [
                    {
                        "element_type": "party_frame",
                        "label": "party_frame",
                        "timestamp_ms": 0,
                        "window_start_ms": 0,
                        "window_end_ms": 2000,
                        "confidence": 0.82,
                        "bbox": {"x": 0, "y": 120, "width": 300, "height": 500},
                        "template_id": "albion_1080p_default",
                        "metadata": {"region_name": "party_frame"},
                    },
                    {
                        "element_type": "health_bar",
                        "label": "health_bar",
                        "timestamp_ms": 0,
                        "window_start_ms": 0,
                        "window_end_ms": 2000,
                        "confidence": 0.71,
                        "bbox": {"x": 760, "y": 980, "width": 380, "height": 40},
                        "template_id": "albion_1080p_default",
                        "metadata": {"region_name": "health_bar"},
                    },
                ],
            },
            {
                "window_start_ms": 2000,
                "window_end_ms": 4000,
                "cache_key": "window:2000-4000",
                "template_id": "albion_1080p_default",
                "engine_id": "template_heuristic",
                "engine_version": "1.0",
                "detection_count": 1,
                "detections": [
                    {
                        "element_type": "minimap",
                        "label": "minimap",
                        "timestamp_ms": 2000,
                        "window_start_ms": 2000,
                        "window_end_ms": 4000,
                        "confidence": 0.77,
                        "bbox": {"x": 1500, "y": 780, "width": 400, "height": 280},
                        "template_id": "albion_1080p_default",
                        "metadata": {"region_name": "minimap"},
                    },
                ],
            },
        ],
        "detections": [],
    }
    async with session_factory() as session:
        await analysis_service._repo.upsert_cache(
            session,
            media_id=media.id,
            module_id="albion",
            analyzer_version="albion-framework-v1.0",
            cache_key="albion:ui-test",
            status=ProcessingStatus.READY,
            payload={
                "analyzer_version": "albion-framework-v1.0",
                "cache_key": "albion:ui-test",
                "duration_ms": 4500,
                "frame_rate": 60.0,
                "summary": {
                    "detector_count": 2,
                    "event_count": 1,
                    "gpu_enabled": True,
                    "detector_ids": ["framework_probe", "ui"],
                },
                "detector_results": {
                    "ui": {
                        "detector_id": "ui",
                        "detector_version": "albion-ui-v1.0",
                        "cache_key": "albion-ui:test",
                        "confidence": 0.9,
                        "reasoning": "test",
                        "events": [],
                        "payload": ui_payload,
                    },
                },
                "detector_caches": {},
            },
            source_fingerprint="fp-albion-ui",
            confidence=0.9,
        )

    ui = await client.get(f"/api/v1/projects/{project_id}/media/{media.id}/analysis/albion/ui")
    assert ui.status_code == 200
    body = ui.json()
    assert body is not None
    assert body["detector_version"] == "albion-ui-v1.0"
    assert body["template_id"] == "albion_1080p_default"
    assert body["summary"]["by_element"]["party_frame"] == 1
    assert body["summary"]["by_element"]["minimap"] == 1
    assert len(body["frame_windows"]) == 2
    assert body["frame_windows"][0]["detections"][0]["bbox"]["width"] > 0


@pytest.mark.asyncio
async def test_albion_ability_analysis_query(client: AsyncClient, tmp_path):
    project_root = tmp_path / "albion-ability-project"
    project_id = await _create_project(client, project_root)

    source = project_root / "media" / "originals" / "media-albion-ability.mp4"
    source.parent.mkdir(parents=True, exist_ok=True)
    source.write_bytes(b"fake")

    media = MediaItem(
        id="media-albion-ability",
        project_id=project_id,
        file_path=str(source),
        file_name="media-albion-ability.mp4",
        source_path=str(source),
        media_type=MediaType.VIDEO,
        role=MediaRole.CLIP,
        storage_mode=StorageMode.COPY,
        import_status=ImportStatus.READY,
        proxy_status=ProcessingStatus.READY,
        waveform_status=ProcessingStatus.READY,
        scene_status=ProcessingStatus.READY,
        metadata_status=ProcessingStatus.READY,
        duration_ms=5000,
        frame_rate=60.0,
        tags=[],
        is_favorite=False,
        created_at=utc_now_iso(),
        updated_at=utc_now_iso(),
    )
    media_service = deps.get_media_service()
    session_factory = await media_service._project_service._ensure_project_db(project_root)
    async with session_factory() as session:
        await media_service._repo.create(session, media)

    analysis_service: AnalysisService = deps.get_analysis_service()
    _, session_factory = await analysis_service._project_session(project_id)
    ability_payload = {
        "detector_version": "albion-ability-v1.0",
        "cache_key": "albion-ability:test",
        "duration_ms": 5000,
        "frame_rate": 60.0,
        "window_ms": 2000,
        "sample_interval_ms": 2000,
        "catalog_id": "default",
        "summary": {
            "frames_sampled": 2,
            "window_count": 2,
            "mention_count": 2,
            "activation_count": 2,
            "ultimate_count": 1,
            "cooldown_event_count": 4,
            "unique_ability_count": 2,
            "catalog_id": "default",
            "by_ability": {"meteor": 1, "galatine_pair": 1},
            "by_event_type": {
                "activation": 1,
                "ultimate_activation": 1,
                "cooldown_start": 2,
                "cooldown_ready": 2,
            },
            "reused_albion_ocr": True,
        },
        "frame_windows": [
            {
                "window_start_ms": 0,
                "window_end_ms": 2000,
                "cache_key": "ability-window:0-2000",
                "catalog_id": "default",
                "event_count": 3,
                "events": [
                    {
                        "ability_id": "meteor",
                        "ability_name": "Meteor",
                        "event_type": "ultimate_activation",
                        "timestamp_ms": 1000,
                        "window_start_ms": 1000,
                        "window_end_ms": 3000,
                        "confidence": 0.9,
                        "is_ultimate": True,
                        "cooldown_ms": 120000,
                        "metadata": {},
                    },
                ],
            },
            {
                "window_start_ms": 2000,
                "window_end_ms": 4000,
                "cache_key": "ability-window:2000-4000",
                "catalog_id": "default",
                "event_count": 3,
                "events": [
                    {
                        "ability_id": "galatine_pair",
                        "ability_name": "Galatine Pair",
                        "event_type": "activation",
                        "timestamp_ms": 2500,
                        "window_start_ms": 2500,
                        "window_end_ms": 4500,
                        "confidence": 0.85,
                        "is_ultimate": False,
                        "cooldown_ms": 20000,
                        "metadata": {},
                    },
                ],
            },
        ],
        "events": [
            {
                "ability_id": "meteor",
                "ability_name": "Meteor",
                "event_type": "ultimate_activation",
                "timestamp_ms": 1000,
                "window_start_ms": 1000,
                "window_end_ms": 3000,
                "confidence": 0.9,
                "is_ultimate": True,
                "cooldown_ms": 120000,
                "metadata": {},
            },
            {
                "ability_id": "galatine_pair",
                "ability_name": "Galatine Pair",
                "event_type": "activation",
                "timestamp_ms": 2500,
                "window_start_ms": 2500,
                "window_end_ms": 4500,
                "confidence": 0.85,
                "is_ultimate": False,
                "cooldown_ms": 20000,
                "metadata": {},
            },
        ],
        "unique_abilities": ["galatine_pair", "meteor"],
    }
    async with session_factory() as session:
        await analysis_service._repo.upsert_cache(
            session,
            media_id=media.id,
            module_id="albion",
            analyzer_version="albion-framework-v1.0",
            cache_key="albion:ability-test",
            status=ProcessingStatus.READY,
            payload={
                "analyzer_version": "albion-framework-v1.0",
                "cache_key": "albion:ability-test",
                "duration_ms": 5000,
                "frame_rate": 60.0,
                "summary": {
                    "detector_count": 4,
                    "event_count": 2,
                    "gpu_enabled": True,
                    "detector_ids": ["framework_probe", "ui", "ocr", "ability"],
                },
                "detector_results": {
                    "ability": {
                        "detector_id": "ability",
                        "detector_version": "albion-ability-v1.0",
                        "cache_key": "albion-ability:test",
                        "confidence": 0.9,
                        "reasoning": "test",
                        "events": [],
                        "payload": ability_payload,
                    },
                },
                "detector_caches": {},
            },
            source_fingerprint="fp-albion-ability",
            confidence=0.9,
        )

    abilities = await client.get(
        f"/api/v1/projects/{project_id}/media/{media.id}/analysis/albion/abilities",
    )
    assert abilities.status_code == 200
    body = abilities.json()
    assert body is not None
    assert body["detector_version"] == "albion-ability-v1.0"
    assert body["catalog_id"] == "default"
    assert body["summary"]["ultimate_count"] == 1
    assert body["summary"]["by_ability"]["meteor"] == 1
    assert len(body["frame_windows"]) == 2
    assert body["frame_windows"][0]["cache_key"]


@pytest.mark.asyncio
async def test_albion_combat_timeline_analysis_query(client: AsyncClient, tmp_path):
    project_root = tmp_path / "albion-combat-project"
    project_id = await _create_project(client, project_root)

    source = project_root / "media" / "originals" / "media-albion-combat.mp4"
    source.parent.mkdir(parents=True, exist_ok=True)
    source.write_bytes(b"fake")

    media = MediaItem(
        id="media-albion-combat",
        project_id=project_id,
        file_path=str(source),
        file_name="media-albion-combat.mp4",
        source_path=str(source),
        media_type=MediaType.VIDEO,
        role=MediaRole.CLIP,
        storage_mode=StorageMode.COPY,
        import_status=ImportStatus.READY,
        proxy_status=ProcessingStatus.READY,
        waveform_status=ProcessingStatus.READY,
        scene_status=ProcessingStatus.READY,
        metadata_status=ProcessingStatus.READY,
        duration_ms=6000,
        frame_rate=60.0,
        tags=[],
        is_favorite=False,
        created_at=utc_now_iso(),
        updated_at=utc_now_iso(),
    )
    media_service = deps.get_media_service()
    session_factory = await media_service._project_service._ensure_project_db(project_root)
    async with session_factory() as session:
        await media_service._repo.create(session, media)

    analysis_service: AnalysisService = deps.get_analysis_service()
    _, session_factory = await analysis_service._project_session(project_id)
    combat_payload = {
        "detector_version": "albion-combat-v1.0",
        "cache_key": "albion-combat:test",
        "duration_ms": 6000,
        "frame_rate": 60.0,
        "window_ms": 2000,
        "sample_interval_ms": 2000,
        "config_id": "default",
        "summary": {
            "frames_sampled": 2,
            "window_count": 2,
            "entry_count": 4,
            "fight_count": 1,
            "kill_count": 1,
            "death_count": 0,
            "retreat_count": 1,
            "config_id": "default",
            "by_event_type": {
                "fight_start": 1,
                "fight_end": 1,
                "kill": 1,
                "death": 0,
                "retreat": 1,
            },
            "reused_albion_ocr": True,
            "reused_albion_ability": False,
            "reused_albion_ui": False,
            "reused_motion": False,
        },
        "frame_windows": [
            {
                "window_start_ms": 2000,
                "window_end_ms": 4000,
                "cache_key": "combat-window:2000-4000",
                "config_id": "default",
                "activity_score": 0.62,
                "entry_count": 3,
                "entries": [
                    {
                        "entry_id": "fight_start:2000:0",
                        "event_type": "fight_start",
                        "timestamp_ms": 2000,
                        "window_start_ms": 2000,
                        "window_end_ms": 4000,
                        "confidence": 0.78,
                        "label": "Fight started",
                        "search_text": "fight_start fight started combat",
                        "metadata": {},
                    },
                ],
            },
        ],
        "entries": [
            {
                "entry_id": "fight_start:2000:0",
                "event_type": "fight_start",
                "timestamp_ms": 2000,
                "window_start_ms": 2000,
                "window_end_ms": 4000,
                "confidence": 0.78,
                "label": "Fight started",
                "search_text": "fight_start fight started combat",
                "metadata": {},
            },
            {
                "entry_id": "kill:2500:1",
                "event_type": "kill",
                "timestamp_ms": 2500,
                "window_start_ms": 2500,
                "window_end_ms": 4500,
                "confidence": 0.9,
                "label": "Kill: Bojukre killed Enemy",
                "search_text": "kill bojukre killed enemy",
                "metadata": {},
            },
            {
                "entry_id": "fight_end:4000:2",
                "event_type": "fight_end",
                "timestamp_ms": 4000,
                "window_start_ms": 2000,
                "window_end_ms": 4000,
                "confidence": 0.76,
                "label": "Fight ended",
                "search_text": "fight_end fight ended combat",
                "metadata": {},
            },
            {
                "entry_id": "retreat:7000:3",
                "event_type": "retreat",
                "timestamp_ms": 7000,
                "window_start_ms": 4000,
                "window_end_ms": 10000,
                "confidence": 0.7,
                "label": "Retreat",
                "search_text": "retreat disengage combat",
                "metadata": {},
            },
        ],
    }
    async with session_factory() as session:
        await analysis_service._repo.upsert_cache(
            session,
            media_id=media.id,
            module_id="albion",
            analyzer_version="albion-framework-v1.0",
            cache_key="albion:combat-test",
            status=ProcessingStatus.READY,
            payload={
                "analyzer_version": "albion-framework-v1.0",
                "cache_key": "albion:combat-test",
                "duration_ms": 6000,
                "frame_rate": 60.0,
                "summary": {
                    "detector_count": 5,
                    "event_count": 4,
                    "gpu_enabled": True,
                    "detector_ids": ["framework_probe", "ui", "ocr", "ability", "combat"],
                },
                "detector_results": {
                    "combat": {
                        "detector_id": "combat",
                        "detector_version": "albion-combat-v1.0",
                        "cache_key": "albion-combat:test",
                        "confidence": 0.9,
                        "reasoning": "test",
                        "events": [],
                        "payload": combat_payload,
                    },
                },
                "detector_caches": {},
            },
            source_fingerprint="fp-albion-combat",
            confidence=0.9,
        )

    combat = await client.get(
        f"/api/v1/projects/{project_id}/media/{media.id}/analysis/albion/combat-timeline",
    )
    assert combat.status_code == 200
    body = combat.json()
    assert body is not None
    assert body["detector_version"] == "albion-combat-v1.0"
    assert body["config_id"] == "default"
    assert body["summary"]["kill_count"] == 1
    assert body["summary"]["retreat_count"] == 1
    assert body["entries"][1]["event_type"] == "kill"
    assert "kill" in body["entries"][1]["search_text"]


@pytest.mark.asyncio
async def test_albion_bomb_analysis_query(client: AsyncClient, tmp_path):
    project_root = tmp_path / "albion-bomb-project"
    project_id = await _create_project(client, project_root)

    source = project_root / "media" / "originals" / "media-albion-bomb.mp4"
    source.parent.mkdir(parents=True, exist_ok=True)
    source.write_bytes(b"fake")

    media = MediaItem(
        id="media-albion-bomb",
        project_id=project_id,
        file_path=str(source),
        file_name="media-albion-bomb.mp4",
        source_path=str(source),
        media_type=MediaType.VIDEO,
        role=MediaRole.CLIP,
        storage_mode=StorageMode.COPY,
        import_status=ImportStatus.READY,
        proxy_status=ProcessingStatus.READY,
        waveform_status=ProcessingStatus.READY,
        scene_status=ProcessingStatus.READY,
        metadata_status=ProcessingStatus.READY,
        duration_ms=6000,
        frame_rate=60.0,
        tags=[],
        is_favorite=False,
        created_at=utc_now_iso(),
        updated_at=utc_now_iso(),
    )
    media_service = deps.get_media_service()
    session_factory = await media_service._project_service._ensure_project_db(project_root)
    async with session_factory() as session:
        await media_service._repo.create(session, media)

    analysis_service: AnalysisService = deps.get_analysis_service()
    _, session_factory = await analysis_service._project_session(project_id)
    bomb_payload = {
        "detector_version": "albion-bomb-v1.0",
        "cache_key": "albion-bomb:test",
        "duration_ms": 6000,
        "frame_rate": 60.0,
        "window_ms": 2000,
        "sample_interval_ms": 2000,
        "config_id": "default",
        "summary": {
            "frames_sampled": 2,
            "window_count": 2,
            "bomb_count": 1,
            "top_bomb_score": 8.4,
            "total_kill_count": 4,
            "config_id": "default",
            "by_source": {"ocr": True, "motion": True, "audio": True, "ability": True},
            "reused_albion_combat": True,
            "reused_albion_ocr": False,
            "reused_albion_ability": True,
            "reused_motion": True,
            "reused_audio": True,
        },
        "frame_windows": [
            {
                "window_start_ms": 2000,
                "window_end_ms": 4000,
                "cache_key": "bomb-window:2000-4000",
                "config_id": "default",
                "bomb_count": 1,
                "max_bomb_score": 8.4,
                "events": [
                    {
                        "event_id": "bomb:2600:0",
                        "timestamp_ms": 2600,
                        "window_start_ms": 2000,
                        "window_end_ms": 4000,
                        "confidence": 0.84,
                        "bomb_score": 8.4,
                        "kill_count": 4,
                        "fusion": {
                            "ocr_score": 1.0,
                            "motion_score": 0.8,
                            "audio_score": 0.7,
                            "ability_score": 0.6,
                        },
                        "search_text": "bomb coordinated",
                        "reasoning": "Bomb detected: 4 kills in 2000ms",
                        "metadata": {},
                    },
                ],
            },
        ],
        "events": [
            {
                "event_id": "bomb:2600:0",
                "timestamp_ms": 2600,
                "window_start_ms": 2000,
                "window_end_ms": 4000,
                "confidence": 0.84,
                "bomb_score": 8.4,
                "kill_count": 4,
                "fusion": {
                    "ocr_score": 1.0,
                    "motion_score": 0.8,
                    "audio_score": 0.7,
                    "ability_score": 0.6,
                },
                "search_text": "bomb coordinated",
                "reasoning": "Bomb detected: 4 kills in 2000ms",
                "metadata": {},
            },
        ],
    }
    async with session_factory() as session:
        await analysis_service._repo.upsert_cache(
            session,
            media_id=media.id,
            module_id="albion",
            analyzer_version="albion-framework-v1.0",
            cache_key="albion:bomb-test",
            status=ProcessingStatus.READY,
            payload={
                "analyzer_version": "albion-framework-v1.0",
                "cache_key": "albion:bomb-test",
                "duration_ms": 6000,
                "frame_rate": 60.0,
                "summary": {
                    "detector_count": 6,
                    "event_count": 1,
                    "gpu_enabled": True,
                    "detector_ids": ["framework_probe", "ui", "ocr", "ability", "combat", "bomb"],
                },
                "detector_results": {
                    "bomb": {
                        "detector_id": "bomb",
                        "detector_version": "albion-bomb-v1.0",
                        "cache_key": "albion-bomb:test",
                        "confidence": 0.9,
                        "reasoning": "test",
                        "events": [],
                        "payload": bomb_payload,
                    },
                },
                "detector_caches": {},
            },
            source_fingerprint="fp-albion-bomb",
            confidence=0.9,
        )

    bombs = await client.get(
        f"/api/v1/projects/{project_id}/media/{media.id}/analysis/albion/bombs",
    )
    assert bombs.status_code == 200
    body = bombs.json()
    assert body is not None
    assert body["detector_version"] == "albion-bomb-v1.0"
    assert body["summary"]["bomb_count"] == 1
    assert body["summary"]["top_bomb_score"] == 8.4
    assert body["events"][0]["fusion"]["motion_score"] > 0


@pytest.mark.asyncio
async def test_albion_engagement_analysis_query(client: AsyncClient, tmp_path):
    project_root = tmp_path / "albion-engagement-project"
    project_id = await _create_project(client, project_root)

    source = project_root / "media" / "originals" / "media-albion-engagement.mp4"
    source.parent.mkdir(parents=True, exist_ok=True)
    source.write_bytes(b"fake")

    media = MediaItem(
        id="media-albion-engagement",
        project_id=project_id,
        file_path=str(source),
        file_name="media-albion-engagement.mp4",
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
        tags=[],
        is_favorite=False,
        created_at=utc_now_iso(),
        updated_at=utc_now_iso(),
    )
    media_service = deps.get_media_service()
    session_factory = await media_service._project_service._ensure_project_db(project_root)
    async with session_factory() as session:
        await media_service._repo.create(session, media)

    analysis_service: AnalysisService = deps.get_analysis_service()
    _, session_factory = await analysis_service._project_session(project_id)
    engagement_payload = {
        "detector_version": "albion-engagement-v1.0",
        "cache_key": "engagement:test",
        "duration_ms": 8000,
        "frame_rate": 60.0,
        "window_ms": 2000,
        "sample_interval_ms": 2000,
        "config_id": "default",
        "summary": {
            "frames_sampled": 4,
            "window_count": 4,
            "tag_count": 2,
            "primary_engagement": "zvz",
            "sustained_combat_ms": 0,
            "config_id": "default",
            "signals": {
                "kill_count": 5,
                "death_count": 0,
                "fight_count": 0,
                "bomb_count": 1,
                "sustained_combat_ms": 0,
                "sustained_ui_ms": 0,
                "party_frame_count": 0,
                "resource_bar_count": 0,
                "gathering_keyword_hits": 0,
                "avg_motion_score": 0.0,
                "max_motion_score": 0.0,
            },
            "by_engagement_type": {"zvz": 1, "open_world_pvp": 1},
            "reused_albion_combat": True,
            "reused_albion_bomb": True,
            "reused_albion_ui": False,
            "reused_albion_ocr": False,
            "reused_motion": False,
        },
        "frame_windows": [],
        "tags": [
            {
                "engagement_type": "zvz",
                "confidence": 0.9,
                "score": 9.0,
                "reasoning": "ZvZ engagement: 5 kills, 1 bomb event(s)",
                "search_text": "zvz zvz engagement 5 kills 1 bomb event(s)",
                "metadata": {"kill_count": 5, "bomb_count": 1},
            },
            {
                "engagement_type": "open_world_pvp",
                "confidence": 0.8,
                "score": 8.0,
                "reasoning": "Open-world PvP engagement: 5 kill(s) detected",
                "search_text": "open_world_pvp open-world pvp engagement 5 kill(s) detected",
                "metadata": {"kill_count": 5},
            },
        ],
    }
    async with session_factory() as session:
        await analysis_service._repo.upsert_cache(
            session,
            media_id=media.id,
            module_id="albion",
            analyzer_version="albion-framework-v1.0",
            cache_key="albion:engagement-test",
            status=ProcessingStatus.READY,
            payload={
                "analyzer_version": "albion-framework-v1.0",
                "cache_key": "albion:engagement-test",
                "duration_ms": 8000,
                "frame_rate": 60.0,
                "summary": {
                    "detector_count": 7,
                    "event_count": 2,
                    "gpu_enabled": True,
                    "detector_ids": [
                        "framework_probe",
                        "ui",
                        "ocr",
                        "ability",
                        "combat",
                        "bomb",
                        "engagement",
                    ],
                },
                "detector_results": {
                    "engagement": {
                        "detector_id": "engagement",
                        "detector_version": "albion-engagement-v1.0",
                        "cache_key": "albion-engagement:test",
                        "confidence": 0.9,
                        "reasoning": "test",
                        "events": [],
                        "payload": engagement_payload,
                    },
                },
                "detector_caches": {},
            },
            source_fingerprint="fp-albion-engagement",
            confidence=0.9,
        )

    engagement = await client.get(
        f"/api/v1/projects/{project_id}/media/{media.id}/analysis/albion/engagement",
    )
    assert engagement.status_code == 200
    body = engagement.json()
    assert body is not None
    assert body["detector_version"] == "albion-engagement-v1.0"
    assert body["summary"]["tag_count"] == 2
    assert body["summary"]["primary_engagement"] == "zvz"
    assert len(body["tags"]) == 2
    assert body["tags"][0]["engagement_type"] == "zvz"


@pytest.mark.asyncio
async def test_albion_highlight_analysis_query(client: AsyncClient, tmp_path):
    project_root = tmp_path / "albion-highlight-project"
    project_id = await _create_project(client, project_root)

    source = project_root / "media" / "originals" / "media-albion-highlight.mp4"
    source.parent.mkdir(parents=True, exist_ok=True)
    source.write_bytes(b"fake")

    media = MediaItem(
        id="media-albion-highlight",
        project_id=project_id,
        file_path=str(source),
        file_name="media-albion-highlight.mp4",
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
        tags=[],
        is_favorite=False,
        created_at=utc_now_iso(),
        updated_at=utc_now_iso(),
    )
    media_service = deps.get_media_service()
    session_factory = await media_service._project_service._ensure_project_db(project_root)
    async with session_factory() as session:
        await media_service._repo.create(session, media)

    analysis_service: AnalysisService = deps.get_analysis_service()
    _, session_factory = await analysis_service._project_session(project_id)
    highlight_payload = {
        "detector_version": "albion-highlight-v1.0",
        "cache_key": "highlight:test",
        "duration_ms": 8000,
        "frame_rate": 60.0,
        "window_ms": 2000,
        "sample_interval_ms": 2000,
        "config_id": "default",
        "highlight_score": 78.4,
        "confidence": 0.86,
        "explanation": "Albion highlight score 78.4/100. Bomb quality: Top bomb score 8.4/10.",
        "summary": {
            "frames_sampled": 4,
            "window_count": 4,
            "moment_count": 2,
            "highlight_score": 78.4,
            "confidence": 0.86,
            "explanation": "Albion highlight score 78.4/100. Bomb quality: Top bomb score 8.4/10.",
            "config_id": "default",
            "factor_count": 12,
            "top_factor_ids": ["bomb_quality", "kill_count"],
            "by_moment_type": {"bomb": 1, "kill": 1},
            "reused_albion_combat": True,
            "reused_albion_bomb": True,
            "reused_albion_engagement": True,
            "reused_albion_ability": False,
            "reused_albion_ocr": False,
            "reused_albion_ui": False,
            "reused_motion": False,
            "reused_audio": False,
        },
        "factors": [
            {
                "factor_id": "bomb_quality",
                "label": "Bomb quality",
                "score": 0.84,
                "weight": 0.14,
                "contribution": 11.8,
                "reasoning": "Top bomb score 8.4/10",
            }
        ],
        "frame_windows": [],
        "moments": [
            {
                "moment_id": "highlight:bomb:4000:0",
                "timestamp_ms": 4000,
                "window_start_ms": 3500,
                "window_end_ms": 4500,
                "moment_score": 84.0,
                "confidence": 0.86,
                "moment_type": "bomb",
                "reasoning": "Bomb detected",
                "search_text": "highlight bomb",
                "metadata": {"kill_count": 5},
            }
        ],
    }
    async with session_factory() as session:
        await analysis_service._repo.upsert_cache(
            session,
            media_id=media.id,
            module_id="albion",
            analyzer_version="albion-framework-v1.0",
            cache_key="albion:highlight-test",
            status=ProcessingStatus.READY,
            payload={
                "analyzer_version": "albion-framework-v1.0",
                "cache_key": "albion:highlight-test",
                "duration_ms": 8000,
                "frame_rate": 60.0,
                "summary": {
                    "detector_count": 8,
                    "event_count": 2,
                    "gpu_enabled": True,
                    "detector_ids": [
                        "framework_probe",
                        "ui",
                        "ocr",
                        "ability",
                        "combat",
                        "bomb",
                        "engagement",
                        "highlight",
                    ],
                },
                "detector_results": {
                    "highlight": {
                        "detector_id": "highlight",
                        "detector_version": "albion-highlight-v1.0",
                        "cache_key": "albion-highlight:test",
                        "confidence": 0.86,
                        "reasoning": "test",
                        "events": [],
                        "payload": highlight_payload,
                    },
                },
                "detector_caches": {},
            },
            source_fingerprint="fp-albion-highlight",
            confidence=0.86,
        )

    highlights = await client.get(
        f"/api/v1/projects/{project_id}/media/{media.id}/analysis/albion/highlights",
    )
    assert highlights.status_code == 200
    body = highlights.json()
    assert body is not None
    assert body["detector_version"] == "albion-highlight-v1.0"
    assert body["highlight_score"] == 78.4
    assert "Albion highlight score" in body["explanation"]
    assert body["summary"]["factor_count"] == 12
    assert body["moments"][0]["moment_type"] == "bomb"


@pytest.mark.asyncio
async def test_scene_analysis_run_and_query(client: AsyncClient, tmp_path, monkeypatch):
    project_root = tmp_path / "analysis-project"
    project_id = await _create_project(client, project_root)

    source = project_root / "media" / "originals" / "media-1.mp4"
    source.parent.mkdir(parents=True, exist_ok=True)
    source.write_bytes(b"fake")

    media_service = deps.get_media_service()
    media = MediaItem(
        id="media-1",
        project_id=project_id,
        file_path=str(source),
        file_name="media-1.mp4",
        source_path=str(source),
        media_type=MediaType.VIDEO,
        role=MediaRole.CLIP,
        storage_mode=StorageMode.COPY,
        import_status=ImportStatus.READY,
        proxy_status=ProcessingStatus.READY,
        waveform_status=ProcessingStatus.READY,
        scene_status=ProcessingStatus.READY,
        metadata_status=ProcessingStatus.READY,
        duration_ms=5000,
        frame_rate=60.0,
        tags=[],
        is_favorite=False,
        created_at=utc_now_iso(),
        updated_at=utc_now_iso(),
    )

    session_factory = await media_service._project_service._ensure_project_db(project_root)
    async with session_factory() as session:
        await media_service._repo.create(session, media)

    analysis_service: AnalysisService = deps.get_analysis_service()
    _, session_factory = await analysis_service._project_session(project_id)
    async with session_factory() as session:
        await analysis_service._repo.upsert_cache(
            session,
            media_id="media-1",
            module_id="scene",
            analyzer_version="scene-analyzer-v1.0",
            cache_key="scene:test",
            status=ProcessingStatus.READY,
            payload={
                "analyzer_version": "scene-analyzer-v1.0",
                "cache_key": "scene:test",
                "frame_rate": 60.0,
                "frame_count": 300,
                "duration_ms": 5000,
                "events": [
                    {
                        "timestamp_ms": 1000,
                        "frame": 60,
                        "event_type": SceneTransitionType.HARD_CUT.value,
                        "confidence": 0.9,
                        "metadata": {},
                    },
                ],
                "segments": [
                    {
                        "start_frame": 0,
                        "end_frame": 59,
                        "start_ms": 0,
                        "end_ms": 1000,
                        "duration_ms": 1000,
                        "transition_in": None,
                        "confidence": 1.0,
                    },
                    {
                        "start_frame": 60,
                        "end_frame": 299,
                        "start_ms": 1000,
                        "end_ms": 5000,
                        "duration_ms": 4000,
                        "transition_in": SceneTransitionType.HARD_CUT.value,
                        "confidence": 0.9,
                    },
                ],
            },
            source_fingerprint="test-fp",
            confidence=0.95,
        )

    run = await client.post(f"/api/v1/projects/{project_id}/media/media-1/analysis/scene/run")
    assert run.status_code == 202

    scenes = await client.get(f"/api/v1/projects/{project_id}/media/media-1/analysis/scenes")
    assert scenes.status_code == 200
    payload = scenes.json()
    assert payload is not None
    assert len(payload["segments"]) == 2
    assert payload["events"][0]["event_type"] == SceneTransitionType.HARD_CUT.value

    cache = await client.get(f"/api/v1/projects/{project_id}/media/media-1/analysis/scene")
    assert cache.status_code == 200
    assert cache.json()["status"] == ProcessingStatus.READY.value


@pytest.mark.asyncio
async def test_motion_analysis_query(client: AsyncClient, tmp_path):
    project_root = tmp_path / "motion-project"
    project_id = await _create_project(client, project_root)

    source = project_root / "media" / "originals" / "media-2.mp4"
    source.parent.mkdir(parents=True, exist_ok=True)
    source.write_bytes(b"fake")

    media_service = deps.get_media_service()
    media = MediaItem(
        id="media-2",
        project_id=project_id,
        file_path=str(source),
        file_name="media-2.mp4",
        source_path=str(source),
        media_type=MediaType.VIDEO,
        role=MediaRole.CLIP,
        storage_mode=StorageMode.COPY,
        import_status=ImportStatus.READY,
        proxy_status=ProcessingStatus.READY,
        waveform_status=ProcessingStatus.READY,
        scene_status=ProcessingStatus.READY,
        metadata_status=ProcessingStatus.READY,
        duration_ms=3000,
        frame_rate=60.0,
        tags=[],
        is_favorite=False,
        created_at=utc_now_iso(),
        updated_at=utc_now_iso(),
    )

    session_factory = await media_service._project_service._ensure_project_db(project_root)
    async with session_factory() as session:
        await media_service._repo.create(session, media)

    analysis_service: AnalysisService = deps.get_analysis_service()
    _, session_factory = await analysis_service._project_session(project_id)
    async with session_factory() as session:
        await analysis_service._repo.upsert_cache(
            session,
            media_id="media-2",
            module_id="motion",
            analyzer_version="motion-analyzer-v1.0",
            cache_key="motion:test",
            status=ProcessingStatus.READY,
            payload={
                "analyzer_version": "motion-analyzer-v1.0",
                "cache_key": "motion:test",
                "frame_rate": 60.0,
                "duration_ms": 3000,
                "window_ms": 1000,
                "sample_stride_frames": 15,
                "summary": {
                    "overall_motion_score": 0.32,
                    "dominant_movement_class": "slow",
                    "static_ratio": 0.333,
                    "slow_ratio": 0.667,
                    "fast_ratio": 0.0,
                    "average_shake": 0.12,
                    "average_pan": 0.28,
                },
                "windows": [
                    {
                        "start_ms": 0,
                        "end_ms": 1000,
                        "start_frame": 0,
                        "end_frame": 59,
                        "duration_ms": 1000,
                        "motion_score": 0.12,
                        "motion_intensity": 0.08,
                        "movement_class": "static",
                        "camera_movement": {"pan": 0.1, "zoom": 0.05, "shake": 0.08},
                        "confidence": 0.8,
                    },
                    {
                        "start_ms": 1000,
                        "end_ms": 2000,
                        "start_frame": 60,
                        "end_frame": 119,
                        "duration_ms": 1000,
                        "motion_score": 0.42,
                        "motion_intensity": 0.35,
                        "movement_class": "slow",
                        "camera_movement": {"pan": 0.35, "zoom": 0.12, "shake": 0.14},
                        "confidence": 0.85,
                    },
                ],
            },
            source_fingerprint="test-fp",
            confidence=0.82,
        )

    motion = await client.get(f"/api/v1/projects/{project_id}/media/media-2/analysis/motion")
    assert motion.status_code == 200
    body = motion.json()
    assert body is not None
    assert body["summary"]["dominant_movement_class"] == "slow"
    assert len(body["windows"]) == 2
    assert body["windows"][1]["movement_class"] == "slow"


@pytest.mark.asyncio
async def test_audio_analysis_query(client: AsyncClient, tmp_path):
    project_root = tmp_path / "audio-project"
    project_id = await _create_project(client, project_root)

    source = project_root / "media" / "originals" / "media-3.mp4"
    source.parent.mkdir(parents=True, exist_ok=True)
    source.write_bytes(b"fake")

    media_service = deps.get_media_service()
    media = MediaItem(
        id="media-3",
        project_id=project_id,
        file_path=str(source),
        file_name="media-3.mp4",
        source_path=str(source),
        media_type=MediaType.VIDEO,
        role=MediaRole.CLIP,
        storage_mode=StorageMode.COPY,
        import_status=ImportStatus.READY,
        proxy_status=ProcessingStatus.READY,
        waveform_status=ProcessingStatus.READY,
        scene_status=ProcessingStatus.READY,
        metadata_status=ProcessingStatus.READY,
        duration_ms=4000,
        frame_rate=60.0,
        tags=[],
        is_favorite=False,
        created_at=utc_now_iso(),
        updated_at=utc_now_iso(),
    )

    session_factory = await media_service._project_service._ensure_project_db(project_root)
    async with session_factory() as session:
        await media_service._repo.create(session, media)

    analysis_service: AnalysisService = deps.get_analysis_service()
    _, session_factory = await analysis_service._project_session(project_id)
    async with session_factory() as session:
        await analysis_service._repo.upsert_cache(
            session,
            media_id="media-3",
            module_id="audio",
            analyzer_version="audio-analyzer-v1.0",
            cache_key="audio:test",
            status=ProcessingStatus.READY,
            payload={
                "analyzer_version": "audio-analyzer-v1.0",
                "cache_key": "audio:test",
                "duration_ms": 4000,
                "sample_count": 512,
                "window_ms": 1000,
                "has_audio": True,
                "summary": {
                    "loudness_lufs": -19.5,
                    "mean_volume_db": -20.0,
                    "max_volume_db": -4.0,
                    "dynamic_range_db": 16.0,
                    "tempo_bpm": 120.0,
                    "music_probability": 0.65,
                    "voice_probability": 0.35,
                    "silence_ratio": 0.125,
                    "beat_count": 8,
                    "peak_count": 12,
                },
                "events": [
                    {
                        "timestamp_ms": 500,
                        "event_type": "silence",
                        "value": 0.5,
                        "confidence": 0.9,
                        "metadata": {"end_ms": 1000, "duration_ms": 500},
                    },
                    {
                        "timestamp_ms": 1500,
                        "event_type": "beat",
                        "value": 0.82,
                        "confidence": 0.9,
                        "metadata": {"strength": 0.82},
                    },
                ],
                "loudness_windows": [
                    {
                        "start_ms": 0,
                        "end_ms": 1000,
                        "duration_ms": 1000,
                        "loudness_db": -22.0,
                        "dynamic_range_db": 8.0,
                        "music_probability": 0.7,
                        "voice_probability": 0.3,
                        "confidence": 0.8,
                    }
                ],
                "peaks": [0.1, 0.8, 0.2],
            },
            source_fingerprint="test-fp",
            confidence=0.85,
        )

    audio = await client.get(f"/api/v1/projects/{project_id}/media/media-3/analysis/audio")
    assert audio.status_code == 200
    body = audio.json()
    assert body is not None
    assert body["summary"]["tempo_bpm"] == 120.0
    assert body["summary"]["beat_count"] == 8
    assert body["events"][0]["event_type"] == "silence"
    assert body["events"][1]["event_type"] == "beat"


@pytest.mark.asyncio
async def test_ocr_analysis_query(client: AsyncClient, tmp_path):
    project_root = tmp_path / "ocr-project"
    project_id = await _create_project(client, project_root)

    source = project_root / "media" / "originals" / "media-4.mp4"
    source.parent.mkdir(parents=True, exist_ok=True)
    source.write_bytes(b"fake")

    media_service = deps.get_media_service()
    media = MediaItem(
        id="media-4",
        project_id=project_id,
        file_path=str(source),
        file_name="media-4.mp4",
        source_path=str(source),
        media_type=MediaType.VIDEO,
        role=MediaRole.CLIP,
        storage_mode=StorageMode.COPY,
        import_status=ImportStatus.READY,
        proxy_status=ProcessingStatus.READY,
        waveform_status=ProcessingStatus.READY,
        scene_status=ProcessingStatus.READY,
        metadata_status=ProcessingStatus.READY,
        duration_ms=6000,
        frame_rate=60.0,
        tags=[],
        is_favorite=False,
        created_at=utc_now_iso(),
        updated_at=utc_now_iso(),
    )

    session_factory = await media_service._project_service._ensure_project_db(project_root)
    async with session_factory() as session:
        await media_service._repo.create(session, media)

    analysis_service: AnalysisService = deps.get_analysis_service()
    _, session_factory = await analysis_service._project_session(project_id)
    async with session_factory() as session:
        await analysis_service._repo.upsert_cache(
            session,
            media_id="media-4",
            module_id="ocr",
            analyzer_version="ocr-analyzer-v1.0",
            cache_key="ocr:test",
            status=ProcessingStatus.READY,
            payload={
                "analyzer_version": "ocr-analyzer-v1.0",
                "cache_key": "ocr:test",
                "duration_ms": 6000,
                "frame_rate": 60.0,
                "sample_interval_ms": 2000,
                "summary": {
                    "frames_sampled": 3,
                    "detection_count": 2,
                    "unique_text_count": 2,
                    "engine_id": "fake",
                    "engine_version": "test-1.0",
                    "by_category": {
                        "combat_text": 1,
                        "damage_number": 1,
                        "hud_text": 0,
                        "player_name": 0,
                        "guild_name": 0,
                        "chat": 0,
                        "unknown": 0,
                    },
                },
                "detections": [
                    {
                        "text": "[RAVER] PlayerOne killed [ENEMY] Target",
                        "category": "combat_text",
                        "timestamp_ms": 2000,
                        "frame": 120,
                        "confidence": 0.92,
                        "bbox": None,
                        "metadata": {"guild_tag": "RAVER"},
                    },
                    {
                        "text": "1,240",
                        "category": "damage_number",
                        "timestamp_ms": 4000,
                        "frame": 240,
                        "confidence": 0.88,
                        "bbox": {"x": 100, "y": 200, "width": 40, "height": 16},
                        "metadata": {},
                    },
                ],
                "unique_texts": ["[RAVER] PlayerOne killed [ENEMY] Target", "1,240"],
            },
            source_fingerprint="test-fp",
            confidence=0.9,
        )

    ocr = await client.get(f"/api/v1/projects/{project_id}/media/media-4/analysis/ocr")
    assert ocr.status_code == 200
    body = ocr.json()
    assert body is not None
    assert body["summary"]["engine_id"] == "fake"
    assert body["detections"][0]["category"] == "combat_text"
    assert body["unique_texts"] == ["[RAVER] PlayerOne killed [ENEMY] Target", "1,240"]


@pytest.mark.asyncio
async def test_object_analysis_query(client: AsyncClient, tmp_path):
    project_root = tmp_path / "object-project"
    project_id = await _create_project(client, project_root)

    source = project_root / "media" / "originals" / "media-5.mp4"
    source.parent.mkdir(parents=True, exist_ok=True)
    source.write_bytes(b"fake")

    media_service = deps.get_media_service()
    media = MediaItem(
        id="media-5",
        project_id=project_id,
        file_path=str(source),
        file_name="media-5.mp4",
        source_path=str(source),
        media_type=MediaType.VIDEO,
        role=MediaRole.CLIP,
        storage_mode=StorageMode.COPY,
        import_status=ImportStatus.READY,
        proxy_status=ProcessingStatus.READY,
        waveform_status=ProcessingStatus.READY,
        scene_status=ProcessingStatus.READY,
        metadata_status=ProcessingStatus.READY,
        duration_ms=5000,
        frame_rate=60.0,
        tags=[],
        is_favorite=False,
        created_at=utc_now_iso(),
        updated_at=utc_now_iso(),
    )

    session_factory = await media_service._project_service._ensure_project_db(project_root)
    async with session_factory() as session:
        await media_service._repo.create(session, media)

    analysis_service: AnalysisService = deps.get_analysis_service()
    _, session_factory = await analysis_service._project_session(project_id)
    async with session_factory() as session:
        await analysis_service._repo.upsert_cache(
            session,
            media_id="media-5",
            module_id="object",
            analyzer_version="object-analyzer-v1.0",
            cache_key="object:test",
            status=ProcessingStatus.READY,
            payload={
                "analyzer_version": "object-analyzer-v1.0",
                "cache_key": "object:test",
                "duration_ms": 5000,
                "frame_rate": 60.0,
                "sample_interval_ms": 2500,
                "summary": {
                    "frames_sampled": 2,
                    "detection_count": 2,
                    "unique_detection_count": 2,
                    "detector_id": "fake",
                    "detector_version": "test-1.0",
                    "by_category": {
                        "character": 1,
                        "minimap": 1,
                        "mount": 0,
                        "spell_effect": 0,
                        "party_frame": 0,
                        "ui_panel": 0,
                        "health_bar": 0,
                        "unknown": 0,
                    },
                },
                "detections": [
                    {
                        "category": "character",
                        "label": "person",
                        "timestamp_ms": 0,
                        "frame": 0,
                        "confidence": 0.91,
                        "bbox": {"x": 400, "y": 200, "width": 120, "height": 240},
                        "source_model": "fake",
                        "metadata": {},
                    },
                    {
                        "category": "minimap",
                        "label": "minimap_region",
                        "timestamp_ms": 2500,
                        "frame": 150,
                        "confidence": 0.76,
                        "bbox": {"x": 1500, "y": 780, "width": 360, "height": 260},
                        "source_model": "fake",
                        "metadata": {},
                    },
                ],
            },
            source_fingerprint="test-fp",
            confidence=0.88,
        )

    objects = await client.get(f"/api/v1/projects/{project_id}/media/media-5/analysis/object")
    assert objects.status_code == 200
    body = objects.json()
    assert body is not None
    assert body["summary"]["detector_id"] == "fake"
    assert body["detections"][0]["category"] == "character"
    assert body["detections"][1]["category"] == "minimap"


@pytest.mark.asyncio
async def test_embedding_analysis_and_search(client: AsyncClient, tmp_path, monkeypatch):
    project_root = tmp_path / "embedding-project"
    project_id = await _create_project(client, project_root)

    media_service = deps.get_media_service()
    for media_id, file_name in (("media-6", "media-6.mp4"), ("media-7", "media-7.mp4")):
        source = project_root / "media" / "originals" / file_name
        source.parent.mkdir(parents=True, exist_ok=True)
        source.write_bytes(b"fake")
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
            duration_ms=6000,
            frame_rate=60.0,
            tags=[],
            is_favorite=False,
            created_at=utc_now_iso(),
            updated_at=utc_now_iso(),
        )
        session_factory = await media_service._project_service._ensure_project_db(project_root)
        async with session_factory() as session:
            await media_service._repo.create(session, media)

    analysis_service: AnalysisService = deps.get_analysis_service()
    _, session_factory = await analysis_service._project_session(project_id)

    from montage_backend.analysis.embedding_analysis import EmbeddingScopeType, EmbeddingVectorRecord
    from montage_backend.repositories.embedding_repo import EmbeddingRepository

    vector_a = [1.0, 0.0, 0.0]
    vector_b = [0.99, 0.1, 0.0]
    vector_scene = [0.0, 1.0, 0.0]

    repo = EmbeddingRepository()
    async with session_factory() as session:
        await repo.upsert_records(
            session,
            project_id=project_id,
            media_id="media-6",
            model_id="histogram-fallback",
            source_fingerprint="fp6",
            records=[
                EmbeddingVectorRecord(
                    id="emb-6-clip",
                    scope_type=EmbeddingScopeType.CLIP,
                    scope_id="media-6",
                    vector=vector_a,
                    dimensions=3,
                ),
                EmbeddingVectorRecord(
                    id="emb-6-scene",
                    scope_type=EmbeddingScopeType.SCENE,
                    scope_id="scene-0",
                    start_ms=0,
                    end_ms=3000,
                    vector=vector_scene,
                    dimensions=3,
                ),
            ],
        )
        await repo.upsert_records(
            session,
            project_id=project_id,
            media_id="media-7",
            model_id="histogram-fallback",
            source_fingerprint="fp7",
            records=[
                EmbeddingVectorRecord(
                    id="emb-7-clip",
                    scope_type=EmbeddingScopeType.CLIP,
                    scope_id="media-7",
                    vector=vector_b,
                    dimensions=3,
                ),
            ],
        )
        await analysis_service._repo.upsert_cache(
            session,
            media_id="media-6",
            module_id="embedding",
            analyzer_version="embedding-analyzer-v1.0",
            cache_key="embedding:test",
            status=ProcessingStatus.READY,
            payload={
                "analyzer_version": "embedding-analyzer-v1.0",
                "cache_key": "embedding:test",
                "duration_ms": 6000,
                "frame_rate": 60.0,
                "summary": {
                    "model_id": "histogram-fallback",
                    "dimensions": 3,
                    "clip_embedding_id": "emb-6-clip",
                    "scene_count": 1,
                    "keyframe_count": 2,
                    "total_embeddings": 4,
                },
                "embedding_ids": ["emb-6-clip", "emb-6-scene", "emb-6-kf0", "emb-6-kf1"],
            },
            source_fingerprint="fp6",
            confidence=0.9,
        )

    embedding = await client.get(f"/api/v1/projects/{project_id}/media/media-6/analysis/embedding")
    assert embedding.status_code == 200
    body = embedding.json()
    assert body["summary"]["model_id"] == "histogram-fallback"
    assert body["summary"]["total_embeddings"] == 4
    assert "embeddings" not in body

    similar = await client.get(f"/api/v1/projects/{project_id}/media/media-6/similar?top_k=5")
    assert similar.status_code == 200
    similar_body = similar.json()
    assert len(similar_body) >= 1
    assert similar_body[0]["media_id"] == "media-7"

    duplicates = await client.get(
        f"/api/v1/projects/{project_id}/media/media-6/duplicates?threshold=0.9",
    )
    assert duplicates.status_code == 200
    assert len(duplicates.json()) >= 1

    scene_similar = await client.get(
        f"/api/v1/projects/{project_id}/media/media-6/scenes/scene-0/similar?top_k=3",
    )
    assert scene_similar.status_code == 200

    class FakeSearchEngine:
        model_id = "fake-search"
        dimensions = 3

        def is_available(self) -> bool:
            return True

        def embed_png(self, png_bytes: bytes) -> list[float]:
            return vector_a

        def embed_text(self, text: str) -> list[float]:
            return vector_a

    monkeypatch.setattr(
        "montage_backend.services.analysis_service.resolve_embedding_engine",
        lambda **kwargs: FakeSearchEngine(),
    )

    search = await client.post(
        f"/api/v1/projects/{project_id}/analysis/search",
        json={"query": "pvp fight", "scope_type": "clip", "top_k": 5},
    )
    assert search.status_code == 200
    search_body = search.json()
    assert search_body["model_id"] == "fake-search"
    assert len(search_body["matches"]) >= 1


@pytest.mark.asyncio
async def test_clip_analysis_database(client: AsyncClient, tmp_path):
    project_root = tmp_path / "clip-analysis-project"
    project_id = await _create_project(client, project_root)

    source = project_root / "media" / "originals" / "media-8.mp4"
    source.parent.mkdir(parents=True, exist_ok=True)
    source.write_bytes(b"fake")

    media_service = deps.get_media_service()
    media = MediaItem(
        id="media-8",
        project_id=project_id,
        file_path=str(source),
        file_name="media-8.mp4",
        source_path=str(source),
        media_type=MediaType.VIDEO,
        role=MediaRole.CLIP,
        storage_mode=StorageMode.COPY,
        import_status=ImportStatus.READY,
        proxy_status=ProcessingStatus.READY,
        waveform_status=ProcessingStatus.READY,
        scene_status=ProcessingStatus.READY,
        metadata_status=ProcessingStatus.READY,
        duration_ms=5000,
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

    analysis_service: AnalysisService = deps.get_analysis_service()
    _, session_factory = await analysis_service._project_session(project_id)

    from montage_backend.models.domain.metadata import MetadataFeatureKey
    from montage_backend.repositories.metadata_repo import MetadataRepository

    metadata_repo = MetadataRepository()
    async with session_factory() as session:
        await metadata_repo.upsert_feature(
            session,
            media_id="media-8",
            feature_key=MetadataFeatureKey.VISUAL,
            status=ProcessingStatus.READY,
            payload={
                "motion_score": 0.4,
                "camera_movement": {"label": "static", "pan": 0.1, "zoom": 0.0, "shake": 0.0},
                "brightness": {"mean": 128, "min": 0, "max": 255, "std": 10},
                "color_histogram": {"bins": 16, "r": [], "g": [], "b": []},
                "blur_score": 0.1,
                "sharpness": 0.8,
            },
            source_fingerprint="fp8",
            confidence=0.85,
        )
        await analysis_service._repo.upsert_cache(
            session,
            media_id="media-8",
            module_id="scene",
            analyzer_version="scene-analyzer-v1.0",
            cache_key="scene:test",
            status=ProcessingStatus.READY,
            payload={
                "analyzer_version": "scene-analyzer-v1.0",
                "cache_key": "scene:test",
                "frame_rate": 60.0,
                "frame_count": 300,
                "duration_ms": 5000,
                "events": [],
                "segments": [
                    {
                        "start_frame": 0,
                        "end_frame": 59,
                        "start_ms": 0,
                        "end_ms": 1000,
                        "duration_ms": 1000,
                        "confidence": 1.0,
                    },
                ],
            },
            source_fingerprint="fp8",
            confidence=0.9,
        )

    analysis = await client.get(f"/api/v1/projects/{project_id}/media/media-8/analysis")
    assert analysis.status_code == 200
    body = analysis.json()
    assert body["media_id"] == "media-8"
    assert body["scene"] is not None
    assert body["metadata"] is not None
    assert body["summary"]["scene_count"] == 1
    assert body["processing"]["import_status"] == "ready"
    assert "scene" in body["modules"]

    summary = await client.get(f"/api/v1/projects/{project_id}/media/media-8/analysis/summary")
    assert summary.status_code == 200
    assert summary.json()["media_id"] == "media-8"

    overview = await client.get(f"/api/v1/projects/{project_id}/analysis/overview")
    assert overview.status_code == 200
    overview_body = overview.json()
    assert overview_body["clip_count"] >= 1
    assert any(clip["media_id"] == "media-8" for clip in overview_body["clips"])

    invalidate = await client.delete(f"/api/v1/projects/{project_id}/media/media-8/analysis")
    assert invalidate.status_code == 204

    scenes = await client.get(f"/api/v1/projects/{project_id}/media/media-8/analysis/scenes")
    assert scenes.status_code == 200
    assert scenes.json() is None


@pytest.mark.asyncio
async def test_analysis_queue_controls(client: AsyncClient, tmp_path):
    project_root = tmp_path / "queue-project"
    project_id = await _create_project(client, project_root)

    status = await client.get(f"/api/v1/projects/{project_id}/analysis/queue")
    assert status.status_code == 200
    body = status.json()
    assert body["paused"] is False
    assert body["max_workers"] >= 1

    pause = await client.post(f"/api/v1/projects/{project_id}/analysis/queue/pause")
    assert pause.status_code == 200
    assert pause.json()["paused"] is True

    resume = await client.post(f"/api/v1/projects/{project_id}/analysis/queue/resume")
    assert resume.status_code == 200
    assert resume.json()["paused"] is False

    jobs = await client.get(f"/api/v1/projects/{project_id}/analysis/jobs")
    assert jobs.status_code == 200
    assert isinstance(jobs.json(), list)

