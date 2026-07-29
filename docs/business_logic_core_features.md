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

## Still Optional

- Real queue worker integration such as Celery/RQ/Arq.
- Exhaustive RBAC tests for every endpoint and role permutation.
- Production email provider templates and retry policy.
