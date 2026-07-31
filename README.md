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
- `worker`: ARQ worker that processes queued background jobs
- `db`: PostgreSQL 16 on port 5432
- `redis`: Redis 7 on port 6379

The app runs `alembic upgrade head` before starting Uvicorn.

After the stack is up, verify it with:

```powershell
curl http://127.0.0.1:8000/health
curl http://127.0.0.1:8000/openapi.json
```

Use `docker compose logs -f app` if the API container exits during startup.
Use `docker compose logs -f worker` to inspect background job processing.

## Configuration

All settings use the `TASKHUB_` environment prefix and can be placed in `.env`
for local runs.

| Variable | Default | Purpose |
| --- | --- | --- |
| `TASKHUB_ENVIRONMENT` | `local` | App environment: `local`, `test`, `staging`, or `production`. |
| `TASKHUB_DATABASE_URL` | `sqlite+aiosqlite:///./taskhub.db` | Async SQLAlchemy database URL. |
| `TASKHUB_SQL_ECHO` | `false` | Enables SQLAlchemy query logging. |
| `TASKHUB_REDIS_URL` | `redis://localhost:6379/0` | Redis URL for task-list caching. |
| `TASKHUB_REDIS_ENABLED` | `true` | Enables Redis cache; set `false` for SQLite-only checks. |
| `TASKHUB_CACHE_TTL_SECONDS` | `60` | TTL for cached task-list pages. |
| `TASKHUB_QUEUE_ENABLED` | `false` | Enqueues assignment emails through Redis/ARQ when enabled. |
| `TASKHUB_QUEUE_NAME` | `taskhub:queue` | ARQ queue name used by the API and worker. |
| `TASKHUB_QUEUE_JOB_TIMEOUT_SECONDS` | `30` | Maximum runtime for queued jobs. |
| `TASKHUB_SECRET_KEY` | development placeholder | JWT signing key; must be changed in production. |
| `TASKHUB_ACCESS_TOKEN_EXPIRE_MINUTES` | `30` | JWT access-token lifetime. |
| `TASKHUB_REFRESH_TOKEN_EXPIRE_DAYS` | `7` | Refresh-token lifetime. |
| `TASKHUB_FIRST_USER_IS_ADMIN` | `true` | Makes the first registered user a global `ADMIN`. |
| `TASKHUB_EMAIL_ENABLED` | `false` | Enables SMTP assignment emails. |
| `TASKHUB_SMTP_HOST` | empty | SMTP host used when email is enabled. |
| `TASKHUB_SMTP_PORT` | `587` | SMTP port. |
| `TASKHUB_SMTP_USERNAME` | empty | Optional SMTP username. |
| `TASKHUB_SMTP_PASSWORD` | empty | Optional SMTP password. |
| `TASKHUB_SMTP_FROM_EMAIL` | `noreply@taskhub.local` | Sender address for assignment emails. |
| `TASKHUB_SMTP_STARTTLS` | `true` | Enables STARTTLS for SMTP delivery. |
| `TASKHUB_EMAIL_MAX_ATTEMPTS` | `3` | Maximum attempts for assignment email delivery. |
| `TASKHUB_EMAIL_RETRY_DELAY_SECONDS` | `5` | Linear retry delay multiplier for email attempts. |

In `production`, startup fails fast if `TASKHUB_SECRET_KEY` still uses the
development placeholder.

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
- `GET /api/v1/workspaces`
- `GET /api/v1/workspaces/{workspace_id}`
- `PATCH /api/v1/workspaces/{workspace_id}`
- `DELETE /api/v1/workspaces/{workspace_id}`
- `GET /api/v1/workspaces/{workspace_id}/members`
- `POST /api/v1/workspaces/{workspace_id}/members`
- `DELETE /api/v1/workspaces/{workspace_id}/members/{user_id}`
- `GET /api/v1/workspaces/{workspace_id}/projects`
- `POST /api/v1/workspaces/{workspace_id}/projects`
- `GET /api/v1/projects/{project_id}`
- `PATCH /api/v1/projects/{project_id}`
- `POST /api/v1/projects/{project_id}/archive`
- `DELETE /api/v1/projects/{project_id}`
- `GET /api/v1/projects/{project_id}/tasks`
- `POST /api/v1/projects/{project_id}/tasks`
- `PATCH /api/v1/tasks/{task_id}`
- `DELETE /api/v1/tasks/{task_id}`
- `GET /api/v1/projects/{project_id}/labels`
- `POST /api/v1/projects/{project_id}/labels`
- `PATCH /api/v1/labels/{label_id}`
- `DELETE /api/v1/labels/{label_id}`
- `POST /api/v1/tasks/{task_id}/labels/{label_id}`
- `DELETE /api/v1/tasks/{task_id}/labels/{label_id}`
- `GET /api/v1/tasks/{task_id}/comments`
- `POST /api/v1/tasks/{task_id}/comments`
- `DELETE /api/v1/comments/{comment_id}`
- `GET /api/v1/notifications/me`
- `PATCH /api/v1/notifications/{notification_id}/read`
- `PATCH /api/v1/notifications/me/read-all`

## Quality checks

```powershell
python -m ruff format --check .
python -m ruff check .
python -m mypy app tests
python -m pytest -q
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

When Redis is unavailable or `TASKHUB_REDIS_ENABLED=false`, the API skips cache
reads/writes and still serves task lists from the database.

## Background Notifications

Task assignment creates a persistent in-app notification for the assignee. The
same event can enqueue an ARQ job for email notification when
`TASKHUB_QUEUE_ENABLED=true`. If queueing is disabled or Redis is unavailable,
the API falls back to a FastAPI background task. By default email delivery is
disabled and the event is logged; set `TASKHUB_EMAIL_ENABLED` and the SMTP
variables above to send text/html assignment emails with retry handling.

Run a worker locally with:

```powershell
arq app.worker.WorkerSettings
```
