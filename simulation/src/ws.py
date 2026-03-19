"""
WebSocket router for real-time simulation control.

Provides a single /ws endpoint that handles:
- register: identify as agent or frontend
- create_session: create and start a new simulation session
- agent_actions: submit actions during agent consultation
- inject_crisis: trigger a scenario injection
- set_tick_delay: change tick pacing
- pause / resume: control the tick loop
"""

from __future__ import annotations

import logging
from typing import Any

from fastapi import APIRouter
from starlette.websockets import WebSocket, WebSocketDisconnect

from src.engine import AgentDecision
from src.session import SessionConfig
from src.state import session_manager

logger = logging.getLogger(__name__)

router = APIRouter()

# Map scenario names to engine methods
_SCENARIO_MAP: dict[str, str] = {
    "water_leak": "scenario_water_leak",
    "hvac_failure": "scenario_hvac_failure",
    "pathogen": "scenario_pathogen",
    "dust_storm": "scenario_dust_storm",
    "energy_disruption": "scenario_energy_disruption",
}


@router.websocket("/ws")
async def websocket_endpoint(ws: WebSocket) -> None:
    """Main WebSocket endpoint with message dispatch."""
    await ws.accept()

    role: str | None = None
    session_id: str | None = None

    try:
        # Wait for registration message
        raw = await ws.receive_json()
        if raw.get("type") != "register":
            await ws.send_json(
                {
                    "type": "error",
                    "payload": {"message": "First message must be register"},
                }
            )
            await ws.close()
            return

        role = raw.get("payload", {}).get("role", "frontend")
        await ws.send_json({"type": "registered", "payload": {"role": role}})
        logger.info("WebSocket registered as %s", role)

        # Message dispatch loop
        while True:
            msg = await ws.receive_json()
            msg_type = msg.get("type", "")
            msg_session_id = msg.get("session_id", session_id)
            payload = msg.get("payload", {})

            if msg_type == "create_session":
                session_id = await _handle_create_session(ws, role, payload)

            elif msg_type == "join_session":
                session_id = await _handle_join_session(ws, role, payload)

            elif msg_type == "agent_actions":
                await _handle_agent_actions(msg_session_id, payload)

            elif msg_type == "inject_crisis":
                await _handle_inject_crisis(ws, msg_session_id, payload)

            elif msg_type == "set_tick_delay":
                await _handle_set_tick_delay(ws, msg_session_id, payload)

            elif msg_type == "pause":
                await _handle_pause(ws, msg_session_id)

            elif msg_type == "resume":
                await _handle_resume(ws, msg_session_id)

            else:
                await ws.send_json(
                    {
                        "type": "error",
                        "payload": {"message": f"Unknown message type: {msg_type}"},
                    }
                )

    except WebSocketDisconnect:
        logger.info("WebSocket disconnected (role=%s)", role)
    except Exception:
        logger.exception("WebSocket error")
    finally:
        # Clean up connection from session
        if session_id:
            try:
                session = session_manager.get(session_id)
                session.connections.disconnect(ws)
            except Exception:
                pass


async def _handle_create_session(
    ws: WebSocket, role: str | None, payload: dict[str, Any]
) -> str:
    """Create a session, register the WS, start the tick loop, return session_id."""
    config = SessionConfig(
        seed=payload.get("seed"),
        difficulty=payload.get("difficulty", "normal"),
        tick_delay_ms=payload.get("tick_delay_ms", 0),
        mission_sols=payload.get("mission_sols", payload.get("sols", 450)),
        starting_reserves=payload.get("starting_reserves", {}),
    )
    session = session_manager.create(config)
    session.connections.register(ws, role or "frontend")
    session.start()

    await ws.send_json(
        {
            "type": "session_created",
            "session_id": session.id,
            "payload": {
                "session_id": session.id,
                "config": {
                    "seed": config.seed,
                    "difficulty": config.difficulty,
                    "tick_delay_ms": config.tick_delay_ms,
                    "mission_sols": config.mission_sols,
                },
            },
        }
    )
    logger.info("Session %s created and started via WS", session.id)
    return session.id


