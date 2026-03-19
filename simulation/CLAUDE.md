# simulation/

## Purpose

Deterministic Mars greenhouse simulation engine. FastAPI service with no internal AI — pure physics/biology modeling.

## Architecture

- PCSE (WOFOST) pattern with two-phase tick cycle: `calc_rates()` then `integrate()`
- Sub-model call order: Weather -> Energy -> Climate -> Water -> Nutrients -> Crops -> Crew -> Events/Scoring

## Key Files

- `engine.py` — Central orchestrator
- `state.py` — Singleton simulation state
- `app.py` — FastAPI factory
- `catalog.py` — Crop biological rules
- `constants.py` — NASA/WHO/OSHA-sourced constants
- `enums.py` — Shared enumerations

## Models

7 sub-models in `models/`: climate, crew, crops, energy, events, nutrients, scoring, water, weather

## Routers

3 router groups:
- Telemetry — GET endpoints for reading simulation state
- Actions — POST endpoints for agent commands
- Admin — POST endpoints for sim control and scenario injection

## Domain

- 5 crop types: lettuce, potato, radish, beans, herbs
- 3 greenhouse zones: A, B, C
- Crew health model with survival consequences

## Commands

```bash
uv sync                                         # Install dependencies
uv run uvicorn main:app --reload --port 8080     # Start simulation server
```

## Conventions

- All sub-models follow `calc_rates`/`integrate` pattern
- Constants sourced from real references (NASA, WHO, OSHA) — no magic numbers in business logic
