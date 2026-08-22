# Minecraft Server Manager

Minecraft Server Manager is a security-focused, self-hosted control plane for Minecraft Java Edition servers. Administrators can reserve host capacity, provision allowlisted `itzg/minecraft-server` containers, watch live state, send RCON commands, import parkour maps, and create or restore checksummed backups from a responsive web interface.

> **Independent community project:** This project is not affiliated with, endorsed by, or sponsored by Mojang Studios or Microsoft. Minecraft is a trademark of Microsoft. No proprietary Minecraft art, logos, textures, or map content are included.

## What it includes

- React, TypeScript, and Vite frontend with accessible mobile layouts and disconnected/error states
- FastAPI REST API under `/api/v1`, consistent errors, request IDs, SSE updates, and optional OpenAPI UI
- PostgreSQL via SQLAlchemy/Alembic; Redis-backed durable Celery work queue
- Admin, operator, and viewer roles; Argon2id passwords; server-side sessions; CSRF; lockout and IP rate limits
- Docker SDK-only lifecycle control with three ownership labels checked before every operation
- Host memory reservation including stopped servers, allocation locking, and overcommit disabled by default
- Safe URL and ZIP map intake, pre-install backup, rollback, and optional restart
- Manual/safety backups, checksums, download, restore, audit events, and job progress
- Docker Compose deployment with Caddy-managed HTTPS and no published database, Redis, RCON, Docker API, or backend ports

## Architecture at a glance

```text
Internet ── HTTPS ── Caddy ─┬─ React frontend
                            └─ FastAPI ── PostgreSQL
                                  │       Redis/Celery
                                  └─ Docker socket (private, root-equivalent)
                                          └─ labeled Minecraft containers
```

Only the backend and worker can access Docker. Minecraft gameplay ports are allocated directly on the Ubuntu host; RCON remains unpublished. See [Architecture](docs/ARCHITECTURE.md) and [Security](SECURITY.md) before deploying.

## Production deployment

Requirements: an Ubuntu server, a DNS name pointing to it, Docker Engine with Compose v2, and inbound TCP 80/443 plus only the Minecraft ports you intend to expose. Docker is required **only on the target Ubuntu host**; no Docker setup is needed on a development Mac.

```bash
cp .env.example .env
# Replace every <...> placeholder. Generate each application key separately:
openssl rand -hex 32
sudo install -d -o 10001 -g 10001 -m 0750 \
  /srv/minecraft-manager/servers /srv/minecraft-manager/maps /srv/minecraft-manager/backups
docker compose up -d --build
docker compose exec backend minecraft-manager bootstrap-admin
```

Do not pass the bootstrap password on the command line. The interactive command reads it without echoing it. Full instructions, firewall guidance, upgrades, restore drills, and rollback steps are in [Deployment](docs/DEPLOYMENT.md).

## Local command-line development

The application can be inspected and tested without Docker. Python tests do not contact Docker, PostgreSQL, or Redis:

```bash
cd backend
uv sync --extra test --frozen
uv run pytest

cd ../frontend
npm ci
npm run typecheck
npm run build
```

No interactive browser test is required. The repository intentionally supplies CLI-focused pytest coverage for authentication primitives, validation, archive safety, SSRF blocking, and Docker ownership enforcement.

## Administrator safety notes

- Access to the Docker API is effectively root-equivalent access to the host. Never expose `/var/run/docker.sock`, a Docker TCP listener, or a socket proxy.
- Offline mode permits username impersonation. A whitelist does not prevent it. Keep offline-mode servers private.
- Minecraft server creation requires explicit EULA acceptance. Review the [Minecraft EULA](https://aka.ms/MinecraftEULA).
- Memory reservations include stopped servers; a 2 GB container receives about 1536 MB maximum Java heap.
- Permanent deletion requires the exact server name and is not recoverable through this application. Maintain off-host backups.

## Documentation

- [Architecture](docs/ARCHITECTURE.md)
- [REST API](docs/API.md)
- [Deployment](docs/DEPLOYMENT.md)
- [Operations and troubleshooting](docs/TROUBLESHOOTING.md)
- [Contributing](CONTRIBUTING.md)
- [Security policy](SECURITY.md)

## License

Licensed under the [Apache License 2.0](LICENSE).
