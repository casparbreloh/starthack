"""
FastAPI application factory.

Wires together the app instance, CORS middleware, and all routers.
Exposed as the module-level `app` so uvicorn can target `src.app:app`
or (via main.py re-export) `main:app`.
"""

from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from src.routers import actions_router, admin_router, telemetry_router
from src.state import session_manager
from src.ws import router as ws_router


@asynccontextmanager
async def lifespan(application: FastAPI):
    """Manage startup/shutdown lifecycle."""
    yield
    # Shutdown: stop all running tick loops
    for session in session_manager.list_sessions():
        session.stop()


def create_app() -> FastAPI:
    application = FastAPI(
        title="Mars Greenhouse Simulation Engine",
        description=(
            "Deterministic physics/biology state machine for the Syngenta START Hack "
            "'Agriculture on Mars' challenge. No internal AI — exposes the greenhouse "
            "environment to an external AI agent via REST."
        ),
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

    application.include_router(telemetry_router)
    application.include_router(actions_router)
    application.include_router(admin_router)
    application.include_router(ws_router)

    return application


app = create_app()
