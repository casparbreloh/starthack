"""
FastAPI application factory.

Wires together the app instance, CORS middleware, and the WebSocket router.
REST routers are kept in src/routers/ for OpenAPI schema generation only
(see scripts/export_openapi.py) — the running app is WebSocket-only.

When ``FARGATE_MODE=1`` is set, the app auto-creates a single session at
startup, runs the mission at max speed, uploads results to S3, then exits.
"""

from __future__ import annotations

import asyncio
import logging
import os
import sys
from contextlib import asynccontextmanager
from datetime import UTC, datetime

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from src.session import Session, SessionConfig
from src.state import session_manager
from src.ws import router as ws_router

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Fargate mode configuration (all from environment)
# ---------------------------------------------------------------------------
FARGATE_MODE = os.environ.get("FARGATE_MODE") == "1"
FARGATE_TIMEOUT_S = 2 * 60 * 60  # 2 hours

# Populated during startup when FARGATE_MODE is active
_fargate_session: Session | None = None
_fargate_started_at: datetime | None = None


# ---------------------------------------------------------------------------
# Fargate helpers
# ---------------------------------------------------------------------------


async def _on_fargate_mission_end(session: Session) -> None:
    """Upload results to S3 and terminate the process."""
    from src.results import upload_results

    bucket = os.environ.get("RESULTS_BUCKET", "")
    run_id = os.environ.get("RUN_ID", session.id)

    logger.info(
        "Fargate mission ended (sol=%d, phase=%s) — uploading results",
        session.engine.current_sol,
        session.engine.mission_phase.value,
    )
    await upload_results(session, bucket, run_id)

    logger.info("Fargate run complete — shutting down")
    sys.exit(0)


async def _fargate_timeout_watchdog(session: Session) -> None:
    """Force shutdown if the mission hasn't completed within the timeout."""
    await asyncio.sleep(FARGATE_TIMEOUT_S)
    if session.engine.mission_phase.value == "active":
        logger.error(
            "Fargate timeout (%ds) reached at sol %d — forcing shutdown",
            FARGATE_TIMEOUT_S,
            session.engine.current_sol,
        )
        # Still try to upload partial results
        await _on_fargate_mission_end(session)


async def _start_fargate_session() -> None:
    """Create and start a single auto-running session for Fargate mode."""
    global _fargate_session, _fargate_started_at  # noqa: PLW0603

    seed_env = os.environ.get("SEED")
    config = SessionConfig(
        seed=int(seed_env) if seed_env else None,
        difficulty=os.environ.get("DIFFICULTY", "normal"),
        mission_sols=int(os.environ.get("MISSION_SOLS", "450")),
        tick_delay_ms=int(os.environ.get("TICK_DELAY_MS", "0")),
    )

    session = session_manager.create(config)
    session.run_id = os.environ.get("RUN_ID", session.id)
    session.on_mission_end = _on_fargate_mission_end

    # Start unpaused (immediate auto-run)
    session.paused = False
    session.engine.paused = False
    session.start()

    _fargate_session = session
    _fargate_started_at = datetime.now(UTC)

    logger.info(
        "Fargate session %s started (seed=%s, difficulty=%s, sols=%d)",
        session.id,
        config.seed,
        config.difficulty,
        config.mission_sols,
    )

    # Auto-invoke agent if configured (AGENT_RUNTIME_ARN or AGENT_URL)
    from src.agent_bridge import get_own_ws_url, invoke_agent

    try:
        ws_url = await get_own_ws_url()
    except BaseException:
        logger.exception("Failed to resolve own WS URL — running without agent")
        ws_url = None

    if ws_url:
        asyncio.create_task(
            invoke_agent(session.id, ws_url),
            name=f"invoke-agent-{session.id[:8]}",
        )

    # Start timeout watchdog
    asyncio.create_task(
        _fargate_timeout_watchdog(session),
        name=f"fargate-timeout-{session.id[:8]}",
    )


# ---------------------------------------------------------------------------
# Lifespan
# ---------------------------------------------------------------------------


@asynccontextmanager
async def lifespan(application: FastAPI):
    """Manage startup/shutdown lifecycle."""
    if FARGATE_MODE:
        logger.info("FARGATE_MODE=1 detected — auto-starting session")
        await _start_fargate_session()

    yield

    # Shutdown: stop all running tick loops
    for session in session_manager.list_sessions():
        session.stop()


# ---------------------------------------------------------------------------
# App factory
# ---------------------------------------------------------------------------


def create_app() -> FastAPI:
    application = FastAPI(
        title="Oasis Simulation Engine",
        version="1.0.0",
        lifespan=lifespan,
    )

    application.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    @application.get("/health")
    async def health() -> dict:
        return {"status": "ok"}

    @application.get("/sessions")
    async def list_sessions() -> list:
        """Stub for local dev — the real endpoint lives on the orchestrator Lambda."""
        return []

    @application.get("/status")
    async def status() -> dict:
        if _fargate_session is None:
            return {
                "session_id": None,
                "current_sol": None,
                "mission_phase": None,
                "started_at": None,
            }
        return {
            "session_id": _fargate_session.id,
            "current_sol": _fargate_session.engine.current_sol,
            "mission_phase": _fargate_session.engine.mission_phase.value,
            "started_at": _fargate_started_at.isoformat()
            if _fargate_started_at
            else None,
        }

    application.include_router(ws_router)

    return application


app = create_app()
