"""
Interrupt detection for the tick loop.

After each sol, checks for state changes that should trigger an agent
consultation: new crises, crop deaths, harvest readiness, critical
resource levels, and mission phase transitions.
"""

from __future__ import annotations

from typing import Any

from src.constants import CRISIS_BATTERY_PCT, CRISIS_WATER_RESERVOIR_L
from src.engine import SimulationEngine
from src.enums import MissionPhase


def detect_interrupts(
    engine: SimulationEngine,
    pre_crisis_ids: set[str],
    pre_ready_crops: set[str],
    tick_events: list[dict[str, Any]],
    previous_phase: MissionPhase,
    last_interrupt_sols: dict[str, int] | None = None,
) -> list[dict[str, Any]]:
    """
    Detect interrupts that occurred during the last tick.

    Args:
        engine: The simulation engine after the tick.
        pre_crisis_ids: Set of crisis IDs that were active before the tick.
        pre_ready_crops: Set of crop IDs that were harvest-ready before the tick.
        tick_events: Events returned by engine.advance() for this tick.
        previous_phase: Mission phase before the tick.
        last_interrupt_sols: Mutable dict tracking the last sol each interrupt
            type fired. Used to deduplicate persistent-condition interrupts
            (water_critical, battery_critical) so they fire at most once per sol.

    Returns:
        List of interrupt dicts, each with 'type' and 'detail' keys.
    """
    if last_interrupt_sols is None:
        last_interrupt_sols = {}
    interrupts: list[dict[str, Any]] = []

    # New crises
    current_crisis_ids = {c.id for c in engine.events.active_crises()}
    new_crisis_ids = current_crisis_ids - pre_crisis_ids
    for crisis in engine.events.active_crises():
        if crisis.id in new_crisis_ids:
            interrupts.append(
                {
                    "type": "new_crisis",
                    "detail": {
                        "crisis_id": crisis.id,
                        "crisis_type": crisis.type.value,
                        "severity": crisis.severity.value,
                        "message": crisis.message,
                    },
                }
            )

    # Crop deaths (check tick_events for crop death alerts)
    for event in tick_events:
        if (
            event.get("type") == "alert"
            and event.get("category") == "crop"
            and "died" in event.get("message", "").lower()
        ):
            interrupts.append(
                {
                    "type": "crop_death",
                    "detail": {"message": event["message"], "sol": event["sol"]},
                }
            )

    # Harvest ready (new crops that became ready this tick)
    current_ready_crops = {
        crop_id for crop_id, batch in engine.crops.batches.items() if batch.is_ready
    }
    newly_ready = current_ready_crops - pre_ready_crops
    for crop_id in newly_ready:
        batch = engine.crops.batches[crop_id]
        interrupts.append(
            {
                "type": "harvest_ready",
                "detail": {
                    "crop_id": crop_id,
                    "crop_type": batch.crop_type.value,
                    "zone_id": batch.zone_id,
                },
            }
        )

    # Water critical (deduplicate: fire at most once per sol)
    if engine.water.state.reservoir_liters < CRISIS_WATER_RESERVOIR_L:
        if last_interrupt_sols.get("water_critical", -1) < engine.current_sol:
            last_interrupt_sols["water_critical"] = engine.current_sol
            interrupts.append(
                {
                    "type": "water_critical",
                    "detail": {
                        "reservoir_liters": engine.water.state.reservoir_liters,
                    },
                }
            )

    # Battery critical (deduplicate: fire at most once per sol)
    if engine.energy.battery_pct < CRISIS_BATTERY_PCT:
        if last_interrupt_sols.get("battery_critical", -1) < engine.current_sol:
            last_interrupt_sols["battery_critical"] = engine.current_sol
            interrupts.append(
                {
                    "type": "battery_critical",
                    "detail": {
                        "battery_pct": engine.energy.battery_pct,
                    },
                }
            )

    # Mission phase change
    if engine.mission_phase != previous_phase:
        interrupts.append(
            {
                "type": "mission_phase_change",
                "detail": {
                    "previous": previous_phase.value,
                    "current": engine.mission_phase.value,
                },
            }
        )

    return interrupts
