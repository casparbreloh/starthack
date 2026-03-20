"""
FastAPI application factory.

Wires together the app instance, CORS middleware, and the WebSocket router.
REST routers are kept in src/routers/ for OpenAPI schema generation only
(see scripts/export_openapi.py) — the running app is WebSocket-only.

When ``SESSION_MODE`` is set to ``interactive`` or ``training``, the app
auto-creates a single bootstrap session at startup. Interactive sessions start
paused for the frontend to join, while training sessions auto-run at max speed.
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
# Bootstrap session mode configuration (all from environment)
# ---------------------------------------------------------------------------
FARGATE_TIMEOUT_S = 2 * 60 * 60  # 2 hours
INTERACTIVE_DEFAULT_TICK_DELAY_MS = 1000

# Populated during startup when SESSION_MODE is active
_bootstrap_session: Session | None = None
_bootstrap_started_at: datetime | None = None


# ---------------------------------------------------------------------------
# Fargate helpers
# ---------------------------------------------------------------------------


def _get_session_mode() -> str:
    """Return the configured bootstrap session mode, if any."""
    return os.environ.get("SESSION_MODE", "").strip().lower()


def _is_bootstrap_mode() -> bool:
    """Return whether the process should auto-create a bootstrap session."""
    return _get_session_mode() in {"interactive", "training"}


async def _on_bootstrap_mission_end(session: Session) -> None:
    """Upload results to S3 and terminate the process."""
    from src.results import upload_results

    bucket = os.environ.get("RESULTS_BUCKET", "")
    run_id = os.environ.get("RUN_ID", session.id)

    logger.info(
        "Bootstrap session ended (sol=%d, phase=%s) — uploading results",
        session.engine.current_sol,
        session.engine.mission_phase.value,
    )
    await upload_results(session, bucket, run_id)

    logger.info("Bootstrap run complete — shutting down")
    sys.exit(0)


async def _bootstrap_timeout_watchdog(session: Session) -> None:
    """Force shutdown if the mission hasn't completed within the timeout."""
    await asyncio.sleep(FARGATE_TIMEOUT_S)
    if session.engine.mission_phase.value == "active":
        logger.error(
            "Bootstrap timeout (%ds) reached at sol %d — forcing shutdown",
            FARGATE_TIMEOUT_S,
            session.engine.current_sol,
        )
        # Still try to upload partial results
        await _on_bootstrap_mission_end(session)


async def _start_bootstrap_session() -> None:
    """Create and start a single bootstrap session for deployed mode."""
    global _bootstrap_session, _bootstrap_started_at  # noqa: PLW0603

    session_mode = _get_session_mode()
    seed_env = os.environ.get("SEED")
    default_tick_delay_ms = (
        0 if session_mode == "training" else INTERACTIVE_DEFAULT_TICK_DELAY_MS
    )
    config = SessionConfig(
        seed=int(seed_env) if seed_env else None,
        difficulty=os.environ.get("DIFFICULTY", "normal"),
        mission_sols=int(os.environ.get("MISSION_SOLS", "450")),
        tick_delay_ms=int(os.environ.get("TICK_DELAY_MS", str(default_tick_delay_ms))),
    )

    run_id = os.environ.get("RUN_ID")
    session_id = run_id if session_mode == "interactive" and run_id else None
    session = session_manager.create(config, session_id=session_id)
    session.run_id = os.environ.get("RUN_ID", session.id)
    session.on_mission_end = _on_bootstrap_mission_end

    if session_mode == "training":
        session.paused = False
        session.engine.paused = False
    else:
        session.paused = True
        session.engine.paused = True
    session.start()

    _bootstrap_session = session
    _bootstrap_started_at = datetime.now(UTC)

    logger.info(
        "Bootstrap session %s started (mode=%s, seed=%s, difficulty=%s, sols=%d, paused=%s)",
        session.id,
        session_mode,
        config.seed,
        config.difficulty,
        config.mission_sols,
        session.paused,
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
        _bootstrap_timeout_watchdog(session),
        name=f"bootstrap-timeout-{session.id[:8]}",
    )


# ---------------------------------------------------------------------------
# Lifespan
# ---------------------------------------------------------------------------


@asynccontextmanager
async def lifespan(application: FastAPI):
    """Manage startup/shutdown lifecycle."""
    if _is_bootstrap_mode():
        logger.info(
            "SESSION_MODE=%s detected — auto-starting bootstrap session",
            _get_session_mode(),
        )
        await _start_bootstrap_session()

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
        if _bootstrap_session is None:
            return {
                "session_id": None,
                "current_sol": None,
                "mission_phase": None,
                "started_at": None,
                "session_mode": None,
            }
        return {
            "session_id": _bootstrap_session.id,
            "current_sol": _bootstrap_session.engine.current_sol,
            "mission_phase": _bootstrap_session.engine.mission_phase.value,
            "started_at": _bootstrap_started_at.isoformat()
            if _bootstrap_started_at
            else None,
            "session_mode": _get_session_mode() or None,
        }

    application.include_router(ws_router)

    return application


app = create_app()
