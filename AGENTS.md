## Project

Mars Greenhouse Agent System — Syngenta START Hack challenge. Autonomous AI agents manage a Martian greenhouse simulation for a 450-day crew mission (4 astronauts).

## Stack

- **Agent**: Python 3.13+, deployed on AWS AgentCore
- **Simulation**: Python 3.13+, FastAPI, uvicorn
- **Frontend**: React 19, TypeScript 5.9, Vite 8, Tailwind CSS 4
- **ML**: PyTorch 2.10, scikit-learn 1.8, pandas 3.0
- **Package managers**: `uv` (Python), `pnpm` (frontend)

## Structure

- `agent/` — AI agent (Python, uv)
- `simulation/` — greenhouse simulation API (Python, FastAPI, uv)
- `frontend/` — dashboard UI (React, TypeScript, Vite, pnpm)
- `ml/` — Mars weather prediction ML pipeline (PyTorch LSTM)
- `docs/` — project references (see below)

## Docs

- `docs/ARCHITECTURE.md` — infrastructure and deployment
- `docs/CHALLENGE.MD` — Syngenta START Hack challenge brief
- `docs/mcp-data/` — domain knowledge: Mars environment, crop profiles, nutrition, plant stress, greenhouse scenarios

## Commands

- `make install` — install all dependencies
- `make dev` — run all services in parallel
- `make dev-agent` — run agent only
- `make dev-simulation` — run simulation only
- `make dev-frontend` — run frontend only
- `make check` — lint, format-check, and type-check all projects
- `make check-fix` — auto-fix lint and format issues in all projects
- `cd ml && uv run python -m mars_weather.train` — train ML models
- `cd ml && uv run python -m mars_weather.evaluate` — evaluate on test set
- `cd ml && uv run python -m mars_weather.predict` — run predictions

## Where to Look

- Weather prediction logic → `ml/mars_weather/`
- Challenge requirements → `docs/CHALLENGE.MD`
- Crop/nutrition/stress data → `docs/mcp-data/`
- Trained model artifacts → `ml/models/`

## Conventions

- Python: snake_case, relative imports within packages
- TypeScript: strict mode, bundler module resolution
- Temporal train/val/test splits (no data leakage)
- Models saved with metadata JSON + pickle scalers
