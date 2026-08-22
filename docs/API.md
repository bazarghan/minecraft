# REST API

The versioned API is rooted at `/api/v1`. Production OpenAPI is disabled by default. Set `MSM_DOCS_ENABLED=true` only on a protected installation to expose `/api/docs` and `/api/openapi.json`.

## Authentication

`POST /auth/login` accepts a username and password, sets the HttpOnly session cookie, and returns the current user plus an in-memory CSRF token. `POST /auth/csrf` rotates that token for an existing cookie session. Mutating endpoints require `X-CSRF-Token`. `POST /auth/logout`, `POST /auth/password`, `GET /auth/sessions`, and `DELETE /auth/sessions/{id}` manage the account lifecycle.

Roles are cumulative: viewers read fleet state; operators run Minecraft, map, backup, and console operations; administrators also manage users, roles, settings, and the full audit log. Unauthorized requests return 401 or 403.

## Resources

- `GET/POST /servers`, `GET/PATCH/DELETE /servers/{id}` — configuration and container-preserving deletion
- `POST /servers/{id}/start|stop|restart|force-stop|duplicate` — validated lifecycle actions
- `DELETE /servers/{id}/data` — permanent name-confirmed data deletion after container removal
- `GET /servers/{id}/metrics|logs|logs/download`, `POST /servers/{id}/console`
- `GET /host/capacity|metrics`, `GET /events` — snapshot and SSE stream
- `GET/POST/PATCH /users`, `GET /users/roles`
- `GET /maps`, `POST /maps/upload|url|library`, `POST /maps/{id}/install`
- `GET /backups`, `POST /backups/servers/{id}`, `GET /backups/{id}/download`, `POST /backups/{id}/restore`
- `GET /jobs`, `GET /jobs/{id}`, `GET /audit`, `GET/PATCH /settings`

Collection endpoints accept non-negative `offset` and a `limit` capped at 100.

## Errors and tracing

Every response includes `X-Request-ID`. Clients may supply one; it is limited to 64 characters. Errors have one shape:

```json
{
  "error": {
    "code": "validation_error",
    "message": "Request validation failed",
    "request_id": "c8dd…",
    "details": {"fields": [{"path": "body.slug", "message": "…"}]}
  }
}
```

Internal exception text and RCON credentials are never returned.
