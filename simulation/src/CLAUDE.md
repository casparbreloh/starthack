# simulation/src/

## Purpose

Core simulation source code. Engine, WebSocket protocol, session management, and all sub-models.

## Key Files

- `engine.py` — SimulationEngine class: `advance()` → `_tick()` runs one sol through all sub-models
- `ws.py` — WebSocket router: consultation protocol (register → create_session → tick → consult → actions)
- `tick_loop.py` — Async self-ticking loop: advances engine, detects interrupts, pauses for agent consultation
- `session.py` — SessionManager registry + Session dataclass (engine + config + lock + connections)
- `connection.py` — ConnectionManager: tracks 1 agent + N frontend WebSocket connections per session
- `snapshots.py` — Builds telemetry dicts from engine state for WebSocket broadcast
- `interrupts.py` — Post-tick interrupt detection (new crises, crop deaths, critical levels, harvest readiness)
- `app.py` — FastAPI factory with lifespan, CORS, router mounting
- `state.py` — Global SessionManager singleton
- `catalog.py` — Crop biological parameters (growth days, yields, water demand, nutritional content)
- `constants.py` — All simulation constants with real-world references
- `enums.py` — MissionPhase, CropType, Difficulty, crisis types

## Subdirectories

- `models/` — Physics/biology sub-models (weather, energy, climate, water, nutrients, crops, crew, events, scoring)
- `routers/` — REST API routers (kept for OpenAPI codegen, not mounted at runtime)

## Consultation Protocol Flow

1. Tick loop advances engine one sol
2. `detect_interrupts()` checks for agent-relevant state changes
3. If interrupts found: pause, build consultation snapshot, send to agent via WebSocket
4. Agent responds with actions + next_checkin sol
5. Engine applies actions, resumes ticking until next interrupt or next_checkin sol
