import fnmatch
from collections.abc import AsyncIterator, Callable
from pathlib import Path
from typing import Any

import pytest
from httpx import ASGITransport, AsyncClient

PASSWORD = "strong-password"
NEW_PASSWORD = "new-strong-password"


class FakeRedis:
    def __init__(self) -> None:
        self.store: dict[str, str] = {}
        self.get_calls: list[str] = []
        self.set_calls: list[tuple[str, int]] = []
        self.delete_calls: list[tuple[str, ...]] = []

    async def get(self, key: str) -> str | None:
        self.get_calls.append(key)
        return self.store.get(key)

    async def set(self, key: str, value: str, ex: int) -> None:
        self.set_calls.append((key, ex))
        self.store[key] = value

    async def scan_iter(self, match: str) -> AsyncIterator[str]:
        for key in list(self.store):
            if fnmatch.fnmatch(key, match):
                yield key

    async def delete(self, *keys: str) -> None:
        self.delete_calls.append(keys)
        for key in keys:
            self.store.pop(key, None)


class FakeArqRedis:
    def __init__(self) -> None:
        self.jobs: list[tuple[str, tuple[object, ...], dict[str, object]]] = []
        self.closed = False

    async def enqueue_job(
        self,
        function: str,
        *args: object,
        **kwargs: object,
    ) -> object:
        self.jobs.append((function, args, kwargs))
        return object()

    async def close(self, *, close_connection_pool: bool = False) -> None:
        self.closed = close_connection_pool


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

    app.state.redis = None
    async with engine.begin() as connection:
        await connection.run_sync(Base.metadata.create_all)

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as test_client:
        yield test_client

    async with engine.begin() as connection:
        await connection.run_sync(Base.metadata.drop_all)
    app.state.redis = None
    await engine.dispose()


async def register_user(client: AsyncClient, email: str, full_name: str) -> dict[str, Any]:
    response = await client.post(
        "/api/v1/auth/register",
        json={
            "email": email,
            "full_name": full_name,
            "password": PASSWORD,
        },
    )
    assert response.status_code == 201
    return response.json()


async def login_headers(client: AsyncClient, email: str) -> dict[str, str]:
    token_pair = await login_user(client, email)
    return {"Authorization": f"Bearer {token_pair['access_token']}"}


async def login_user(
    client: AsyncClient,
    email: str,
    password: str = PASSWORD,
) -> dict[str, Any]:
    response = await client.post(
        "/api/v1/auth/login",
        json={"email": email, "password": password},
    )
    assert response.status_code == 200
    return response.json()


async def create_workspace_and_project(
    client: AsyncClient,
    headers: dict[str, str],
    *,
    workspace_name: str = "Engineering",
    project_name: str = "API",
) -> tuple[int, int]:
    workspace_response = await client.post(
        "/api/v1/workspaces",
        json={"name": workspace_name},
        headers=headers,
    )
    assert workspace_response.status_code == 201
    workspace_id = workspace_response.json()["id"]

    project_response = await client.post(
        f"/api/v1/workspaces/{workspace_id}/projects",
        json={"name": project_name},
        headers=headers,
    )
    assert project_response.status_code == 201
    project_id = project_response.json()["id"]
    return workspace_id, project_id


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


