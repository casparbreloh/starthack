# agent/src/agents/

## Purpose

Orchestrator and 6 specialist crisis agents for the Mars greenhouse mission. The orchestrator processes consultation snapshots from the simulation WebSocket; specialists are dispatched for crisis interrupts.

## Key Files

- `orchestrator.py` — Main agent. Processes consultation snapshots, decides actions + next_checkin sol. Integrates weather forecasts, energy projections, journal context, and AgentCore Memory.
- `triage.py` — Multi-crisis coordinator. Prioritizes and dispatches to specialists in correct order.
- `water_crisis.py` — Handles water_recycling_decline and water_shortage
- `energy_crisis.py` — Handles energy_disruption
- `pathogen_response.py` — Handles pathogen_outbreak
- `climate_emergency.py` — Handles temperature_failure and co2_imbalance
- `storm_preparation.py` — Triggered by dust_opacity > 1.0, not by crisis type
- `nutrition_planner.py` — Handles food_shortage and nutrient_depletion

## Conventions

- All specialists are plain `@tool`-decorated functions that create a Strands Agent internally
- Orchestrator receives consultation snapshots (not raw API calls) and returns actions + next_checkin
- Triage agent has `@tool`-decorated wrappers that delegate to each specialist
- Crisis tracker observes outcomes at 5/15/50-sol windows after crisis response
