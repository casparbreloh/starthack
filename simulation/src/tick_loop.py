"""
Self-ticking simulation loop.

Runs as an asyncio Task, advancing the engine one sol per iteration.
Handles agent consultation pauses, tick pacing, and interrupt detection.
"""

from __future__ import annotations

import asyncio
import logging
from typing import TYPE_CHECKING, Any

from src.enums import CropType, MissionPhase, Severity
from src.interrupts import detect_interrupts
from src.snapshots import build_consultation_snapshot, build_state_snapshot

if TYPE_CHECKING:
    from src.session import Session

logger = logging.getLogger(__name__)

AGENT_TIMEOUT_S = 300


async def run_session_loop(session: Session) -> None:
    """
    Main tick loop for a session. Advances one sol per iteration.

    Runs until the mission ends or the task is cancelled.
    """
    engine = session.engine
    logger.info("Tick loop started for session %s", session.id)

    try:
        while engine.mission_phase == MissionPhase.ACTIVE:
            # Respect pause
            while session.paused:
                await asyncio.sleep(0.1)

            # Tick pacing — always yield to let the event loop process
            # incoming WS messages (crisis injection, pause, etc.)
            delay = (
                session.config.tick_delay_ms / 1000.0
                if session.config.tick_delay_ms > 0
                else 0
            )
            await asyncio.sleep(delay)

            # Capture pre-tick state for interrupt detection
            pre_crisis_ids = {c.id for c in engine.events.active_crises()}
            pre_ready_crops = {
                crop_id
                for crop_id, batch in engine.crops.batches.items()
                if batch.is_ready
            }
            previous_phase = engine.mission_phase

            # Advance one sol under lock; also snapshot crisis_interrupt_pending
            async with session.lock:
                tick_events = engine.advance(1)
                crisis_pending = session.crisis_interrupt_pending
                session.crisis_interrupt_pending = False

            # Detect interrupts (read-only, no lock needed)
            interrupts = detect_interrupts(
                engine,
                pre_crisis_ids,
                pre_ready_crops,
                tick_events,
                previous_phase,
                last_interrupt_sols=session.last_interrupt_sols,
            )

            # Build snapshot and broadcast (read-only, no lock needed)
            snapshot = build_state_snapshot(engine)
            snapshot["events"] = tick_events
            snapshot["interrupts"] = interrupts
            await session.connections.broadcast_tick(snapshot)

            # Agent consultation check: scheduled (every N sols) OR interrupt
            should_consult = session.connections.agent is not None and (
                engine.current_sol >= session.next_consultation_sol
                or interrupts
                or crisis_pending
            )

            if should_consult:
                reason = "interrupt" if interrupts or crisis_pending else "scheduled"
                await _consult_agent(session, snapshot, interrupts, reason)

            # Check if mission ended
            if engine.mission_phase != MissionPhase.ACTIVE:
                await session.connections.broadcast(
                    {
                        "type": "mission_end",
                        "payload": {
                            "mission_phase": engine.mission_phase.value,
                            "final_sol": engine.current_sol,
                            "snapshot": snapshot,
                        },
                    }
                )
                break

    except asyncio.CancelledError:
        logger.info("Tick loop cancelled for session %s", session.id)
    except Exception:
        logger.exception("Tick loop error for session %s", session.id)
        try:
            await session.connections.broadcast(
                {"type": "error", "payload": {"message": "Simulation crashed"}}
            )
        except Exception:
            pass


async def _consult_agent(
    session: Session,
    snapshot: dict[str, Any],
    interrupts: list[dict[str, Any]],
    reason: str = "scheduled",
) -> None:
    """Pause the tick loop and wait for agent actions."""
    session.agent_response_event.clear()

    # Build enriched consultation snapshot (includes weather history,
    # forecast, crop catalog, events log, sensors — everything the
    # agent needs without REST calls)
    consultation_snapshot = build_consultation_snapshot(session.engine)
    # Carry over events and interrupts from the tick
    consultation_snapshot["events"] = snapshot.get("events", [])
    consultation_snapshot["interrupts"] = interrupts

    await session.connections.send_to_agent(
        {
            "type": "consultation",
            "session_id": session.id,
            "payload": {
                "sol": session.engine.current_sol,
                "reason": reason,
                "interrupts": interrupts,
                "snapshot": consultation_snapshot,
            },
        }
    )

    try:
        await asyncio.wait_for(
            session.agent_response_event.wait(), timeout=AGENT_TIMEOUT_S
        )
    except TimeoutError:
        logger.warning(
            "Agent consultation timed out after %ds for session %s",
            AGENT_TIMEOUT_S,
            session.id,
        )
        # Advance so the loop doesn't immediately re-consult on the next tick
        session.next_consultation_sol = (
            session.engine.current_sol + session.next_checkin
        )
        return

    # Execute pending actions under lock
    if session.pending_actions:
        async with session.lock:
            await execute_actions(session.engine, session.pending_actions)
        session.pending_actions.clear()

    # Update next consultation sol
    session.next_consultation_sol = session.engine.current_sol + session.next_checkin


