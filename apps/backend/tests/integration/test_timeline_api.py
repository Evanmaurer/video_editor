from __future__ import annotations

import pytest
from httpx import AsyncClient


async def _create_project(client: AsyncClient, project_root, name: str = "Timeline Test") -> str:
    create = await client.post(
        "/api/v1/projects",
        json={
            "name": name,
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
async def test_get_active_timeline_creates_default(client: AsyncClient, tmp_path):
    project_id = await _create_project(client, tmp_path / "proj")

    response = await client.get(f"/api/v1/projects/{project_id}/timelines/active")
    assert response.status_code == 200
    body = response.json()
    assert body["project_id"] == project_id
    assert len(body["tracks"]) == 4
    assert body["tracks"][0]["type"] == "video"


@pytest.mark.asyncio
async def test_save_timeline_persists(client: AsyncClient, tmp_path):
    project_id = await _create_project(client, tmp_path / "proj2")

    active = await client.get(f"/api/v1/projects/{project_id}/timelines/active")
    doc = active.json()
    timeline_id = doc["id"]
    track_id = doc["tracks"][0]["id"]

    doc["tracks"][0]["clips"] = [
        {
            "id": "clip-test-1",
            "media_item_id": "media-abc",
            "track_id": track_id,
            "start_ms": 0,
            "end_ms": 3000,
            "source_in_ms": 0,
            "source_out_ms": 3000,
            "speed": 1.0,
            "opacity": 1.0,
            "name": "Test Clip",
        },
    ]
    doc["duration_ms"] = 3000

    save = await client.put(
        f"/api/v1/projects/{project_id}/timelines/{timeline_id}",
        json=doc,
    )
    assert save.status_code == 200
    assert save.json()["version"] == 2

    reload = await client.get(f"/api/v1/projects/{project_id}/timelines/{timeline_id}")
    assert reload.status_code == 200
    reloaded = reload.json()
    assert reloaded["duration_ms"] == 3000
    assert len(reloaded["tracks"][0]["clips"]) == 1


@pytest.mark.asyncio
async def test_list_timelines(client: AsyncClient, tmp_path):
    project_id = await _create_project(client, tmp_path / "proj3")
    await client.get(f"/api/v1/projects/{project_id}/timelines/active")

    listed = await client.get(f"/api/v1/projects/{project_id}/timelines")
    assert listed.status_code == 200
    items = listed.json()["items"]
    assert len(items) >= 1
    assert items[0]["is_active"] is True
