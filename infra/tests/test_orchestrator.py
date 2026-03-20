from __future__ import annotations

import importlib.util
import json
import os
import sys
import unittest
from pathlib import Path
from types import ModuleType
from unittest.mock import MagicMock, patch


MODULE_PATH = (
    Path(__file__).resolve().parents[1] / "lambda" / "orchestrator" / "index.py"
)


class OrchestratorModuleTestCase(unittest.TestCase):
    def load_module(self):
        clients: dict[str, MagicMock] = {}

        def client_factory(name: str) -> MagicMock:
            client = MagicMock(name=f"{name}_client")
            if name == "elbv2":
                client.exceptions = type(
                    "Elbv2Exceptions",
                    (),
                    {
                        "TargetGroupNotFoundException": type(
                            "TargetGroupNotFoundException",
                            (Exception,),
                            {},
                        )
                    },
                )()
            clients[name] = client
            return client

        env = {
            "CLUSTER_NAME": "oasis",
            "TASK_DEFINITION_ARN": "task-def-arn",
            "SUBNET_IDS": "subnet-1,subnet-2",
            "SECURITY_GROUP_ID": "sg-123",
            "RESULTS_BUCKET": "results-bucket",
            "AGENT_RUNTIME_ARN": "agent-runtime-arn",
            "ALB_LISTENER_ARN": "listener-arn",
            "VPC_ID": "vpc-123",
            "WS_BASE_URL": "wss://example.cloudfront.net",
        }

        fake_boto3 = ModuleType("boto3")
        fake_boto3.client = client_factory

        with patch.dict(os.environ, env, clear=False), patch.dict(
            sys.modules,
            {"boto3": fake_boto3},
        ):
            spec = importlib.util.spec_from_file_location(
                "test_orchestrator_index",
                MODULE_PATH,
            )
            module = importlib.util.module_from_spec(spec)
            assert spec is not None and spec.loader is not None
            spec.loader.exec_module(module)

        return module, clients

    def make_running_task(self, run_id: str = "run-123") -> dict:
        return {
            "taskArn": "task-arn",
            "lastStatus": "RUNNING",
            "startedBy": run_id,
            "attachments": [
                {
                    "type": "ElasticNetworkInterface",
                    "details": [{"name": "networkInterfaceId", "value": "eni-123"}],
                }
            ],
        }

    def test_start_session_sets_interactive_overrides(self):
        module, clients = self.load_module()
        clients["ecs"].run_task.return_value = {"tasks": [{"taskArn": "task-arn"}]}

        response = module._start_session({"body": json.dumps({"mode": "interactive"})})
        body = json.loads(response["body"])
        env_list = clients["ecs"].run_task.call_args.kwargs["overrides"][
            "containerOverrides"
        ][0]["environment"]
        env_map = {entry["name"]: entry["value"] for entry in env_list}

        self.assertEqual(env_map["SESSION_MODE"], "interactive")
        self.assertEqual(env_map["TICK_DELAY_MS"], "1000")
        self.assertEqual(env_map["SIM_WS_URL"], f"wss://example.cloudfront.net/ws/{body['run_id']}")
        self.assertFalse(body["ws_ready"])

    def test_start_session_sets_training_overrides(self):
        module, clients = self.load_module()
        clients["ecs"].run_task.return_value = {"tasks": [{"taskArn": "task-arn"}]}

        response = module._start_session({"body": json.dumps({"mode": "training"})})
        body = json.loads(response["body"])
        env_list = clients["ecs"].run_task.call_args.kwargs["overrides"][
            "containerOverrides"
        ][0]["environment"]
        env_map = {entry["name"]: entry["value"] for entry in env_list}

        self.assertEqual(env_map["SESSION_MODE"], "training")
        self.assertEqual(env_map["TICK_DELAY_MS"], "0")
        self.assertEqual(env_map["SIM_WS_URL"], f"wss://example.cloudfront.net/ws/{body['run_id']}")
        self.assertFalse(body["ws_ready"])

    def test_running_task_with_initial_target_health_stays_starting(self):
        module, _ = self.load_module()
        task = self.make_running_task()

        with patch.object(
            module,
            "_resolve_ips",
            return_value=("10.0.0.10", "52.0.0.10"),
        ), patch.object(
            module,
            "_ensure_alb_routing",
            return_value="tg-arn",
        ) as ensure_alb_routing, patch.object(
            module,
            "_describe_target_health",
            return_value=("initial", "Elb.InitialHealthChecking"),
        ):
            info = module._extract_task_info(task)

        ensure_alb_routing.assert_called_once_with("run-123", "10.0.0.10")
        self.assertEqual(info["status"], "starting")
        self.assertFalse(info["ws_ready"])
        self.assertIsNone(info["ws_url"])
        self.assertEqual(info["target_health_state"], "initial")
        self.assertEqual(info["ready_reason"], "Elb.InitialHealthChecking")

    def test_running_task_with_healthy_target_exposes_ws_url(self):
        module, _ = self.load_module()
        task = self.make_running_task(run_id="run-456")

        with patch.object(
            module,
            "_resolve_ips",
            return_value=("10.0.0.11", "52.0.0.11"),
        ), patch.object(
            module,
            "_ensure_alb_routing",
            return_value="tg-arn",
        ), patch.object(
            module,
            "_describe_target_health",
            return_value=("healthy", None),
        ):
            info = module._extract_task_info(task)

        self.assertEqual(info["status"], "running")
        self.assertTrue(info["ws_ready"])
        self.assertEqual(info["ws_url"], "wss://example.cloudfront.net/ws/run-456")
        self.assertEqual(info["target_health_state"], "healthy")

    def test_stopped_task_cleans_up_without_recreating_routing(self):
        module, _ = self.load_module()
        task = {
            **self.make_running_task(),
            "lastStatus": "STOPPED",
            "stopCode": "EssentialContainerExited",
        }

        with patch.object(
            module,
            "_resolve_ips",
            return_value=("10.0.0.10", "52.0.0.10"),
        ), patch.object(module, "_ensure_alb_routing") as ensure_alb_routing, patch.object(
            module,
            "_cleanup_alb_routing",
        ) as cleanup_alb_routing:
            info = module._extract_task_info(task)

        ensure_alb_routing.assert_not_called()
        cleanup_alb_routing.assert_called_once_with("run-123")
        self.assertEqual(info["status"], "completed")
        self.assertFalse(info["ws_ready"])
        self.assertIsNone(info["ws_url"])


if __name__ == "__main__":
    unittest.main()
