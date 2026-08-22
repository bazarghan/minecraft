# Ubuntu deployment

## Prepare the host

Use a supported Ubuntu LTS host dedicated to trusted administrators. Point a DNS A/AAAA record at it. Install Docker Engine and the Compose plugin using Docker's official Ubuntu instructions. Do not enable an unauthenticated Docker TCP listener.

Allow inbound TCP 80 and 443 for Caddy. Allow only the selected Minecraft TCP ports (automatic allocation uses 25565–26000). PostgreSQL, Redis, backend, Docker, and RCON ports must remain blocked.

Create persistent roots for the unprivileged application UID:

```bash
sudo install -d -o 10001 -g 10001 -m 0750 \
  /srv/minecraft-manager/servers \
  /srv/minecraft-manager/maps/incoming \
  /srv/minecraft-manager/backups
getent group docker | cut -d: -f3   # place this numeric value in DOCKER_GID
```

## Configure and start

Copy `.env.example` to `.env`, replace every placeholder, and restrict it to the deployment administrator (`chmod 600 .env`). Generate `MSM_SECRET_KEY`, `MSM_ENCRYPTION_KEY`, and the database password independently. Losing the encryption key makes stored RCON credentials unrecoverable; protect it in an external secret backup.

```bash
docker compose config                 # inspect the rendered configuration
docker compose up -d --build
docker compose ps
docker compose exec backend minecraft-manager bootstrap-admin
```

The optional `MSM_INITIAL_ADMIN_*` values support unattended first boot only. Remove them from `.env` immediately after successful bootstrap and recreate the services.

## Upgrade and rollback

Create database and off-host world backups first. Then fetch the desired signed/tagged release, review `CHANGELOG.md`, and run `docker compose build --pull` followed by `docker compose up -d`. The backend applies forward Alembic migrations before starting.

For rollback, stop management services, restore the database backup that matches the old release, check out that release, rebuild, and start. Do not downgrade database migrations in place without a verified backup.

## Backup policy

Application backups protect world data but remain on the same host by default. Copy checksummed backup files and PostgreSQL dumps to encrypted off-host storage. Test a restore regularly. Retention is configured in Host settings; external lifecycle rules remain the operator's responsibility.

## Docker warning

Anyone who can control the backend or worker can effectively control the host through Docker. Restrict SSH, repository deployment credentials, Compose permissions, and administrator accounts accordingly.
