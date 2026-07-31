# Business Logic & Core Features

This document tracks the gap between the current API and the Business Logic &
Core Features section in `web_req_editable.docx`.

## Gaps Found

- Notification domain was missing from the database and API, although the sample
  app domain mentions notifications.
- Task assignment only logged a background email event; no persistent in-app
  notification existed.
- `ADMIN` RBAC existed in permission checks, but there was no API surface to
  exercise admin user management.
- OpenAPI docs relied on endpoint-specific responses; common error responses
  were not documented consistently across the app.
- First-user bootstrap for an admin account was not explicit.

## Completed

- Added first-user admin bootstrap with `TASKHUB_FIRST_USER_IS_ADMIN`.
- Added admin user endpoints:
  - `GET /api/v1/users`
  - `PATCH /api/v1/users/{user_id}`
- Added notification persistence:
  - `notifications` table
  - task assignment notification creation
  - notification repository and schemas
- Added notification endpoints:
  - `GET /api/v1/notifications/me`
  - `PATCH /api/v1/notifications/{notification_id}/read`
  - `PATCH /api/v1/notifications/me/read-all`
- Added configurable SMTP-backed background assignment email:
  - local/default mode logs the queued email
  - SMTP mode sends mail when enabled by env vars
- Added global OpenAPI error response documentation for common error cases.
- Added focused RBAC regression coverage for admin-only user management,
  workspace OWNER/EDITOR/VIEWER behavior, outsider denial, and assignee-limited
  task updates/comments.
- Added regression coverage for auth token rotation/logout/password changes,
  Redis task-list cache hit/invalidation, project archive, label detach/delete,
  comment/task/project/workspace deletion, and member removal.
- Added optional ARQ/Redis queue worker support for assignment email jobs, with
  FastAPI background task fallback when queueing is disabled or Redis is
  unavailable.
- Added text/html assignment email templates plus configurable retry policy.
- Added broader role matrix regression coverage across admin-only,
  owner-only, workspace read, workspace write, assignee-specific, and delete
  behaviors.

## Future Hardening

- Run `docker compose up --build` in an environment with Docker CLI available.
- Add provider-specific transactional email templates if adopting a vendor such
  as SES, SendGrid, or Mailgun.
- Add observability around queue depth, failed jobs, and email delivery metrics.
