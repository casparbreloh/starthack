"""
Session management for multiple concurrent simulation instances.

Each Session wraps a SimulationEngine with metadata and a concurrency lock.
The SessionManager maintains a registry of sessions and provides a default
session so bare REST calls (without a session_id) keep working.
"""

from __future__ import annotations

import asyncio
import uuid
from dataclasses import dataclass, field
from datetime import UTC, datetime

from fastapi import HTTPException

from src.connection import ConnectionManager
from src.engine import SimulationEngine


@dataclass
class SessionConfig:
    """Internal configuration for a simulation session."""

    seed: int | None = None
    difficulty: str = "normal"
    tick_delay_ms: int = 0
    starting_reserves: dict[str, float] = field(default_factory=dict)


class Session:
    """A single simulation session with its engine, config, and metadata."""

    def __init__(self, config: SessionConfig | None = None) -> None:
        self.id: str = str(uuid.uuid4())
        self.config: SessionConfig = config or SessionConfig()
        self.engine: SimulationEngine = SimulationEngine()
        self.created_at: datetime = datetime.now(UTC)
        self.lock: asyncio.Lock = asyncio.Lock()

        # WebSocket connection management
        self.connections: ConnectionManager = ConnectionManager()

        # Tick loop state
        self.next_consultation_sol: int = 0
        self.agent_response_event: asyncio.Event = asyncio.Event()
        self.pending_actions: list[dict] = []
        self.paused: bool = False
        self.next_checkin: int = 1
        self.tick_task: asyncio.Task | None = None  # type: ignore[type-arg]
        self.crisis_interrupt_pending: bool = False

    def start(self) -> None:
        """Start the self-ticking loop as an asyncio Task."""
        if self.tick_task is not None and not self.tick_task.done():
            return

        from src.tick_loop import run_session_loop

        self.tick_task = asyncio.get_event_loop().create_task(
            run_session_loop(self), name=f"tick-{self.id[:8]}"
        )

    def stop(self) -> None:
        """Cancel the tick loop task."""
        if self.tick_task is not None and not self.tick_task.done():
            self.tick_task.cancel()


class SessionManager:
    """Registry of named simulation sessions with a default fallback."""

    def __init__(self) -> None:
        self._sessions: dict[str, Session] = {}
        self._default_session: Session = Session()
        self._sessions[self._default_session.id] = self._default_session

    def create(self, config: SessionConfig | None = None) -> Session:
        """Create a new session and register it."""
        session = Session(config)
        self._sessions[session.id] = session
        return session

    def get(self, session_id: str) -> Session:
        """Look up a session by id; raises HTTP 404 if not found."""
        session = self._sessions.get(session_id)
        if session is None:
            raise HTTPException(404, f"Session '{session_id}' not found")
        return session

    def get_or_default(self, session_id: str | None) -> Session:
        """Return the requested session, or the default if session_id is None."""
        if session_id is None:
            return self._default_session
        return self.get(session_id)

    def destroy(self, session_id: str) -> None:
        """Remove a session from the registry."""
        if session_id not in self._sessions:
            raise HTTPException(404, f"Session '{session_id}' not found")
        if session_id == self._default_session.id:
            raise HTTPException(400, "Cannot destroy the default session")
        del self._sessions[session_id]

    def list_sessions(self) -> list[Session]:
        """Return all active sessions."""
        return list(self._sessions.values())
