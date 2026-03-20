from __future__ import annotations

import ast
import unittest
from pathlib import Path


STACK_PATH = Path(__file__).resolve().parents[1] / "stacks" / "oasis_stack.py"


def _literal_str(node: ast.AST) -> str | None:
    if isinstance(node, ast.Constant) and isinstance(node.value, str):
        return node.value
    return None


class OasisStackSourceTestCase(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.module = ast.parse(STACK_PATH.read_text())

    def test_invoke_agent_runtime_policy_includes_runtime_and_endpoint(self):
        invoke_resources: list[str] = []

        for node in ast.walk(self.module):
            if not isinstance(node, ast.Call):
                continue
            if not isinstance(node.func, ast.Attribute):
                continue
            if node.func.attr != "PolicyStatement":
                continue

            actions_kw = next(
                (kw for kw in node.keywords if kw.arg == "actions"),
                None,
            )
            resources_kw = next(
                (kw for kw in node.keywords if kw.arg == "resources"),
                None,
            )
            if (
                actions_kw is None
                or resources_kw is None
                or not isinstance(actions_kw.value, ast.List)
                or not isinstance(resources_kw.value, ast.List)
            ):
                continue

            actions = {_literal_str(item) for item in actions_kw.value.elts}
            if "bedrock-agentcore:InvokeAgentRuntime" not in actions:
                continue

            for resource in resources_kw.value.elts:
                if isinstance(resource, ast.Attribute):
                    invoke_resources.append(resource.attr)

        self.assertIn("attr_agent_runtime_arn", invoke_resources)
        self.assertIn("attr_agent_runtime_endpoint_arn", invoke_resources)

    def test_orchestrator_permissions_include_describe_target_health(self):
        statements: list[set[str]] = []

        for node in ast.walk(self.module):
            if not isinstance(node, ast.Call):
                continue
            if not isinstance(node.func, ast.Attribute):
                continue
            if node.func.attr != "PolicyStatement":
                continue

            actions_kw = next(
                (kw for kw in node.keywords if kw.arg == "actions"),
                None,
            )
            if actions_kw is None or not isinstance(actions_kw.value, ast.List):
                continue

            actions = {
                action
                for action in (_literal_str(item) for item in actions_kw.value.elts)
                if action is not None
            }
            if actions:
                statements.append(actions)

        self.assertTrue(
            any(
                "elasticloadbalancing:DescribeTargetHealth" in actions
                for actions in statements
            )
        )


if __name__ == "__main__":
    unittest.main()
