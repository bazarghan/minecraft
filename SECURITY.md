# Security policy

## Supported versions

Until 1.0, only the latest commit on `main` receives security fixes. Stable release support will be documented here once releases begin.

## Reporting a vulnerability

Use GitHub private vulnerability reporting for `bazarghan/minecraft`. Do not disclose the issue publicly until a fix is available. Include the affected version, reproduction steps, impact, and any proposed mitigation. Avoid accessing data you do not own and stop testing if it could damage a world or host.

Maintainers aim to acknowledge a report within 5 business days and will coordinate disclosure after triage. No bounty is promised.

## Critical trust boundaries

The Docker API grants root-equivalent host control. Never expose the socket, Docker TCP API, or a socket proxy to a public or user-facing network. Only the backend and worker may mount the socket. All actions must verify the managed, project, and server-ID labels.

RCON passwords are unique, randomly generated, encrypted at rest, and never published as ports. Browser sessions use Secure, HttpOnly, SameSite=Strict cookies; CSRF tokens are kept only in memory. Secrets belong only in environment variables or Docker secrets, never Git.

URL imports must retain redirect-by-redirect public-IP validation, strict time/size bounds, and staging cleanup. ZIP handling must retain traversal, link, file-count, expansion, and compression-ratio controls.
