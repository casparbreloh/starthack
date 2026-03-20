"""Export the FastAPI OpenAPI schema as JSON to stdout.

Creates a dedicated app with REST routers mounted for schema extraction.
The production app (src.app) is WebSocket-only — these routers exist
solely to keep Pydantic response models → OpenAPI → TypeScript codegen
working for end-to-end type safety.
"""

import json
import sys

from fastapi import FastAPI

from src.routers import actions_router, admin_router, telemetry_router

schema_app = FastAPI(title="Oasis Simulation Engine", version="1.0.0")
schema_app.include_router(telemetry_router)
schema_app.include_router(actions_router)
schema_app.include_router(admin_router)

schema = schema_app.openapi()
json.dump(schema, sys.stdout, indent=2)
print()
