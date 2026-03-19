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
