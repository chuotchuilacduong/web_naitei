from collections.abc import AsyncIterator
from pathlib import Path

import pytest
from httpx import ASGITransport, AsyncClient


@pytest.fixture
async def client(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> AsyncIterator[AsyncClient]:
    database_path = tmp_path / "taskhub-test.db"
    monkeypatch.setenv("TASKHUB_ENVIRONMENT", "test")
    monkeypatch.setenv("TASKHUB_DATABASE_URL", f"sqlite+aiosqlite:///{database_path.as_posix()}")
    monkeypatch.setenv("TASKHUB_REDIS_ENABLED", "false")
    monkeypatch.setenv("TASKHUB_SECRET_KEY", "test-secret-key-with-enough-length")

    from app.db.models import Base
    from app.db.session import engine
    from app.main import app

    async with engine.begin() as connection:
        await connection.run_sync(Base.metadata.create_all)

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as test_client:
        yield test_client

    async with engine.begin() as connection:
        await connection.run_sync(Base.metadata.drop_all)
    await engine.dispose()


@pytest.mark.asyncio
async def test_taskhub_core_flow(client: AsyncClient) -> None:
    register_response = await client.post(
        "/api/v1/auth/register",
        json={
            "email": "owner@example.com",
            "full_name": "Owner User",
            "password": "strong-password",
        },
    )
    assert register_response.status_code == 201

    login_response = await client.post(
        "/api/v1/auth/login",
        json={"email": "owner@example.com", "password": "strong-password"},
    )
    assert login_response.status_code == 200
    token = login_response.json()["access_token"]
    headers = {"Authorization": f"Bearer {token}"}

    workspace_response = await client.post(
        "/api/v1/workspaces",
        json={"name": "Engineering"},
        headers=headers,
    )
    assert workspace_response.status_code == 201
    workspace_id = workspace_response.json()["id"]

    project_response = await client.post(
        f"/api/v1/workspaces/{workspace_id}/projects",
        json={"name": "API", "description": "TaskHub API"},
        headers=headers,
    )
    assert project_response.status_code == 201
    project_id = project_response.json()["id"]

    task_response = await client.post(
        f"/api/v1/projects/{project_id}/tasks",
        json={"title": "Build endpoints", "priority": "HIGH"},
        headers=headers,
    )
    assert task_response.status_code == 201
    task_id = task_response.json()["id"]

    list_response = await client.get(
        f"/api/v1/projects/{project_id}/tasks?status=TODO&priority=HIGH",
        headers=headers,
    )
    assert list_response.status_code == 200
    assert list_response.json()["total"] == 1

    label_response = await client.post(
        f"/api/v1/projects/{project_id}/labels",
        json={"name": "backend", "color": "#3366ff"},
        headers=headers,
    )
    assert label_response.status_code == 201
    label_id = label_response.json()["id"]

    attach_response = await client.post(
        f"/api/v1/tasks/{task_id}/labels/{label_id}",
        headers=headers,
    )
    assert attach_response.status_code == 200

    comment_response = await client.post(
        f"/api/v1/tasks/{task_id}/comments",
        json={"content": "First implementation pass"},
        headers=headers,
    )
    assert comment_response.status_code == 201

    update_response = await client.patch(
        f"/api/v1/tasks/{task_id}",
        json={"status": "DONE"},
        headers=headers,
    )
    assert update_response.status_code == 200
    assert update_response.json()["status"] == "DONE"