async def execute_actions(
    engine: Any, actions: list[dict[str, Any]]
) -> list[dict[str, Any]]:
    """
    Execute a list of agent actions against the engine.

    Each action is {"endpoint": "crops/plant", "body": {...}}.
    Returns a list of result dicts.
    """
    results: list[dict[str, Any]] = []

    for action in actions:
        endpoint = action.get("endpoint", "")
        body = action.get("body", {})

        try:
            result = _dispatch_action(engine, endpoint, body)
            results.append({"endpoint": endpoint, "status": "ok", "result": result})
        except Exception as exc:
            logger.warning("Action '%s' failed: %s", endpoint, exc)
            results.append({"endpoint": endpoint, "status": "error", "error": str(exc)})

    return results


def _dispatch_action(
    engine: Any, endpoint: str, body: dict[str, Any]
) -> dict[str, Any]:
    """Map an action endpoint to an engine method call."""
    if endpoint == "energy/allocate":
        engine.energy.allocate(body)
        return {"allocation": engine.energy.state.allocation}

    if endpoint == "greenhouse/set_environment":
        zone_id = body.get("zone_id")
        zone_body = {k: v for k, v in body.items() if k != "zone_id"}
        zone = engine.climate.set_zone(zone_id=zone_id, **zone_body)
        return {"zone_id": zone.zone_id, "target_temp_c": zone.target_temp_c}

    if endpoint == "water/set_irrigation":
        zone_id = body["zone_id"]
        liters = body["irrigation_liters_per_sol"]
        engine.water.set_irrigation(zone_id, liters)
        return {"zone_id": zone_id, "irrigation_liters_per_sol": liters}

    if endpoint == "water/maintenance":
        action_name = body.get("action", "clean_filters")
        result = engine.water.maintenance(action_name)
        if result.get("result") == "success":
            engine.scoring.record_preventive_action()
        return result

    if endpoint == "water/mine_ice":
        result = engine.water.mine_ice(
            current_sol=engine.current_sol,
            battery_wh=engine.energy.state.battery_level_wh,
        )
        if result["result"] == "success":
            # Deduct energy from battery
            engine.energy.state.battery_level_wh = max(
                0.0, engine.energy.state.battery_level_wh - result["energy_cost_wh"]
            )
            # Record preventive action
            engine.scoring.record_preventive_action()
            # Log success event
            engine.events.log(
                engine.current_sol,
                "action",
                "water",
                f"Ice mining: extracted {result['liters_extracted']} L (drill health: {result['new_drill_health_pct']}%)",
                Severity.INFO,
            )
        else:
            # Log failure event
            engine.events.log(
                engine.current_sol,
                "action",
                "water",
                f"Ice mining failed: {result.get('reason', 'unknown')}",
                Severity.WARNING,
            )
        return result

    if endpoint == "crops/plant":
        crop_type = CropType(body["type"])
        batch = engine.crops.plant(
            current_sol=engine.current_sol,
            crop_type=crop_type,
            zone_id=body["zone_id"],
            area_m2=body["area_m2"],
            batch_name=body.get("batch_name"),
        )
        return {"crop_id": batch.crop_id, "planted_sol": batch.planted_sol}

    if endpoint == "crops/harvest":
        crop_id = body["crop_id"]
        result = engine.crops.harvest(crop_id)
        engine.crew.add_harvest(
            kcal=result["calories_kcal"],
            protein_g=result["protein_g"],
            has_micronutrients=result["provides_micronutrients"],
        )
        engine.scoring.record_harvest(result["yield_kg"])
        return result

    if endpoint == "crops/remove":
        crop_id = body["crop_id"]
        reason = body.get("reason", "")
        result = engine.crops.remove(crop_id, reason)
        engine.scoring.record_crop_removed(result["waste_kg"])
        return result

    if endpoint == "nutrients/adjust":
        zone_id = body["zone_id"]
        engine.nutrients.adjust(
            zone_id=zone_id,
            target_ph=body.get("target_ph"),
            nitrogen_boost=body.get("nitrogen_boost", False),
            potassium_boost=body.get("potassium_boost", False),
            flush_solution=body.get("flush_solution", False),
        )
        if body.get("flush_solution"):
            engine.water.state.reservoir_liters = max(
                0.0, engine.water.state.reservoir_liters - 10.0
            )
        return {"zone_id": zone_id, "status": "adjusted"}

    raise ValueError(f"Unknown action endpoint: {endpoint}")
