# Architecture

## Components and trust boundaries

Caddy is the only public management-plane component. It terminates HTTPS and routes `/api/*` and `/healthz` to FastAPI; all other paths go to the static React service. PostgreSQL, Redis, the backend, and frontend use an internal Compose network and publish no host ports.

FastAPI owns authentication, authorization, validation, audit recording, capacity decisions, and Docker orchestration. Celery workers perform durable map, backup, restore, and reconciliation work. PostgreSQL is authoritative for configuration and reservations; Redis is transport and result storage, not the source of truth.

The Docker socket is mounted only into the backend and worker. This socket is root-equivalent. `DockerControl` is the sole Docker SDK boundary and accepts only containers with all of:

```text
com.minecraft-manager.managed=true
com.minecraft-manager.project=minecraft-server-manager
com.minecraft-manager.server-id=<database UUID>
```

The browser never selects an image. `itzg/minecraft-server:java25` is forced for 26.1.1; other accepted versions use the project allowlist. RCON is enabled inside each container but never published. A random per-server password is encrypted with the application encryption key.

## Data model

Users own revocable server-side sessions. Audit events are append-only application records. Minecraft server rows retain the configured reservation even when stopped. Maps and backups retain SHA-256 checksums and controlled storage paths. Background jobs retain state, progress, safe errors, and results.

World data lives at `/srv/minecraft-manager/servers/<server UUID>` on the host, separate from container lifecycle. Maps and backups have separate roots. Recreating or removing a container never deletes the server directory. Permanent deletion is a separate, name-confirmed action.

## Consistency and concurrency

PostgreSQL row locks serialize lifecycle changes per server. A PostgreSQL advisory transaction lock serializes memory and port allocation. Transitional states reject conflicting operations. Periodic reconciliation compares only labeled Docker containers with database state after restarts.

Map installation stops the server, creates a backup, extracts into staging, validates `level.dat`, swaps the world directory, rolls back copy failures, and starts only after successful installation when requested. Restores similarly create a safety backup first.

## Security design

Passwords use Argon2id. Opaque session tokens are stored only as SHA-256 hashes; the raw value lives in a Secure, HttpOnly, SameSite=Strict cookie. A separate CSRF token is stored only in frontend memory and rotated after page load. Login attempts are limited by IP in Redis and repeated account failures trigger temporary database lockout.

URL imports accept only HTTP(S) on standard ports, validate DNS answers as globally routable on every redirect, disable automatic redirects, stream with limits and timeouts, and clean staging on failure. ZIP intake rejects traversal, absolute paths, links, excess file counts, expansion limits, and suspicious compression ratios.
