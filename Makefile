.PHONY: test typecheck build check

test:
	cd backend && uv run --frozen --extra test pytest

typecheck:
	cd frontend && npm run typecheck

build:
	cd frontend && npm run build

check: test typecheck build
