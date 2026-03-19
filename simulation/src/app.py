"""
FastAPI application factory.

Wires together the app instance, CORS middleware, and the WebSocket router.
REST routers are kept in src/routers/ for OpenAPI schema generation only
(see scripts/export_openapi.py) — the running app is WebSocket-only.
"""

from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

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

    application.include_router(ws_router)

    return application


app = create_app()
