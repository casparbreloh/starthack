## Project

Mars Greenhouse Agent System — Syngenta START Hack challenge. Autonomous AI agents manage a Martian greenhouse simulation for a 450-day crew mission (4 astronauts).

## Stack

- **Agent**: Python 3.13+, deployed on AWS AgentCore
- **Simulation**: Python 3.13+, FastAPI, uvicorn
- **Frontend**: React 19, TypeScript 5.9, Vite 8, Tailwind CSS 4
- **ML**: PyTorch 2.10, scikit-learn 1.8, pandas 3.0
- **Package managers**: `uv` (Python), `pnpm` (frontend)

## Structure

- `agent/` — AI agent system: orchestrator + 6 specialist crisis agents, REST and WebSocket modes (Python, uv)
- `simulation/` — greenhouse simulation API with self-ticking WebSocket engine (Python, FastAPI, uv)
- `frontend/` — dashboard UI with real-time WebSocket state updates (React, TypeScript, Vite, pnpm)
- `ml/` — Mars weather prediction ML pipeline + HTTP sidecar service (PyTorch LSTM, FastAPI)
- `docs/` — project references (see below)

## Docs

- `docs/ARCHITECTURE.md` — infrastructure and deployment
- `docs/CHALLENGE.md` — Syngenta START Hack challenge brief
- `docs/mcp-data/` — domain knowledge: Mars environment, crop profiles, nutrition, plant stress, greenhouse scenarios

## Commands

- `make install` — install all dependencies
- `make dev` — run all services in parallel
- `make dev-agent` — run agent only (REST mode via AgentCore)
- `make dev-simulation` — run simulation only (starts tick loop on WebSocket session creation)
- `make dev-frontend` — run frontend only
- `make dev-ml` — run ML sidecar service only (port 8090)
- `make check` — lint, format-check, and type-check all projects
- `make check-fix` — auto-fix lint and format issues in all projects
- `make codegen` — regenerate TypeScript types from the simulation OpenAPI schema
- `make check-codegen` — regenerate and verify types are up-to-date (used in CI)
- `cd ml && uv run python -m mars_weather.train` — train ML models
- `cd ml && uv run python -m mars_weather.evaluate` — evaluate on test set
- `cd ml && uv run python -m mars_weather.predict` — run predictions
- `cd agent && uv run mars-agent` — run agent mission (REST mode)
- `cd agent && uv run mars-agent --ws` — run agent mission (WebSocket mode)

## Where to Look

- Weather prediction logic → `ml/mars_weather/`
- ML sidecar service → `ml/serve.py`
- Agent weather client → `agent/src/weather_integration.py`
- Agent orchestrator → `agent/src/agents/orchestrator.py`
- Specialist crisis agents → `agent/src/agents/`
- Agent tool factories → `agent/src/tools/`
- Agent WebSocket client → `agent/src/ws_client.py`
- Simulation sub-models → `simulation/src/models/`
- Simulation session manager → `simulation/src/session.py`
- Simulation WebSocket router → `simulation/src/ws.py`
- Simulation tick loop → `simulation/src/tick_loop.py`
- Simulation interrupt detector → `simulation/src/interrupts.py`
- Simulation snapshot builder → `simulation/src/snapshots.py`
- Simulation connection manager → `simulation/src/connection.py`
- Frontend WebSocket hook → `frontend/src/hooks/useWebSocket.ts`
- Challenge requirements → `docs/CHALLENGE.md`
- Crop/nutrition/stress data → `docs/mcp-data/`
- Trained model artifacts → `ml/models/`
- API response models (Pydantic) → `simulation/src/models/responses.py`
- Generated TypeScript types → `frontend/src/contracts/simulation.d.ts`
- Frontend type re-exports → `frontend/src/types/simulation.ts`
- OpenAPI schema export script → `simulation/scripts/export_openapi.py`

## OpenAPI Contracts

Frontend TypeScript types are auto-generated from the simulation's OpenAPI schema:

1. Pydantic response models in `simulation/src/models/responses.py` define the data contract
2. REST routers in `simulation/src/routers/` reference these models (kept for schema generation only — not mounted in the running app)
3. `simulation/scripts/export_openapi.py` creates a schema-only FastAPI app with routers to extract OpenAPI JSON
4. `openapi-typescript` generates `frontend/src/contracts/simulation.d.ts` from the schema
5. `frontend/src/types/simulation.ts` re-exports generated types under stable names

When changing a data shape: update the Pydantic model in `responses.py`, run `make codegen`, and the frontend types update automatically. CI runs `make check-codegen` to enforce types stay in sync.

## Pre-Commit Checks

Before committing and pushing, always run `make check` to catch lint, format, and type errors. If it fails, run `make check-fix` to auto-fix what it can, then re-run `make check`. If changing API response shapes, also run `make check-codegen` to verify generated types are in sync. Do not commit or push until all checks pass.

## Conventions

- Python: snake_case, relative imports within packages
- TypeScript: strict mode, bundler module resolution
- Frontend types come from OpenAPI codegen — do not hand-write API types in `frontend/src/types/`
- Temporal train/val/test splits (no data leakage)
- Models saved with metadata JSON + pickle scalers