@pytest.mark.asyncio
async def test_workspace_rbac_roles_and_assignee_permissions(client: AsyncClient) -> None:
    admin = await register_user(client, "admin@example.com", "Admin User")
    owner = await register_user(client, "owner-rbac@example.com", "Workspace Owner")
    editor = await register_user(client, "editor@example.com", "Editor User")
    viewer = await register_user(client, "viewer@example.com", "Viewer User")
    outsider = await register_user(client, "outsider@example.com", "Outsider User")
    assert admin["role"] == "ADMIN"
    assert owner["role"] == "MEMBER"

    admin_headers = await login_headers(client, "admin@example.com")
    owner_headers = await login_headers(client, "owner-rbac@example.com")
    editor_headers = await login_headers(client, "editor@example.com")
    viewer_headers = await login_headers(client, "viewer@example.com")
    outsider_headers = await login_headers(client, "outsider@example.com")

    workspace_response = await client.post(
        "/api/v1/workspaces",
        json={"name": "RBAC Workspace"},
        headers=owner_headers,
    )
    assert workspace_response.status_code == 201
    workspace_id = workspace_response.json()["id"]

    project_response = await client.post(
        f"/api/v1/workspaces/{workspace_id}/projects",
        json={"name": "RBAC Project"},
        headers=owner_headers,
    )
    assert project_response.status_code == 201
    project_id = project_response.json()["id"]

    for user, role in ((editor, "EDITOR"), (viewer, "VIEWER")):
        invite_response = await client.post(
            f"/api/v1/workspaces/{workspace_id}/members",
            json={"user_id": user["id"], "role": role},
            headers=owner_headers,
        )
        assert invite_response.status_code == 201

    editor_invite_response = await client.post(
        f"/api/v1/workspaces/{workspace_id}/members",
        json={"user_id": outsider["id"], "role": "VIEWER"},
        headers=editor_headers,
    )
    assert editor_invite_response.status_code == 403

    admin_users_response = await client.get("/api/v1/users", headers=admin_headers)
    assert admin_users_response.status_code == 200
    editor_users_response = await client.get("/api/v1/users", headers=editor_headers)
    assert editor_users_response.status_code == 403

    task_response = await client.post(
        f"/api/v1/projects/{project_id}/tasks",
        json={"title": "Assigned viewer task", "assignee_id": viewer["id"]},
        headers=owner_headers,
    )
    assert task_response.status_code == 201
    task_id = task_response.json()["id"]

    viewer_read_response = await client.get(
        f"/api/v1/projects/{project_id}/tasks",
        headers=viewer_headers,
    )
    assert viewer_read_response.status_code == 200
    outsider_read_response = await client.get(
        f"/api/v1/projects/{project_id}/tasks",
        headers=outsider_headers,
    )
    assert outsider_read_response.status_code == 403

    viewer_create_task_response = await client.post(
        f"/api/v1/projects/{project_id}/tasks",
        json={"title": "Viewer should not create"},
        headers=viewer_headers,
    )
    assert viewer_create_task_response.status_code == 403

    viewer_status_response = await client.patch(
        f"/api/v1/tasks/{task_id}",
        json={"status": "IN_PROGRESS"},
        headers=viewer_headers,
    )
    assert viewer_status_response.status_code == 200
    assert viewer_status_response.json()["status"] == "IN_PROGRESS"

    viewer_title_response = await client.patch(
        f"/api/v1/tasks/{task_id}",
        json={"title": "Viewer should not retitle"},
        headers=viewer_headers,
    )
    assert viewer_title_response.status_code == 403

    viewer_comment_response = await client.post(
        f"/api/v1/tasks/{task_id}/comments",
        json={"content": "Assignee can comment"},
        headers=viewer_headers,
    )
    assert viewer_comment_response.status_code == 201

    label_create_response = await client.post(
        f"/api/v1/projects/{project_id}/labels",
        json={"name": "backend", "color": "#3366ff"},
        headers=editor_headers,
    )
    assert label_create_response.status_code == 201
    label_id = label_create_response.json()["id"]

    viewer_attach_label_response = await client.post(
        f"/api/v1/tasks/{task_id}/labels/{label_id}",
        headers=viewer_headers,
    )
    assert viewer_attach_label_response.status_code == 403

    editor_attach_label_response = await client.post(
        f"/api/v1/tasks/{task_id}/labels/{label_id}",
        headers=editor_headers,
    )
    assert editor_attach_label_response.status_code == 200


@pytest.mark.asyncio
async def test_auth_refresh_logout_and_change_password_flow(client: AsyncClient) -> None:
    await register_user(client, "auth@example.com", "Auth User")
    token_pair = await login_user(client, "auth@example.com")

    profile_response = await client.get(
        "/api/v1/users/me",
        headers={"Authorization": f"Bearer {token_pair['access_token']}"},
    )
    assert profile_response.status_code == 200
    assert profile_response.json()["email"] == "auth@example.com"

    refresh_response = await client.post(
        "/api/v1/auth/refresh",
        json={"refresh_token": token_pair["refresh_token"]},
    )
    assert refresh_response.status_code == 200
    refreshed_token_pair = refresh_response.json()

    reused_refresh_response = await client.post(
        "/api/v1/auth/refresh",
        json={"refresh_token": token_pair["refresh_token"]},
    )
    assert reused_refresh_response.status_code == 401

    change_password_response = await client.post(
        "/api/v1/users/me/change-password",
        json={"current_password": PASSWORD, "new_password": NEW_PASSWORD},
        headers={"Authorization": f"Bearer {refreshed_token_pair['access_token']}"},
    )
    assert change_password_response.status_code == 204

    old_password_response = await client.post(
        "/api/v1/auth/login",
        json={"email": "auth@example.com", "password": PASSWORD},
    )
    assert old_password_response.status_code == 401

    new_token_pair = await login_user(client, "auth@example.com", NEW_PASSWORD)
    logout_response = await client.post(
        "/api/v1/auth/logout",
        json={"refresh_token": new_token_pair["refresh_token"]},
    )
    assert logout_response.status_code == 204

    logged_out_refresh_response = await client.post(
        "/api/v1/auth/refresh",
        json={"refresh_token": new_token_pair["refresh_token"]},
    )
    assert logged_out_refresh_response.status_code == 401


