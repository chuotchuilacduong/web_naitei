# Session 1-2 Deliverable

This milestone covers the first two sessions from `web_req_editable.docx`.

## Session 1: Core Setup & Architecture

Implemented:

- Layered project structure:
  - `app/main.py`: FastAPI application instance, lifespan hook, middleware, exception handlers.
  - `app/api/v1/router.py`: versioned API router.
  - `app/api/v1/endpoints/`: request handlers grouped by resource.
  - `app/schemas/`: Pydantic v2 request and response schemas.
  - `app/services/`: business and permission logic.
  - `app/repositories/`: database access layer.
  - `app/db/`: SQLAlchemy models and async session setup.
  - `app/core/`: configuration, security, logging, Redis helper, exception handling.
- APIRouter-based routing under `/api/v1`.
- Dependency injection for database sessions and authenticated users in `app/api/deps.py`.
- Pydantic v2 schemas with `ConfigDict(from_attributes=True)` for ORM responses.
- Basic CRUD endpoints are available for the `Workspace` resource:
  - `POST /api/v1/workspaces`
  - `GET /api/v1/workspaces`
  - `GET /api/v1/workspaces/{workspace_id}`
  - `PATCH /api/v1/workspaces/{workspace_id}`
  - `DELETE /api/v1/workspaces/{workspace_id}`

Run locally:

```powershell
conda activate taskhub-fastapi
$env:TASKHUB_DATABASE_URL='sqlite+aiosqlite:///./taskhub.db'
$env:TASKHUB_REDIS_ENABLED='false'
alembic upgrade head
uvicorn app.main:app --reload
```

## Session 2: Database, SQLAlchemy 2.x & Alembic

Implemented:

- SQLAlchemy 2.x async engine/session in `app/db/session.py`.
- Declarative ORM models in `app/db/models.py`.
- Main TaskHub entities:
  - `users`
  - `refresh_tokens`
  - `workspaces`
  - `workspace_members`
  - `projects`
  - `tasks`
  - `labels`
  - `task_labels`
  - `comments`
- Relationships:
  - User owns workspaces.
  - Workspace has members and projects.
  - Project has tasks and labels.
  - Task has assignee, creator, labels, and comments.
  - Label is attached to tasks through `task_labels`.
- Repository pattern:
  - `BaseRepository[ModelT]` with async CRUD helpers.
  - Resource repositories for users, workspaces, projects, tasks, labels, comments, refresh tokens.
  - Task filtering and pagination query support in `TaskRepository`.
- Alembic async environment:
  - `alembic.ini`
  - `alembic/env.py`
  - `alembic/versions/202607280001_initial_taskhub_schema.py`
- Database integration with FastAPI through `get_db()` dependency.

Migration command:

```powershell
conda activate taskhub-fastapi
alembic upgrade head
```

## Verification

Commands used for this milestone:

```powershell
ruff check .
mypy app tests
pytest
```

Smoke coverage:

- Register and login user.
- Create workspace.
- Create project inside workspace.
- Create and filter task.
- Create label and attach it to task.
- Create comment.
- Update task status.
