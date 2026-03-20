"""
Oasis Simulation Engine — entry point.

Run with:  uv run uvicorn main:app --reload
"""

from src.app import app  # noqa: F401  (re-exported for uvicorn)
