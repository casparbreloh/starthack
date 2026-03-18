# Agents

## Repo Structure

- `backend/` — FastAPI server with agent orchestration and simulation loop
  - `main.py` — app entry point
  - `agent/` — individual agent implementations
  - `simulation/` — greenhouse simulation state and time progression
  - `api/` — route handlers
- `frontend/` — React/TypeScript UI (Vite)
  - `src/App.tsx` — root component
- `docs/` — challenge brief and reference data (Mars environment, crop profiles, nutrition, scenarios)

## Agent Modules

Agents live in `backend/agent/`. Each agent is a separate module:

- **planner** — crop scheduling and growing area allocation
- **environment** — greenhouse climate control (temp, humidity, CO₂, lighting)
- **resource** — water, energy, and consumable tracking
- **diagnostics** — plant stress and system failure detection
- **nutrition** — dietary output evaluation against crew requirements

Agents query the Syngenta knowledge base via the AWS AgentCore gateway.
