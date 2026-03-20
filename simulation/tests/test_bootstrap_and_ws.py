from __future__ import annotations

import asyncio
import os
import unittest
from unittest.mock import patch

from fastapi.testclient import TestClient

import src.app as app_module
from src.session import SessionConfig
from src.state import session_manager


class BootstrapSessionTests(unittest.IsolatedAsyncioTestCase):
    async def asyncTearDown(self) -> None:
        bootstrap_session = app_module._bootstrap_session
        if bootstrap_session is not None:
            bootstrap_session.stop()
            if session_manager.exists(bootstrap_session.id):
                session_manager.destroy(bootstrap_session.id)
        app_module._bootstrap_session = None
        app_module._bootstrap_started_at = None
        await asyncio.sleep(0)

    async def test_interactive_bootstrap_session_uses_run_id(self):
        with patch.dict(
            os.environ,
            {
                "SESSION_MODE": "interactive",
                "RUN_ID": "run-interactive-id",
                "MISSION_SOLS": "450",
            },
            clear=False,
        ):
            await app_module._start_bootstrap_session()

        bootstrap_session = app_module._bootstrap_session
        assert bootstrap_session is not None
        self.assertEqual(bootstrap_session.id, "run-interactive-id")

    async def test_interactive_bootstrap_session_starts_paused(self):
        with patch.dict(
            os.environ,
            {
                "SESSION_MODE": "interactive",
                "RUN_ID": "run-interactive-paused",
                "MISSION_SOLS": "450",
            },
            clear=False,
        ):
            await app_module._start_bootstrap_session()

        bootstrap_session = app_module._bootstrap_session
        assert bootstrap_session is not None
        self.assertTrue(bootstrap_session.paused)
        self.assertTrue(bootstrap_session.engine.paused)


class WebSocketBootstrapRouteTests(unittest.TestCase):
    def tearDown(self) -> None:
        for session_id in ("run-existing-bootstrap",):
            if session_manager.exists(session_id):
                session_manager.destroy(session_id)

    def test_create_session_is_rejected_when_bootstrap_session_exists(self):
        session_manager.create(SessionConfig(), session_id="run-existing-bootstrap")

        with TestClient(app_module.app) as client:
            with client.websocket_connect("/ws/run-existing-bootstrap") as ws:
                ws.send_json({"type": "register", "payload": {"role": "frontend"}})
                self.assertEqual(ws.receive_json()["type"], "registered")

                ws.send_json({"type": "create_session", "payload": {"paused": True}})
                error = ws.receive_json()

        self.assertEqual(error["type"], "error")
        self.assertEqual(error["payload"]["code"], "bootstrap_session_only")
        self.assertEqual(error["payload"]["session_id"], "run-existing-bootstrap")


if __name__ == "__main__":
    unittest.main()
