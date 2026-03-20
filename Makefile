.PHONY: dev dev-agent dev-simulation dev-frontend dev-ml install install-frozen install-infra \
	check check-agent check-frontend check-simulation check-ml \
	check-fix check-agent-fix check-frontend-fix check-simulation-fix \
	codegen check-codegen deploy destroy synth

dev-simulation:
	@cd simulation && AGENT_URL=$${AGENT_URL:-http://localhost:9090} uv run uvicorn main:app --reload --port 8080

dev-agent:
	@cd agent && uv run uvicorn src.main:app --reload --port 9090

dev-ml:
	@cd ml && uv run uvicorn serve:app --reload --port 8090

dev-frontend:
	@cd frontend && pnpm dev --port 5173

dev:
	@trap 'kill 0' INT TERM; \
	make dev-simulation & \
	make dev-ml & \
	make dev-frontend & \
	echo "[dev] waiting for simulation on :8080…"; \
	until curl -sf http://localhost:8080/health > /dev/null 2>&1; do sleep 0.5; done; \
	echo "[dev] simulation ready — starting agent"; \
	make dev-agent & \
	wait

install-infra:
	@cd infra && uv sync

install:
	@cd agent && uv sync
	@cd simulation && uv sync
	@cd ml && uv sync
	@cd frontend && pnpm install
	@cd infra && uv sync

install-frozen:
	@cd agent && uv sync --frozen
	@cd simulation && uv sync --frozen
	@cd ml && uv sync --frozen
	@cd frontend && pnpm install --frozen-lockfile

check-agent:
	@cd agent && uv run ruff check src && uv run ruff format --check src && uv run pyright src

check-frontend:
	@cd frontend && npx oxfmt --check src && npx oxlint src && npx tsc --noEmit

check-simulation:
	@cd simulation && uv run ruff check src main.py && uv run ruff format --check src main.py && uv run pyright src main.py

check-ml:
	@cd ml && uv run ruff check serve.py && uv run ruff format --check serve.py && uv run pyright serve.py

check: check-agent check-frontend check-simulation check-ml

check-agent-fix:
	@cd agent && uv run ruff check --fix src && uv run ruff format src

check-frontend-fix:
	@cd frontend && npx oxfmt src && npx oxlint --fix src

check-simulation-fix:
	@cd simulation && uv run ruff check --fix src main.py && uv run ruff format src main.py

check-fix: check-agent-fix check-frontend-fix check-simulation-fix

codegen:
	@cd simulation && uv run python -m scripts.export_openapi > /tmp/oasis-openapi.json
	@cd frontend && pnpm exec openapi-typescript /tmp/oasis-openapi.json -o src/contracts/simulation.d.ts --export-type
	@cd frontend && pnpm exec oxfmt src/contracts/simulation.d.ts

check-codegen:
	@make codegen
	@git diff --exit-code frontend/src/contracts/simulation.d.ts

deploy:
	@cd infra && npx cdk deploy --require-approval never $(if $(GITHUB_TOKEN),-c github_token=$(GITHUB_TOKEN),)

destroy:
	@cd infra && npx cdk destroy --force

synth:
	@cd infra && npx cdk synth