async def _handle_join_session(
    ws: WebSocket, role: str | None, payload: dict[str, Any]
) -> str:
    """Re-register a WebSocket with an existing session (e.g. after reconnect)."""
    target_id = payload.get("session_id", "")
    session = session_manager.get(target_id)
    session.connections.register(ws, role or "frontend")

    await ws.send_json(
        {
            "type": "session_joined",
            "session_id": session.id,
            "payload": {"session_id": session.id},
        }
    )
    logger.info("WebSocket re-joined session %s as %s", session.id, role)
    return session.id


async def _handle_agent_actions(
    session_id: str | None, payload: dict[str, Any]
) -> None:
    """Store pending actions, log decision, and signal the tick loop."""
    if session_id is None:
        return
    session = session_manager.get(session_id)
    session.pending_actions = payload.get("actions", [])
    session.next_checkin = payload.get("next_checkin", 1)

    # Record agent decision telemetry if provided
    log_decision = payload.get("log_decision")
    if log_decision:
        decision = AgentDecision(
            sol=session.engine.current_sol,
            decisions=session.pending_actions,
            risk_assessment=log_decision.get("risk_assessment", "nominal"),
        )
        session.engine.log_agent_decision(decision)

    session.agent_response_event.set()


async def _handle_inject_crisis(
    ws: WebSocket, session_id: str | None, payload: dict[str, Any]
) -> None:
    """Inject a crisis scenario into the session."""
    if session_id is None:
        await ws.send_json(
            {"type": "error", "payload": {"message": "No session_id provided"}}
        )
        return

    session = session_manager.get(session_id)
    scenario = payload.get("scenario", "")
    method_name = _SCENARIO_MAP.get(scenario)

    if method_name is None:
        await ws.send_json(
            {
                "type": "error",
                "payload": {
                    "message": f"Unknown scenario: {scenario}",
                    "available": list(_SCENARIO_MAP.keys()),
                },
            }
        )
        return

    engine = session.engine
    method = getattr(engine, method_name)

    # Some scenarios need extra args — mutate engine under lock
    async with session.lock:
        if scenario == "pathogen":
            crop_id = payload.get("crop_id")
            if not crop_id:
                await ws.send_json(
                    {
                        "type": "error",
                        "payload": {"message": "pathogen requires crop_id"},
                    }
                )
                return
            method(crop_id)
        elif scenario == "dust_storm":
            duration = payload.get("duration_sols", 10)
            method(duration)
        else:
            method()

        # Trigger agent consultation on next tick
        session.next_consultation_sol = engine.current_sol
        session.crisis_interrupt_pending = True

    await ws.send_json(
        {
            "type": "crisis_injected",
            "session_id": session_id,
            "payload": {"scenario": scenario, "sol": engine.current_sol},
        }
    )


async def _handle_set_tick_delay(
    ws: WebSocket, session_id: str | None, payload: dict[str, Any]
) -> None:
    """Update the tick delay for a session."""
    if session_id is None:
        await ws.send_json(
            {"type": "error", "payload": {"message": "No session_id provided"}}
        )
        return

    session = session_manager.get(session_id)
    tick_delay_ms = payload.get("tick_delay_ms", 0)
    session.config.tick_delay_ms = tick_delay_ms

    await ws.send_json(
        {
            "type": "tick_delay_set",
            "session_id": session_id,
            "payload": {"tick_delay_ms": tick_delay_ms},
        }
    )


async def _handle_pause(ws: WebSocket, session_id: str | None) -> None:
    """Pause the tick loop."""
    if session_id is None:
        await ws.send_json(
            {"type": "error", "payload": {"message": "No session_id provided"}}
        )
        return

    session = session_manager.get(session_id)
    session.paused = True
    session.engine.paused = True
    await ws.send_json({"type": "paused", "session_id": session_id, "payload": {}})


async def _handle_resume(ws: WebSocket, session_id: str | None) -> None:
    """Resume the tick loop."""
    if session_id is None:
        await ws.send_json(
            {"type": "error", "payload": {"message": "No session_id provided"}}
        )
        return

    session = session_manager.get(session_id)
    session.paused = False
    session.engine.paused = False
    await ws.send_json({"type": "resumed", "session_id": session_id, "payload": {}})
