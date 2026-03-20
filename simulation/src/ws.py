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

import asyncio
import logging
import os
from typing import Any

from fastapi import APIRouter
from pydantic import BaseModel, Field, ValidationError
from starlette.websockets import WebSocket, WebSocketDisconnect

from src.agent_bridge import get_own_ws_url, invoke_agent
from src.constants import MISSION_DURATION_SOLS
from src.engine import AgentDecision
from src.session import SessionConfig
from src.snapshots import build_state_snapshot
from src.state import session_manager

logger = logging.getLogger(__name__)

# Agent invocation is handled inside invoke_agent() which reads
# AGENT_RUNTIME_ARN / AGENT_URL from environment directly.
_AGENT_CONFIGURED = bool(
    os.environ.get("AGENT_RUNTIME_ARN") or os.environ.get("AGENT_URL")
)

router = APIRouter()

# Map scenario names to engine methods
_SCENARIO_MAP: dict[str, str] = {
    "water_leak": "scenario_water_leak",
    "hvac_failure": "scenario_hvac_failure",
    "pathogen": "scenario_pathogen",
    "dust_storm": "scenario_dust_storm",
    "energy_disruption": "scenario_energy_disruption",
}


class _CreateSessionPayload(BaseModel):
    seed: int | None = None
    difficulty: str = "normal"
    tick_delay_ms: int = Field(default=0, ge=0)
    mission_sols: int = Field(
        default=MISSION_DURATION_SOLS, ge=1, le=MISSION_DURATION_SOLS
    )
    starting_reserves: dict[str, float] = Field(default_factory=dict)
    paused: bool = True
    autonomous_events_enabled: bool = True


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

            try:
                if msg_type == "create_session":
                    new_session_id = await _handle_create_session(ws, role, payload)
                    if new_session_id is not None:
                        session_id = new_session_id

                elif msg_type == "join_session":
                    session_id = await _handle_join_session(ws, role, payload)

                elif msg_type == "reset_session":
                    new_session_id = await _handle_reset_session(
                        ws, role, msg_session_id, payload
                    )
                    if new_session_id is not None:
                        session_id = new_session_id

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
                raise
            except Exception:
                logger.exception("Error handling message type '%s'", msg_type)
                try:
                    await ws.send_json(
                        {
                            "type": "error",
                            "payload": {
                                "message": f"Internal error handling {msg_type}"
                            },
                        }
                    )
                except Exception:
                    pass

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
) -> str | None:
    """Create a session, register the WS, start the tick loop, return session_id."""
    normalized_payload = dict(payload)
    if "mission_sols" not in normalized_payload and "sols" in normalized_payload:
        normalized_payload["mission_sols"] = normalized_payload["sols"]

    try:
        req = _CreateSessionPayload(**normalized_payload)
    except ValidationError as exc:
        await ws.send_json(
            {
                "type": "error",
                "payload": {
                    "message": "Invalid create_session payload",
                    "errors": exc.errors(),
                },
            }
        )
        return None

    config = SessionConfig(
        seed=req.seed,
        difficulty=req.difficulty,
        tick_delay_ms=req.tick_delay_ms,
        mission_sols=req.mission_sols,
        starting_reserves=req.starting_reserves,
        autonomous_events_enabled=req.autonomous_events_enabled,
    )
    session = session_manager.create(config)
    session.engine.autonomous_events_enabled = config.autonomous_events_enabled
    session.connections.register(ws, role or "frontend")

    # Start paused if requested (default) so the frontend can show initial state
    if req.paused:
        session.paused = True
        session.engine.paused = True

    session.start()

    await ws.send_json(
        {
            "type": "session_created",
            "session_id": session.id,
            "payload": {
                "session_id": session.id,
                "paused": session.paused,
                "config": {
                    "seed": config.seed,
                    "difficulty": config.difficulty,
                    "tick_delay_ms": config.tick_delay_ms,
                    "mission_sols": config.mission_sols,
                    "autonomous_events_enabled": config.autonomous_events_enabled,
                },
            },
        }
    )

    # Send initial state snapshot so the UI has data even while paused
    snapshot = build_state_snapshot(session.engine)
    await ws.send_json({"type": "tick", "payload": snapshot})

    logger.info("Session %s created (paused=%s) via WS", session.id, session.paused)

    # Auto-invoke agent if configured (AGENT_RUNTIME_ARN or AGENT_URL)
    if _AGENT_CONFIGURED:
        ws_url = await get_own_ws_url()
        asyncio.create_task(
            invoke_agent(session.id, ws_url),
            name=f"invoke-agent-{session.id[:8]}",
        )

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

    # Send current state so reconnects get immediate data
    snapshot = build_state_snapshot(session.engine)
    await ws.send_json({"type": "tick", "payload": snapshot})

    # When agent joins, trigger immediate consultation on next tick
    if role == "agent":
        session.next_consultation_sol = session.engine.current_sol

    logger.info("WebSocket re-joined session %s as %s", session.id, role)
    return session.id


async def _handle_reset_session(
    ws: WebSocket,
    role: str | None,
    old_session_id: str | None,
    payload: dict[str, Any],
) -> str | None:
    """Destroy the current session and create a fresh one (paused by default)."""
    if old_session_id:
        try:
            session_manager.destroy(old_session_id)
        except Exception:
            pass  # session may already be gone

    return await _handle_create_session(ws, role, payload)


async def _handle_agent_actions(
    session_id: str | None, payload: dict[str, Any]
) -> None:
    """Store pending actions, log decision, and signal the tick loop."""
    if session_id is None:
        return
    session = session_manager.get(session_id)
    session.pending_actions = payload.get("actions", [])
    raw_next_checkin = payload.get("next_checkin", 1)
    try:
        next_checkin = int(raw_next_checkin)
    except (TypeError, ValueError):
        logger.warning(
            "Invalid next_checkin value %r in agent_actions payload; defaulting to 1",
            raw_next_checkin,
        )
        next_checkin = 1
    session.next_checkin = max(1, min(50, next_checkin))

    # Record agent decision telemetry if provided
    log_decision = payload.get("log_decision")
    if log_decision:
        decision = AgentDecision(
            sol=session.engine.current_sol,
            decisions=session.pending_actions,
            risk_assessment=log_decision.get("risk_assessment", "nominal"),
            reasoning=log_decision.get("reasoning", ""),
            summary=log_decision.get("summary", ""),
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
