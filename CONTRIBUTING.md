# Contributing

Thank you for helping improve Minecraft Server Manager.

## Before opening a change

1. Search existing issues and security notices.
2. For vulnerabilities, follow `SECURITY.md`; do not open a public issue.
3. Keep changes focused and avoid proprietary Minecraft artwork or redistributed maps.
4. Preserve the trust boundary: browsers never access Docker, and containers without all ownership labels are never managed.

## Development workflow

Fork the project, branch from `main`, and use clear commits. Install locked dependencies with `uv sync --extra test --frozen` in `backend` and `npm ci` in `frontend`. Run `uv run pytest`, `npm run typecheck`, `npm run lint`, and `npm run build` before opening a pull request. Tests must not require an interactive browser or a local Docker daemon.

Update documentation, migrations, `.env.example`, and `CHANGELOG.md` when behavior or configuration changes. Pull requests must explain security impact, database changes, and a rollback path.

By contributing, you agree that your contribution is licensed under Apache-2.0 and to follow the `CODE_OF_CONDUCT.md`.
