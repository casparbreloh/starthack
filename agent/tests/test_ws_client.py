"""Unit tests for the simulation WebSocket client."""

from __future__ import annotations

import asyncio
import json

from src.ws_client import SimWebSocketClient


class _FakeWebSocket:
    def __init__(self, messages: list[dict]) -> None:
        self._messages = [json.dumps(message) for message in messages]

    def __aiter__(self):
        return self

    async def __anext__(self) -> str:
        if not self._messages:
            raise StopAsyncIteration
        return self._messages.pop(0)


def test_listen_loop_captures_terminal_payload():
    """mission_end messages should preserve the final snapshot and phase."""

    async def _run() -> tuple[bool, dict | None, dict | None]:
        client = SimWebSocketClient()
        client._ws = _FakeWebSocket(  # type: ignore[assignment]
            [
                {
                    "type": "mission_end",
                    "payload": {
                        "mission_phase": "failed",
                        "final_sol": 12,
                        "snapshot": {"score_current": {"scores": {"overall_score": 1.5}}},
                    },
                }
            ]
        )

        await client._listen_loop()
        consultation = await client.wait_for_consultation()
        return client.mission_ended, client.mission_end_payload, consultation

    mission_ended, payload, consultation = asyncio.run(_run())

    assert mission_ended is True
    assert consultation is None
    assert payload is not None
    assert payload["mission_phase"] == "failed"
    assert payload["snapshot"]["score_current"]["scores"]["overall_score"] == 1.5
