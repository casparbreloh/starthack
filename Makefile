.PHONY: dev dev-agent dev-simulation dev-frontend install

dev-simulation:
	@cd simulation && uv run uvicorn main:app --reload --port 8080

dev-agent:
	@cd agent && uv run uvicorn src.main:app --reload --port 9090

dev-frontend:
	@cd frontend && pnpm dev --port 5173

dev:
	@trap 'kill 0' INT TERM; \
	make dev-agent & make dev-simulation & make dev-frontend & wait

install:
	@cd agent && uv sync
	@cd simulation && uv sync
	@cd frontend && pnpm install
