"""
WebSocket connection manager.

Tracks the single agent connection and multiple frontend connections per session.
Provides helpers for broadcasting tick data and sending targeted messages.
"""

from __future__ import annotations

import logging
from typing import Any

from starlette.websockets import WebSocket, WebSocketState

logger = logging.getLogger(__name__)


class ConnectionManager:
    """Manages WebSocket connections for a single simulation session."""

    def __init__(self) -> None:
        self.agent: WebSocket | None = None
        self.frontends: list[WebSocket] = []

    def register(self, ws: WebSocket, role: str) -> None:
        """Register a WebSocket connection by role."""
        if role == "agent":
            if self.agent is not None:
                logger.warning("Replacing existing agent connection")
            self.agent = ws
        elif role == "frontend":
            self.frontends.append(ws)
        else:
            logger.warning("Unknown role '%s', treating as frontend", role)
            self.frontends.append(ws)

    def disconnect(self, ws: WebSocket) -> None:
        """Remove a WebSocket from tracked connections."""
        if ws is self.agent:
            self.agent = None
            logger.info("Agent disconnected")
        elif ws in self.frontends:
            self.frontends.remove(ws)
            logger.info("Frontend disconnected (%d remaining)", len(self.frontends))

    async def broadcast_tick(self, data: dict[str, Any]) -> None:
        """Send tick data to all connected clients (agent + frontends)."""
        message = {"type": "tick", "payload": data}
        targets: list[WebSocket] = list(self.frontends)
        if self.agent is not None:
            targets.append(self.agent)
        for ws in targets:
            await self._safe_send(ws, message)

    async def send_to_agent(self, data: dict[str, Any]) -> None:
        """Send a message to the agent connection, if connected."""
        if self.agent is None:
            logger.debug("No agent connected, skipping send_to_agent")
            return
        await self._safe_send(self.agent, data)

    async def broadcast(self, data: dict[str, Any]) -> None:
        """Send a message to all connected clients."""
        targets: list[WebSocket] = list(self.frontends)
        if self.agent is not None:
            targets.append(self.agent)
        for ws in targets:
            await self._safe_send(ws, data)

    async def _safe_send(self, ws: WebSocket, data: dict[str, Any]) -> None:
        """Send JSON to a WebSocket, handling disconnection gracefully."""
        try:
            if ws.client_state == WebSocketState.CONNECTED:
                await ws.send_json(data)
        except Exception:
            logger.warning("Failed to send to WebSocket, removing connection")
            self.disconnect(ws)
