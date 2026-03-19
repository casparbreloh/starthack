.PHONY: dev dev-agent dev-simulation dev-frontend install \
	check check-agent check-frontend check-simulation \
	check-fix check-agent-fix check-frontend-fix check-simulation-fix

dev-agent:
	@cd agent && uv run python -m src

dev-simulation:
	@cd simulation && uv run uvicorn main:app --reload

dev-frontend:
	@cd frontend && pnpm dev

dev:
	@trap 'kill 0' INT TERM; \
	make dev-agent & make dev-simulation & make dev-frontend & wait

install:
	@cd agent && uv sync
	@cd simulation && uv sync
	@cd frontend && pnpm install

check-agent:
	@cd agent && uv run ruff check src && uv run ruff format --check src && uv run pyright src

check-frontend:
	@cd frontend && npx oxfmt --check && npx oxlint && npx tsc --noEmit

check-simulation:
	@cd simulation && uv run ruff check src main.py && uv run ruff format --check src main.py && uv run pyright src main.py

check: check-agent check-frontend check-simulation

check-agent-fix:
	@cd agent && uv run ruff check --fix src && uv run ruff format src

check-frontend-fix:
	@cd frontend && npx oxfmt && npx oxlint --fix

check-simulation-fix:
	@cd simulation && uv run ruff check --fix src main.py && uv run ruff format src main.py

check-fix: check-agent-fix check-frontend-fix check-simulation-fix
