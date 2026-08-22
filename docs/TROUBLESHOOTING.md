# Operations and troubleshooting

## Use the request ID first

Safe UI errors include a request ID. Match it against backend or worker logs on the Ubuntu host. Do not paste `.env`, cookies, RCON output containing secrets, or full world archives into public issues.

## HTTPS does not start

Confirm the DNS record points to the host and TCP 80/443 are reachable. Check Caddy logs and certificate-rate-limit messages. `MSM_DOMAIN` must be a hostname, not a URL.

## Backend cannot access Docker

Confirm `/var/run/docker.sock` exists and `DOCKER_GID` matches its group ID. Access is intentionally not widened to world-writable. Never solve this by exposing a Docker TCP socket.

## Capacity refusal

The allocator subtracts the Ubuntu/application reserve and every non-deleted server reservation, including stopped servers. Delete unused server records/data only after backups, lower reservations through a controlled recreate workflow, or add physical memory. Overcommit is intentionally off and should rarely be enabled.

## A server fails to start

Open the server logs, verify the selected version/type combination, disk free space, port availability, and memory. Minecraft 26.1.1 uses `itzg/minecraft-server:java25`. The manager never manipulates an existing unrelated container when labels do not match.

## Map import fails

The direct URL must be HTTP(S), use a public address on standard ports, complete within configured limits, and return a ZIP. The archive must contain exactly one plausible world with `level.dat`, without links, traversal, extreme expansion, or too many files. Redirects are revalidated.

## Restore recovery directory exists

Do not delete it blindly. Stop the server and inspect the current and `.restore-old`/`.map-old` directories against checksums and the job error. Move the verified copy into place during a maintenance window, then retain the other until the server is confirmed healthy.

## Database or Redis unavailable

Check their Compose health status and available disk. PostgreSQL is authoritative. Redis loss may require re-queueing incomplete jobs; never mark a destructive job successful without verifying its database result and filesystem state.
