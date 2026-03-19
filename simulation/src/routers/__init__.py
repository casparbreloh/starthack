from src.routers.actions import router as actions_router
from src.routers.admin import router as admin_router
from src.routers.telemetry import router as telemetry_router

__all__ = ["telemetry_router", "actions_router", "admin_router"]
