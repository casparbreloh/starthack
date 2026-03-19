"""
HTTP bridge for invoking the agent via POST /invocations.

The simulation calls this when a session is created/reset to invite
the agent to connect back via WebSocket and manage the greenhouse.
Failures are non-fatal — the simulation continues without an agent.
"""

from __future__ import annotations

import logging

import httpx

logger = logging.getLogger(__name__)


async def invoke_agent(agent_url: str, session_id: str, ws_url: str) -> None:
    """POST to the agent's /invocations endpoint to start a join_mission.

    Reads the SSE stream in the background, logging agent events.
    On connection failure, logs a warning and returns (non-fatal).
    """
    payload = {
        "action": "join_mission",
        "config": {
            "session_id": session_id,
            "ws_url": ws_url,
        },
    }

    try:
        async with httpx.AsyncClient(
            timeout=httpx.Timeout(connect=5.0, read=300.0, write=5.0, pool=5.0)
        ) as client:
            async with client.stream(
                "POST", f"{agent_url}/invocations", json=payload
            ) as resp:
                resp.raise_for_status()
                async for line in resp.aiter_lines():
                    if not line.strip():
                        continue
                    logger.info("Agent event: %s", line.rstrip())
    except httpx.ConnectError:
        logger.warning(
            "Could not reach agent at %s — simulation continues without agent",
            agent_url,
        )
    except Exception:
        logger.exception("Agent invocation failed for session %s", session_id)