@pytest.mark.asyncio
async def test_task_list_cache_hit_and_invalidation_flow(client: AsyncClient) -> None:
    from app.main import app

    await register_user(client, "cache-owner@example.com", "Cache Owner")
    headers = await login_headers(client, "cache-owner@example.com")
    _, project_id = await create_workspace_and_project(
        client,
        headers,
        workspace_name="Cache Workspace",
        project_name="Cache Project",
    )

    initial_task_response = await client.post(
        f"/api/v1/projects/{project_id}/tasks",
        json={"title": "Cached task"},
        headers=headers,
    )
    assert initial_task_response.status_code == 201

    fake_redis = FakeRedis()
    app.state.redis = fake_redis

    first_list_response = await client.get(
        f"/api/v1/projects/{project_id}/tasks?limit=10",
        headers=headers,
    )
    assert first_list_response.status_code == 200
    assert first_list_response.json()["total"] == 1
    assert len(fake_redis.store) == 1
    assert len(fake_redis.set_calls) == 1
    cached_key = next(iter(fake_redis.store))

    second_list_response = await client.get(
        f"/api/v1/projects/{project_id}/tasks?limit=10",
        headers=headers,
    )
    assert second_list_response.status_code == 200
    assert second_list_response.json() == first_list_response.json()
    assert fake_redis.get_calls == [cached_key, cached_key]
    assert len(fake_redis.set_calls) == 1

    mutation_response = await client.post(
        f"/api/v1/projects/{project_id}/tasks",
        json={"title": "Invalidates cached page"},
        headers=headers,
    )
    assert mutation_response.status_code == 201
    assert fake_redis.store == {}
    assert any(cached_key in keys for keys in fake_redis.delete_calls)

    refreshed_list_response = await client.get(
        f"/api/v1/projects/{project_id}/tasks?limit=10",
        headers=headers,
    )
    assert refreshed_list_response.status_code == 200
    assert refreshed_list_response.json()["total"] == 2
    assert len(fake_redis.set_calls) == 2


