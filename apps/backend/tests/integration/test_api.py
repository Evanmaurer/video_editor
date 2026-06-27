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
async def test_cors_allows_electron_dev_origin(client):
    response = await client.options(
        "/api/v1/projects/recent",
        headers={
            "Origin": "http://localhost:5173",
            "Access-Control-Request-Method": "GET",
            "Access-Control-Request-Headers": "x-montage-token",
        },
    )
    assert response.status_code == 200
    assert response.headers.get("access-control-allow-origin") == "http://localhost:5173"
    assert "x-montage-token" in response.headers.get("access-control-allow-headers", "").lower()


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
            "target_game": "albion",
        },
    )
    assert response.status_code == 201
    data = response.json()
    assert data["name"] == "API Project"
    assert project_root.exists()
    assert (project_root / "project.db").exists()
    assert (project_root / "project.json").exists()


@pytest.mark.asyncio
async def test_create_project_clean_installation(tmp_path, monkeypatch):
    """Regression: project creation on a fresh app.db (no lifespan / empty data dir)."""
    from httpx import ASGITransport, AsyncClient

    from montage_backend.api import deps
    from montage_backend.database import db_manager
    from montage_backend.main import app

    from montage_backend.config import settings

    app_data = tmp_path / "fresh_app_data"
    monkeypatch.setattr("montage_backend.config.settings.app_data_dir", app_data)
    db_manager._app_engine = None
    db_manager._app_session_factory = None
    db_manager._started = False
    deps._project_service = None
    deps._settings_service = None

    transport = ASGITransport(app=app)
    project_root = tmp_path / "CleanInstallProject"
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        response = await ac.post(
            "/api/v1/projects",
            json={
                "name": "Clean Install",
                "root_path": str(project_root),
                "width": 1920,
                "height": 1080,
                "frame_rate": 60,
                "target_game": "albion",
            },
            headers={"X-Montage-Token": settings.auth_token},
        )

    assert response.status_code == 201, response.text
    data = response.json()
    assert data["name"] == "Clean Install"
    assert data["target_game"] == "albion"
    assert project_root.exists()
    assert (app_data / "app.db").exists()


@pytest.mark.asyncio
async def test_create_project_duplicate_returns_structured_error(client, tmp_path):
    project_root = tmp_path / "DuplicateProject"
    payload = {
        "name": "Duplicate",
        "root_path": str(project_root),
        "width": 1920,
        "height": 1080,
        "frame_rate": 60.0,
        "target_game": "albion",
    }
    first = await client.post("/api/v1/projects", json=payload)
    assert first.status_code == 201

    second = await client.post("/api/v1/projects", json=payload)
    assert second.status_code == 409
    body = second.json()
    assert body["error"] == "PROJECT_ALREADY_EXISTS"
    assert "message" in body


@pytest.mark.asyncio
async def test_create_project_invalid_path_returns_structured_error(client, tmp_path):
    file_path = tmp_path / "not_a_directory.txt"
    file_path.write_text("x")

    response = await client.post(
        "/api/v1/projects",
        json={
            "name": "Bad Path",
            "root_path": str(file_path),
            "width": 1920,
            "height": 1080,
            "frame_rate": 60.0,
            "target_game": "albion",
        },
    )
    assert response.status_code == 400
    body = response.json()
    assert body["error"] == "INVALID_PROJECT"
    assert "message" in body


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
