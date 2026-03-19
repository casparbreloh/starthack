## Project

Mars Greenhouse Agent System — Syngenta START Hack challenge. Autonomous AI agents manage a Martian greenhouse simulation for a 450-day crew mission (4 astronauts).

## Stack

- **Agent**: Python 3.13+, deployed on AWS AgentCore
- **Simulation**: Python 3.13+, FastAPI, uvicorn
- **Frontend**: React 19, TypeScript 5.9, Vite 8, Tailwind CSS 4
- **ML**: PyTorch 2.10, scikit-learn 1.8, pandas 3.0
- **Package managers**: `uv` (Python), `pnpm` (frontend)

## Structure

- `agent/` — AI agent system: orchestrator + 6 specialist crisis agents (Python, uv)
- `simulation/` — greenhouse simulation API (Python, FastAPI, uv)
- `frontend/` — dashboard UI (React, TypeScript, Vite, pnpm)
- `ml/` — Mars weather prediction ML pipeline + HTTP sidecar service (PyTorch LSTM, FastAPI)
- `docs/` — project references (see below)

## Docs

- `docs/ARCHITECTURE.md` — infrastructure and deployment
- `docs/CHALLENGE.md` — Syngenta START Hack challenge brief
- `docs/mcp-data/` — domain knowledge: Mars environment, crop profiles, nutrition, plant stress, greenhouse scenarios

## Commands

- `make install` — install all dependencies
- `make dev` — run all services in parallel
- `make dev-agent` — run agent only
- `make dev-simulation` — run simulation only
- `make dev-frontend` — run frontend only
- `make dev-ml` — run ML sidecar service only (port 8090)
- `make check` — lint, format-check, and type-check all projects
- `make check-fix` — auto-fix lint and format issues in all projects
- `make codegen` — regenerate TypeScript types from the simulation OpenAPI schema
- `make check-codegen` — regenerate and verify types are up-to-date (used in CI)
- `cd ml && uv run python -m mars_weather.train` — train ML models
- `cd ml && uv run python -m mars_weather.evaluate` — evaluate on test set
- `cd ml && uv run python -m mars_weather.predict` — run predictions

## Where to Look

- Weather prediction logic → `ml/mars_weather/`
- ML sidecar service → `ml/serve.py`
- Agent weather client → `agent/src/weather_integration.py`
- Agent orchestrator → `agent/src/agents/orchestrator.py`
- Specialist crisis agents → `agent/src/agents/`
- Agent tool factories → `agent/src/tools/`
- Simulation sub-models → `simulation/src/models/`
- Challenge requirements → `docs/CHALLENGE.md`
- Crop/nutrition/stress data → `docs/mcp-data/`
- Trained model artifacts → `ml/models/`
- API response models (Pydantic) → `simulation/src/models/responses.py`
- Generated TypeScript types → `frontend/src/contracts/simulation.d.ts`
- Frontend type re-exports → `frontend/src/types/simulation.ts`
- OpenAPI schema export script → `simulation/scripts/export_openapi.py`

## OpenAPI Contracts

Frontend TypeScript types are auto-generated from the simulation's OpenAPI schema:

1. Pydantic response models in `simulation/src/models/responses.py` define the API contract
2. `simulation/scripts/export_openapi.py` extracts the OpenAPI JSON without starting a server
3. `openapi-typescript` generates `frontend/src/contracts/simulation.d.ts` from the schema
4. `frontend/src/types/simulation.ts` re-exports generated types under stable names

When changing an API response shape: update the Pydantic model in `responses.py`, run `make codegen`, and the frontend types update automatically. CI runs `make check-codegen` to enforce types stay in sync.

## Pre-Commit Checks

Before committing and pushing, always run `make check` to catch lint, format, and type errors. If it fails, run `make check-fix` to auto-fix what it can, then re-run `make check`. If changing API response shapes, also run `make check-codegen` to verify generated types are in sync. Do not commit or push until all checks pass.

## Conventions

- Python: snake_case, relative imports within packages
- TypeScript: strict mode, bundler module resolution
- Frontend types come from OpenAPI codegen — do not hand-write API types in `frontend/src/types/`
- Temporal train/val/test splits (no data leakage)
- Models saved with metadata JSON + pickle scalers