@pytest.mark.asyncio
async def test_archive_delete_detach_and_remove_member_flow(client: AsyncClient) -> None:
    owner = await register_user(client, "delete-owner@example.com", "Delete Owner")
    member = await register_user(client, "delete-member@example.com", "Delete Member")
    assert owner["role"] == "ADMIN"

    owner_headers = await login_headers(client, "delete-owner@example.com")
    member_headers = await login_headers(client, "delete-member@example.com")
    workspace_id, project_id = await create_workspace_and_project(
        client,
        owner_headers,
        workspace_name="Delete Workspace",
        project_name="Delete Project",
    )

    invite_response = await client.post(
        f"/api/v1/workspaces/{workspace_id}/members",
        json={"user_id": member["id"], "role": "VIEWER"},
        headers=owner_headers,
    )
    assert invite_response.status_code == 201

    archive_response = await client.post(
        f"/api/v1/projects/{project_id}/archive",
        headers=owner_headers,
    )
    assert archive_response.status_code == 200
    assert archive_response.json()["status"] == "ARCHIVED"

    get_archived_project_response = await client.get(
        f"/api/v1/projects/{project_id}",
        headers=owner_headers,
    )
    assert get_archived_project_response.status_code == 200
    assert get_archived_project_response.json()["status"] == "ARCHIVED"

    task_response = await client.post(
        f"/api/v1/projects/{project_id}/tasks",
        json={"title": "Delete target"},
        headers=owner_headers,
    )
    assert task_response.status_code == 201
    task_id = task_response.json()["id"]

    label_response = await client.post(
        f"/api/v1/projects/{project_id}/labels",
        json={"name": "cleanup", "color": "#33aa66"},
        headers=owner_headers,
    )
    assert label_response.status_code == 201
    label_id = label_response.json()["id"]

    attach_response = await client.post(
        f"/api/v1/tasks/{task_id}/labels/{label_id}",
        headers=owner_headers,
    )
    assert attach_response.status_code == 200

    comment_response = await client.post(
        f"/api/v1/tasks/{task_id}/comments",
        json={"content": "Delete me"},
        headers=owner_headers,
    )
    assert comment_response.status_code == 201
    comment_id = comment_response.json()["id"]

    detach_label_response = await client.delete(
        f"/api/v1/tasks/{task_id}/labels/{label_id}",
        headers=owner_headers,
    )
    assert detach_label_response.status_code == 204

    delete_label_response = await client.delete(
        f"/api/v1/labels/{label_id}",
        headers=owner_headers,
    )
    assert delete_label_response.status_code == 204

    update_deleted_label_response = await client.patch(
        f"/api/v1/labels/{label_id}",
        json={"name": "should be gone"},
        headers=owner_headers,
    )
    assert update_deleted_label_response.status_code == 404

    delete_comment_response = await client.delete(
        f"/api/v1/comments/{comment_id}",
        headers=owner_headers,
    )
    assert delete_comment_response.status_code == 204

    comments_response = await client.get(
        f"/api/v1/tasks/{task_id}/comments",
        headers=owner_headers,
    )
    assert comments_response.status_code == 200
    assert comments_response.json() == []

    delete_task_response = await client.delete(
        f"/api/v1/tasks/{task_id}",
        headers=owner_headers,
    )
    assert delete_task_response.status_code == 204

    update_deleted_task_response = await client.patch(
        f"/api/v1/tasks/{task_id}",
        json={"status": "DONE"},
        headers=owner_headers,
    )
    assert update_deleted_task_response.status_code == 404

    remove_member_response = await client.delete(
        f"/api/v1/workspaces/{workspace_id}/members/{member['id']}",
        headers=owner_headers,
    )
    assert remove_member_response.status_code == 204

    removed_member_workspace_response = await client.get(
        f"/api/v1/workspaces/{workspace_id}",
        headers=member_headers,
    )
    assert removed_member_workspace_response.status_code == 403

    delete_project_response = await client.delete(
        f"/api/v1/projects/{project_id}",
        headers=owner_headers,
    )
    assert delete_project_response.status_code == 204

    get_deleted_project_response = await client.get(
        f"/api/v1/projects/{project_id}",
        headers=owner_headers,
    )
    assert get_deleted_project_response.status_code == 404

    delete_workspace_response = await client.delete(
        f"/api/v1/workspaces/{workspace_id}",
        headers=owner_headers,
    )
    assert delete_workspace_response.status_code == 204

    get_deleted_workspace_response = await client.get(
        f"/api/v1/workspaces/{workspace_id}",
        headers=owner_headers,
    )
    assert get_deleted_workspace_response.status_code == 404


