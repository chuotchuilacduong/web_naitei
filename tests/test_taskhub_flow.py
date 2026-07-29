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
    openapi_response = await client.get("/openapi.json")
    assert openapi_response.status_code == 200
    security_schemes = openapi_response.json()["components"]["securitySchemes"]
    assert security_schemes["BearerAuth"]["type"] == "http"
    assert security_schemes["BearerAuth"]["scheme"] == "bearer"

    missing_token_response = await client.get("/api/v1/users/me")
    assert missing_token_response.status_code == 401
    assert missing_token_response.headers["www-authenticate"] == "Bearer"

    register_response = await client.post(
        "/api/v1/auth/register",
        json={
            "email": "owner@example.com",
            "full_name": "Owner User",
            "password": "strong-password",
        },
    )
    assert register_response.status_code == 201
    assert register_response.json()["role"] == "ADMIN"

    member_response = await client.post(
        "/api/v1/auth/register",
        json={
            "email": "member@example.com",
            "full_name": "Member User",
            "password": "strong-password",
        },
    )
    assert member_response.status_code == 201
    member_id = member_response.json()["id"]

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

    user_page_response = await client.get("/api/v1/users", headers=headers)
    assert user_page_response.status_code == 200
    assert user_page_response.json()["total"] == 2

    admin_update_response = await client.patch(
        f"/api/v1/users/{member_id}",
        json={"full_name": "Updated Member User"},
        headers=headers,
    )
    assert admin_update_response.status_code == 200
    assert admin_update_response.json()["full_name"] == "Updated Member User"

    invite_response = await client.post(
        f"/api/v1/workspaces/{workspace_id}/members",
        json={"user_id": member_id, "role": "EDITOR"},
        headers=headers,
    )
    assert invite_response.status_code == 201

    project_response = await client.post(
        f"/api/v1/workspaces/{workspace_id}/projects",
        json={"name": "API", "description": "TaskHub API"},
        headers=headers,
    )
    assert project_response.status_code == 201
    project_id = project_response.json()["id"]

    task_response = await client.post(
        f"/api/v1/projects/{project_id}/tasks",
        json={"title": "Build endpoints", "priority": "HIGH", "assignee_id": member_id},
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

    member_login_response = await client.post(
        "/api/v1/auth/login",
        json={"email": "member@example.com", "password": "strong-password"},
    )
    assert member_login_response.status_code == 200
    member_headers = {"Authorization": f"Bearer {member_login_response.json()['access_token']}"}

    notification_response = await client.get("/api/v1/notifications/me", headers=member_headers)
    assert notification_response.status_code == 200
    notification_payload = notification_response.json()
    assert notification_payload["total"] == 1
    notification_id = notification_payload["items"][0]["id"]

    mark_read_response = await client.patch(
        f"/api/v1/notifications/{notification_id}/read",
        headers=member_headers,
    )
    assert mark_read_response.status_code == 200
    assert mark_read_response.json()["is_read"] is True

    mark_all_read_response = await client.patch(
        "/api/v1/notifications/me/read-all",
        headers=member_headers,
    )
    assert mark_all_read_response.status_code == 200

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

    explicit_null_patch_cases = [
        ("/api/v1/users/me", {"full_name": None}),
        (f"/api/v1/users/{member_id}", {"role": None}),
        (f"/api/v1/users/{member_id}", {"is_active": None}),
        (f"/api/v1/workspaces/{workspace_id}", {"name": None}),
        (f"/api/v1/projects/{project_id}", {"name": None}),
        (f"/api/v1/projects/{project_id}", {"status": None}),
        (f"/api/v1/tasks/{task_id}", {"title": None}),
        (f"/api/v1/tasks/{task_id}", {"status": None}),
        (f"/api/v1/tasks/{task_id}", {"priority": None}),
        (f"/api/v1/labels/{label_id}", {"name": None}),
        (f"/api/v1/labels/{label_id}", {"color": None}),
    ]
    for path, payload in explicit_null_patch_cases:
        null_patch_response = await client.patch(path, json=payload, headers=headers)
        assert null_patch_response.status_code == 422

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
