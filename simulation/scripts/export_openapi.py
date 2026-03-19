"""Export the FastAPI OpenAPI schema as JSON to stdout."""

import json
import sys

from src.app import app

schema = app.openapi()
json.dump(schema, sys.stdout, indent=2)
print()
