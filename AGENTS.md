# Agents

## Repo Structure

- `agent/` — AI agent deployed on AWS AgentCore
  - `src/` — agent modules
  - `pyproject.toml`
- `simulation/` — FastAPI greenhouse simulation service (the agent acts upon this)
  - `src/` — simulation state, time progression, API endpoints
  - `main.py` — app entry point
  - `pyproject.toml`
- `frontend/` — React/TypeScript UI (Vite)
  - `src/App.tsx` — root component
- `docs/` — challenge brief and reference data (Mars environment, crop profiles, nutrition, scenarios)

## Agent Modules

Agents live in `agent/src/`. Each agent is a separate module:

- **planner** — crop scheduling and growing area allocation
- **environment** — greenhouse climate control (temp, humidity, CO₂, lighting)
- **resource** — water, energy, and consumable tracking
- **diagnostics** — plant stress and system failure detection
- **nutrition** — dietary output evaluation against crew requirements

Agents query the Syngenta knowledge base via the AWS AgentCore gateway. The frontend can subscribe to agent actions in real-time via the AG-UI protocol that AgentCore exposes.
