"""WebSocket client for connecting the agent to the simulation's /ws endpoint.

Provides an async interface for the agent to:
- Register as an agent
- Create a simulation session
- Receive consultation requests (blocking queue)
- Send actions with next_checkin scheduling
"""

from __future__ import annotations

import asyncio
import json
import logging
from typing import Any

import websockets
from websockets import ClientConnection

logger = logging.getLogger(__name__)

# Sentinel value pushed to the queue when the mission ends
_MISSION_ENDED = object()


class SimWebSocketClient:
    """Async WebSocket client for the Mars greenhouse simulation.

    Connects to the simulation's /ws endpoint and participates in the
    consultation protocol: receive consultation requests, send actions.

    Usage::

        async with SimWebSocketClient() as ws_client:
            await ws_client.connect("ws://localhost:8080/ws")
            session_id = await ws_client.create_session({"seed": 0, "difficulty": "normal"})
            while True:
                consultation = await ws_client.wait_for_consultation()
                if consultation is None:
                    break  # mission ended
                actions, next_checkin, reasoning = decide(consultation)
                await ws_client.send_actions(actions, next_checkin, reasoning)
    """

    def __init__(self) -> None:
        self._ws: ClientConnection | None = None
        self._session_id: str | None = None
        self._consultation_queue: asyncio.Queue[dict | object] = asyncio.Queue()
        self._session_created_future: asyncio.Future[dict] | None = None
        self._listen_task: asyncio.Task[None] | None = None
        self._mission_ended = False
        self._mission_end_payload: dict[str, Any] | None = None

    async def __aenter__(self) -> SimWebSocketClient:
        return self

    async def __aexit__(self, *args: object) -> None:
        await self.close()

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    async def connect(self, url: str) -> None:
        """Connect to the simulation WebSocket and register as agent.

        Args:
            url: WebSocket URL, e.g. ``ws://localhost:8080/ws``
        """
        self._ws = await websockets.connect(url, ping_interval=30, ping_timeout=120)
        logger.info("WebSocket connected to %s", url)

        # Register as agent
        await self._send({"type": "register", "payload": {"role": "agent"}})

        # Wait for registration ack
        raw = await self._ws.recv()
        msg = json.loads(raw)
        if msg.get("type") != "registered":
            raise RuntimeError(f"Expected 'registered' response, got: {msg}")
        logger.info("Registered as agent")

        # Start background listener
        self._listen_task = asyncio.create_task(self._listen_loop())

    async def create_session(self, config: dict[str, Any]) -> str:
        """Create a new simulation session via WebSocket.

        Args:
            config: Session config dict with keys like seed, difficulty,
                    tick_delay_ms, starting_reserves.

        Returns:
            The session_id string assigned by the server.
        """
        loop = asyncio.get_running_loop()
        self._session_created_future = loop.create_future()

        await self._send(
            {
                "type": "create_session",
                "session_id": None,
                "payload": config,
            }
        )

        result = await self._session_created_future
        session_id: str = str(result["session_id"])
        self._session_id = session_id
        self._session_created_future = None
        logger.info("Session created: %s", self._session_id)
        return session_id

    async def wait_for_consultation(self) -> dict | None:
        """Block until a consultation request arrives from the server.

        Returns:
            Consultation payload dict with keys: sol, interrupts, snapshot.
            Returns ``None`` if the mission has ended.
        """
        item = await self._consultation_queue.get()
        if item is _MISSION_ENDED:
            return None
        return item  # type: ignore[return-value]

    async def send_actions(
        self,
        actions: list[dict[str, Any]],
        next_checkin: int,
        log_decision: dict[str, Any] | None = None,
    ) -> None:
        """Send agent actions back to the simulation.

        Args:
            actions: List of action dicts, each with ``endpoint`` and ``body``.
            next_checkin: Number of sols until the next consultation (1-10).
            log_decision: Optional decision log dict with reasoning and
                          risk_assessment.
        """
        payload: dict[str, Any] = {
            "actions": actions,
            "next_checkin": next_checkin,
        }
        if log_decision is not None:
            payload["log_decision"] = log_decision

        await self._send(
            {
                "type": "agent_actions",
                "session_id": self._session_id,
                "payload": payload,
            }
        )
        logger.debug("Sent %d actions, next_checkin=%d", len(actions), next_checkin)

    async def close(self) -> None:
        """Close the WebSocket connection and cancel the listener."""
        if self._listen_task is not None and not self._listen_task.done():
            self._listen_task.cancel()
            try:
                await self._listen_task
            except asyncio.CancelledError:
                pass
            self._listen_task = None

        if self._ws is not None:
            await self._ws.close()
            self._ws = None
            logger.info("WebSocket connection closed")

    @property
    def session_id(self) -> str | None:
        """The current session ID, or None if no session has been created."""
        return self._session_id

    @property
    def mission_ended(self) -> bool:
        """Whether the server has signalled mission end."""
        return self._mission_ended

    @property
    def mission_end_payload(self) -> dict[str, Any] | None:
        """The payload from the most recent ``mission_end`` message."""
        return self._mission_end_payload

    # ------------------------------------------------------------------
    # Internal
    # ------------------------------------------------------------------

    async def _send(self, msg: dict[str, Any]) -> None:
        """Send a JSON message over the WebSocket."""
        if self._ws is None:
            raise RuntimeError("WebSocket not connected")
        await self._ws.send(json.dumps(msg))

    async def _listen_loop(self) -> None:
        """Background task that receives messages and dispatches them.

        Message types handled:
        - ``session_created`` -> resolves the create_session future
        - ``consultation`` -> enqueues for wait_for_consultation()
        - ``mission_end`` -> sets ended flag, enqueues sentinel
        - ``tick`` -> ignored (agent does not need per-sol ticks)
        - ``error`` -> logged as warning
        - anything else -> logged as debug
        """
        if self._ws is None:
            return

        try:
            async for raw in self._ws:
                msg = json.loads(raw)
                msg_type = msg.get("type", "")

                if msg_type == "session_created":
                    if self._session_created_future is not None:
                        self._session_created_future.set_result(msg.get("payload", {}))

                elif msg_type == "consultation":
                    await self._consultation_queue.put(msg.get("payload", {}))

                elif msg_type == "mission_end":
                    self._mission_ended = True
                    self._mission_end_payload = msg.get("payload", {})
                    await self._consultation_queue.put(_MISSION_ENDED)
                    logger.info("Mission ended (received mission_end)")

                elif msg_type == "tick":
                    pass  # Agent ignores per-sol ticks

                elif msg_type == "error":
                    error_payload = msg.get("payload", {})
                    if (
                        self._session_created_future is not None
                        and not self._session_created_future.done()
                    ):
                        message = error_payload.get("message", "Unknown server error")
                        self._session_created_future.set_exception(
                            RuntimeError(message)
                        )
                    logger.warning(
                        "Server error: %s", error_payload.get("message", msg)
                    )

                else:
                    logger.debug("Unhandled WS message type: %s", msg_type)

        except websockets.exceptions.ConnectionClosed:
            logger.info("WebSocket connection closed by server")
            self._mission_ended = True
            await self._consultation_queue.put(_MISSION_ENDED)
        except asyncio.CancelledError:
            raise
        except Exception:
            logger.exception("Error in WebSocket listen loop")
            self._mission_ended = True
            await self._consultation_queue.put(_MISSION_ENDED)
