.PHONY: dev dev-agent dev-simulation dev-frontend install

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
