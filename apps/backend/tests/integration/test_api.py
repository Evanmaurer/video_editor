import pytest


@pytest.mark.asyncio
async def test_health_endpoint(client):
    response = await client.get("/health")
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "ok"
    assert "version" in data
    assert "gpu_available" in data


@pytest.mark.asyncio
async def test_health_requires_no_auth(client):
    response = await client.get("/health")
    assert response.status_code == 200


@pytest.mark.asyncio
async def test_api_requires_auth(client):
    from httpx import ASGITransport, AsyncClient
    from montage_backend.main import app

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        response = await ac.get("/api/v1/projects/recent")
        assert response.status_code == 401


@pytest.mark.asyncio
async def test_create_project_via_api(client, tmp_path):
    project_root = tmp_path / "ApiProject"
    response = await client.post(
        "/api/v1/projects",
        json={
            "name": "API Project",
            "root_path": str(project_root),
            "width": 1920,
            "height": 1080,
            "frame_rate": 60.0,
        },
    )
    assert response.status_code == 201
    data = response.json()
    assert data["name"] == "API Project"
    assert project_root.exists()


@pytest.mark.asyncio
async def test_open_project_via_api(client, tmp_path):
    project_root = tmp_path / "OpenProject"
    create_resp = await client.post(
        "/api/v1/projects",
        json={"name": "Open Me", "root_path": str(project_root)},
    )
    assert create_resp.status_code == 201

    open_resp = await client.post(
        "/api/v1/projects/open",
        json={"path": str(project_root)},
    )
    assert open_resp.status_code == 200
    assert open_resp.json()["name"] == "Open Me"


@pytest.mark.asyncio
async def test_settings_roundtrip(client):
    get_resp = await client.get("/api/v1/settings")
    assert get_resp.status_code == 200

    update_resp = await client.put(
        "/api/v1/settings",
        json={
            "default_project_path": "/tmp/montages",
            "llm": {
                "provider": "ollama",
                "model": "qwen3:8b-instruct",
                "base_url": "http://127.0.0.1:11434",
            },
            "gpu_enabled": True,
            "worker_count": 2,
        },
    )
    assert update_resp.status_code == 200
    assert update_resp.json()["llm"]["model"] == "qwen3:8b-instruct"
