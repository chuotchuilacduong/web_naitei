# TaskHub API

TaskHub is a FastAPI sample app for task management. It implements users,
workspaces, workspace members, projects, tasks, labels, comments, notifications,
JWT auth, RBAC, Redis caching, Alembic migrations, and Docker Compose for
PostgreSQL 16 and Redis 7.

## Local setup with Conda

```powershell
conda env create -f environment.yml
conda activate taskhub-fastapi
copy .env.example .env
alembic upgrade head
uvicorn app.main:app --reload
```

The API runs at `http://127.0.0.1:8000`.

Docs:

- Swagger UI: `http://127.0.0.1:8000/docs`
- ReDoc: `http://127.0.0.1:8000/redoc`

For quick local checks without PostgreSQL, set this in `.env`:

```env
TASKHUB_DATABASE_URL=sqlite+aiosqlite:///./taskhub.db
TASKHUB_REDIS_ENABLED=false
```

The first registered user is created as `ADMIN` by default. Change
`TASKHUB_FIRST_USER_IS_ADMIN=false` if you want every registered user to start as
`MEMBER`.

## Docker

```powershell
docker compose up --build
```

Compose starts:

- `app`: FastAPI app on port 8000
- `db`: PostgreSQL 16 on port 5432
- `redis`: Redis 7 on port 6379

The app runs `alembic upgrade head` before starting Uvicorn.

## Main endpoints

Session 1-2 implementation notes are documented in `docs/session_1_2.md`.
Business logic and core feature gaps are tracked in
`docs/business_logic_core_features.md`.

- `POST /api/v1/auth/register`
- `POST /api/v1/auth/login`
- `POST /api/v1/auth/refresh`
- `POST /api/v1/auth/logout`
- `GET /api/v1/users/me`
- `PATCH /api/v1/users/me`
- `POST /api/v1/users/me/change-password`
- `GET /api/v1/users`
- `PATCH /api/v1/users/{user_id}`
- `POST /api/v1/workspaces`
- `GET /api/v1/workspaces/{workspace_id}`
- `POST /api/v1/workspaces/{workspace_id}/members`
- `DELETE /api/v1/workspaces/{workspace_id}/members/{user_id}`
- `POST /api/v1/workspaces/{workspace_id}/projects`
- `GET /api/v1/projects/{project_id}/tasks`
- `POST /api/v1/projects/{project_id}/tasks`
- `PATCH /api/v1/tasks/{task_id}`
- `DELETE /api/v1/tasks/{task_id}`
- `POST /api/v1/tasks/{task_id}/labels/{label_id}`
- `POST /api/v1/tasks/{task_id}/comments`
- `GET /api/v1/notifications/me`
- `PATCH /api/v1/notifications/{notification_id}/read`
- `PATCH /api/v1/notifications/me/read-all`

## Quality checks

```powershell
ruff format .
ruff check .
mypy app tests
pytest
```

## RBAC summary

Global `ADMIN` can access all resources. Workspace `OWNER` can manage the
workspace and members. `OWNER` and `EDITOR` can create and edit projects, tasks,
labels, and comments. `VIEWER` can read workspace content. Task assignees can
update task status and comment on assigned tasks.

## Cache strategy

`GET /api/v1/projects/{project_id}/tasks` is cached in Redis by project, filter,
page, and limit. Any task mutation or task-label change invalidates all cached
task pages for that project.
