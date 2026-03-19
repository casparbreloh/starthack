"""Shared mutable state for tool client binding.

This module holds a reference to the active SimClient instance so that
tool factory functions and specialist agents can all use the same client.
Set via set_client() at mission startup; access via get_client().
"""

from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from ..sim_client import SimClient

_client: SimClient | None = None


def set_client(client: SimClient) -> None:
    """Set the shared SimClient instance for all tools."""
    global _client
    _client = client


def get_client() -> SimClient:
    """Get the shared SimClient instance. Raises if not set."""
    if _client is None:
        raise RuntimeError(
            "SimClient not initialized. Call set_client() before using tools."
        )
    return _client
