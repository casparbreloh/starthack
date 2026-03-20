# simulation/

## Purpose

Deterministic Mars greenhouse simulation engine. FastAPI service with self-ticking WebSocket engine — pure physics/biology modeling, no internal AI.

## Architecture

- PCSE (WOFOST) pattern with two-phase tick cycle: `calc_rates()` then `integrate()`
- Sub-model call order: Weather → Energy → Climate → Water → Nutrients → Crops → Crew → Events → Scoring
- WebSocket-driven: simulation auto-ticks, pauses on interrupts for agent consultation
- Session-based: multiple concurrent simulation instances via SessionManager

## Key Files

- `src/engine.py` — Central orchestrator, `_tick()` runs one sol
- `src/ws.py` — WebSocket router (`/ws`): register, create_session, agent_actions, inject_crisis, pause/resume
- `src/tick_loop.py` — Self-ticking async loop with agent consultation pauses and interrupt detection
- `src/session.py` — Session management (SessionManager + Session dataclass)
- `src/connection.py` — WebSocket connection manager (1 agent + N frontends per session)
- `src/snapshots.py` — State snapshot builder (full telemetry dict broadcast on each tick)
- `src/interrupts.py` — Interrupt detection (new crises, crop deaths, critical resources, harvest readiness)
- `src/state.py` — Global SessionManager singleton
- `src/app.py` — FastAPI factory
- `src/catalog.py` — Crop biological rules
- `src/constants.py` — NASA/WHO/OSHA-sourced constants
- `src/enums.py` — Shared enumerations

## Models

9 sub-models in `models/`: climate, crew, crops, energy, events, nutrients, scoring, water, weather

## Routers

- `ws.py` — WebSocket protocol (primary interface for agent + frontend)
- `routers/telemetry.py` — GET endpoints (kept for OpenAPI schema generation)
- `routers/actions.py` — POST endpoints (kept for OpenAPI schema generation)
- `routers/admin.py` — POST endpoints for sim control and scenario injection

## Domain

- 5 crop types: lettuce, potato, radish, beans, herbs
- 3 greenhouse zones: A, B, C
- Crew health model with survival consequences

## Commands

```bash
uv sync                                         # Install dependencies
uv run uvicorn src.app:create_app --factory --reload --port 8080  # Start sim server
```

## Conventions

- All sub-models follow `calc_rates`/`integrate` pattern
- Constants sourced from real references (NASA, WHO, OSHA) — no magic numbers
- REST routers kept for OpenAPI codegen but not mounted in the running app — WebSocket is the runtime interface
- Snapshots mirror the telemetry router response shapes for frontend compatibility