@pytest.mark.asyncio
async def test_queue_enqueue_and_email_template_retry(
    client: AsyncClient,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from app.core.config import get_settings
    from app.services import notifications, queue

    monkeypatch.setenv("TASKHUB_REDIS_ENABLED", "true")
    monkeypatch.setenv("TASKHUB_QUEUE_ENABLED", "true")
    monkeypatch.setenv("TASKHUB_REDIS_URL", "rediss://worker:secret@redis.local:6380/2")
    get_settings.cache_clear()

    fake_arq_redis = FakeArqRedis()

    async def fake_create_pool(redis_settings: Any) -> FakeArqRedis:
        assert redis_settings.host == "redis.local"
        assert redis_settings.port == 6380
        assert redis_settings.database == 2
        assert redis_settings.username == "worker"
        assert redis_settings.password == "secret"
        assert redis_settings.ssl is True
        return fake_arq_redis

    monkeypatch.setattr(queue, "create_pool", fake_create_pool)

    queued = await queue.enqueue_assignment_email("assignee@example.com", "Queued task")

    assert queued is True
    assert fake_arq_redis.closed is True
    assert fake_arq_redis.jobs == [
        (
            "send_assignment_email_job",
            ("assignee@example.com", "Queued task"),
            {"_queue_name": "taskhub:queue"},
        )
    ]

    monkeypatch.setenv("TASKHUB_EMAIL_ENABLED", "true")
    monkeypatch.setenv("TASKHUB_SMTP_HOST", "smtp.example.com")
    monkeypatch.setenv("TASKHUB_SMTP_FROM_EMAIL", "tasks@example.com")
    monkeypatch.setenv("TASKHUB_EMAIL_MAX_ATTEMPTS", "3")
    monkeypatch.setenv("TASKHUB_EMAIL_RETRY_DELAY_SECONDS", "0")
    get_settings.cache_clear()
    settings = get_settings()

    message = notifications.build_assignment_email(
        settings,
        "assignee@example.com",
        "Review <security> fixes",
    )
    plain_body = message.get_body(preferencelist=("plain",))
    html_body = message.get_body(preferencelist=("html",))
    assert plain_body is not None
    assert html_body is not None
    assert message["Subject"] == "TaskHub task assignment"
    assert "Review <security> fixes" in plain_body.get_content()
    assert "Review &lt;security&gt; fixes" in html_body.get_content()

    attempts = 0

    def fake_send_assignment_email_sync(
        settings: object,
        smtp_host: str,
        recipient_email: str,
        task_title: str,
    ) -> None:
        nonlocal attempts
        attempts += 1
        assert smtp_host == "smtp.example.com"
        assert recipient_email == "assignee@example.com"
        assert task_title == "Retry task"
        if attempts < 3:
            raise OSError("SMTP is temporarily unavailable")

    monkeypatch.setattr(
        notifications,
        "_send_assignment_email_sync",
        fake_send_assignment_email_sync,
    )

    await notifications.send_assignment_email_with_retry("assignee@example.com", "Retry task")

    assert attempts == 3
    get_settings.cache_clear()


@pytest.mark.asyncio
async def test_core_endpoint_rbac_matrix(client: AsyncClient) -> None:
    admin = await register_user(client, "matrix-admin@example.com", "Matrix Admin")
    owner = await register_user(client, "matrix-owner@example.com", "Matrix Owner")
    editor = await register_user(client, "matrix-editor@example.com", "Matrix Editor")
    viewer = await register_user(client, "matrix-viewer@example.com", "Matrix Viewer")
    await register_user(client, "matrix-outsider@example.com", "Matrix Outsider")
    assert admin["role"] == "ADMIN"
    assert owner["role"] == "MEMBER"

    role_headers = {
        "admin": await login_headers(client, "matrix-admin@example.com"),
        "owner": await login_headers(client, "matrix-owner@example.com"),
        "editor": await login_headers(client, "matrix-editor@example.com"),
        "viewer": await login_headers(client, "matrix-viewer@example.com"),
        "outsider": await login_headers(client, "matrix-outsider@example.com"),
    }
    workspace_id, project_id = await create_workspace_and_project(
        client,
        role_headers["owner"],
        workspace_name="RBAC Matrix Workspace",
        project_name="RBAC Matrix Project",
    )

    for user, role in ((editor, "EDITOR"), (viewer, "VIEWER")):
        invite_response = await client.post(
            f"/api/v1/workspaces/{workspace_id}/members",
            json={"user_id": user["id"], "role": role},
            headers=role_headers["owner"],
        )
        assert invite_response.status_code == 201

    task_response = await client.post(
        f"/api/v1/projects/{project_id}/tasks",
        json={"title": "Matrix task", "assignee_id": viewer["id"]},
        headers=role_headers["owner"],
    )
    assert task_response.status_code == 201
    task_id = task_response.json()["id"]

    label_response = await client.post(
        f"/api/v1/projects/{project_id}/labels",
        json={"name": "matrix", "color": "#3366ff"},
        headers=role_headers["owner"],
    )
    assert label_response.status_code == 201
    label_id = label_response.json()["id"]

    async def assert_role_statuses(
        method: str,
        path: str,
        expected: dict[str, int],
        json_factory: Callable[[str], dict[str, Any] | None] | None = None,
    ) -> None:
        for role, headers in role_headers.items():
            response = await client.request(
                method,
                path,
                json=json_factory(role) if json_factory is not None else None,
                headers=headers,
            )
            assert response.status_code == expected[role], (
                method,
                path,
                role,
                response.text,
            )

    read_access = {"admin": 200, "owner": 200, "editor": 200, "viewer": 200, "outsider": 403}
    admin_only = {"admin": 200, "owner": 403, "editor": 403, "viewer": 403, "outsider": 403}
    owner_only = {"admin": 200, "owner": 200, "editor": 403, "viewer": 403, "outsider": 403}
    write_access = {"admin": 200, "owner": 200, "editor": 200, "viewer": 403, "outsider": 403}
    create_access = {"admin": 201, "owner": 201, "editor": 201, "viewer": 403, "outsider": 403}

    await assert_role_statuses("GET", "/api/v1/users", admin_only)
    await assert_role_statuses(
        "PATCH",
        f"/api/v1/users/{viewer['id']}",
        admin_only,
        lambda role: {"full_name": f"Matrix Viewer {role}"},
    )
    await assert_role_statuses("GET", f"/api/v1/workspaces/{workspace_id}", read_access)
    await assert_role_statuses("GET", f"/api/v1/workspaces/{workspace_id}/members", read_access)
    await assert_role_statuses(
        "PATCH",
        f"/api/v1/workspaces/{workspace_id}",
        owner_only,
        lambda role: {"name": f"RBAC Matrix Workspace {role}"},
    )
    await assert_role_statuses(
        "GET",
        f"/api/v1/workspaces/{workspace_id}/projects",
        read_access,
    )
    await assert_role_statuses("GET", f"/api/v1/projects/{project_id}", read_access)
    await assert_role_statuses(
        "PATCH",
        f"/api/v1/projects/{project_id}",
        write_access,
        lambda role: {"description": f"Updated by {role}"},
    )
    await assert_role_statuses(
        "POST",
        f"/api/v1/projects/{project_id}/archive",
        write_access,
    )
    await assert_role_statuses("GET", f"/api/v1/projects/{project_id}/tasks", read_access)
    await assert_role_statuses(
        "POST",
        f"/api/v1/projects/{project_id}/tasks",
        create_access,
        lambda role: {"title": f"Created by {role}"},
    )
    await assert_role_statuses(
        "PATCH",
        f"/api/v1/tasks/{task_id}",
        write_access,
        lambda role: {"title": f"Retitled by {role}"},
    )

    assignee_status_access = {
        "admin": 200,
        "owner": 200,
        "editor": 200,
        "viewer": 200,
        "outsider": 403,
    }
    await assert_role_statuses(
        "PATCH",
        f"/api/v1/tasks/{task_id}",
        assignee_status_access,
        lambda role: {"status": "IN_PROGRESS" if role != "editor" else "IN_REVIEW"},
    )
    await assert_role_statuses("GET", f"/api/v1/projects/{project_id}/labels", read_access)
    await assert_role_statuses(
        "POST",
        f"/api/v1/projects/{project_id}/labels",
        create_access,
        lambda role: {"name": f"label-{role}", "color": "#33aa66"},
    )
    await assert_role_statuses(
        "POST",
        f"/api/v1/tasks/{task_id}/labels/{label_id}",
        write_access,
    )
    await assert_role_statuses("GET", f"/api/v1/tasks/{task_id}/comments", read_access)

    assignee_comment_access = {
        "admin": 201,
        "owner": 201,
        "editor": 201,
        "viewer": 201,
        "outsider": 403,
    }
    await assert_role_statuses(
        "POST",
        f"/api/v1/tasks/{task_id}/comments",
        assignee_comment_access,
        lambda role: {"content": f"Comment by {role}"},
    )

    async def create_comment_for_delete() -> int:
        response = await client.post(
            f"/api/v1/tasks/{task_id}/comments",
            json={"content": "Delete permission target"},
            headers=role_headers["owner"],
        )
        assert response.status_code == 201
        return int(response.json()["id"])

    delete_comment_expected = {
        "admin": 204,
        "owner": 204,
        "editor": 204,
        "viewer": 403,
        "outsider": 403,
    }
    for role, expected_status in delete_comment_expected.items():
        comment_id = await create_comment_for_delete()
        response = await client.delete(
            f"/api/v1/comments/{comment_id}",
            headers=role_headers[role],
        )
        assert response.status_code == expected_status

    delete_project_counter = 1

    async def create_project_for_delete() -> int:
        nonlocal delete_project_counter
        response = await client.post(
            f"/api/v1/workspaces/{workspace_id}/projects",
            json={"name": f"Delete Project {delete_project_counter}"},
            headers=role_headers["owner"],
        )
        delete_project_counter += 1
        assert response.status_code == 201
        return int(response.json()["id"])

    delete_project_expected = {
        "admin": 204,
        "owner": 204,
        "editor": 204,
        "viewer": 403,
        "outsider": 403,
    }
    for role, expected_status in delete_project_expected.items():
        delete_project_id = await create_project_for_delete()
        response = await client.delete(
            f"/api/v1/projects/{delete_project_id}",
            headers=role_headers[role],
        )
        assert response.status_code == expected_status
