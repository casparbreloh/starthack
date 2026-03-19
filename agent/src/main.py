"""Mars Greenhouse Agent — BedrockAgentCoreApp entry point.

Supports two modes:
  1. run_mission: Run the full 450-sol greenhouse management loop (WebSocket)
  2. query: Interactive single-prompt query mode (for hackathon demo)
"""

from __future__ import annotations

import json
import logging
from typing import Any

from bedrock_agentcore.runtime import BedrockAgentCoreApp, RequestContext

from .config import VALID_DIFFICULTIES

logger = logging.getLogger(__name__)

app = BedrockAgentCoreApp()


@app.entrypoint
async def agent_handler(payload: dict[str, Any], context: RequestContext):
    """Handle incoming agent requests."""
    action = payload.get("action", "query")

    if action == "run_mission":
        config = payload.get("config", {})
        difficulty = config.get("difficulty", "normal")
        if difficulty not in VALID_DIFFICULTIES:
            yield {
                "data": json.dumps(
                    {
                        "error": f"Invalid difficulty '{difficulty}'. Must be one of: {VALID_DIFFICULTIES}"
                    }
                )
            }
            return

        seed = config.get("seed", 0)
        mission_sols = config.get("sols", 450)

        yield {
            "data": json.dumps(
                {
                    "event": "mission_start",
                    "seed": seed,
                    "difficulty": difficulty,
                    "sols": mission_sols,
                }
            )
        }

        from .agents.orchestrator import run_mission
        from .config import SIM_WS_URL

        try:
            result = await run_mission(
                ws_url=SIM_WS_URL,
                seed=seed,
                difficulty=difficulty,
                mission_sols=mission_sols,
            )

            yield {
                "data": json.dumps(
                    {
                        "event": "mission_complete",
                        "run_id": result["run_id"],
                        "final_score": result["final_score"],
                        "mission_phase": result["mission_phase"],
                        "total_crises": result["total_crises"],
                    }
                )
            }

        except Exception as exc:
            logger.error("Mission failed: %s", exc)
            yield {
                "data": json.dumps(
                    {
                        "event": "mission_error",
                        "error": str(exc),
                    }
                )
            }

    else:
        # query mode: interactive single-prompt response
        prompt = payload.get("prompt", "Give me a status report on the greenhouse.")

        from strands import Agent
        from strands.models.bedrock import BedrockModel

        from .config import AGENT_TEMPERATURE, MODEL_ID
        from .prompts import ORCHESTRATOR_SYSTEM_PROMPT
        from .tools.actions import create_action_tools
        from .tools.telemetry import create_telemetry_tools

        telemetry_tools = create_telemetry_tools({})
        action_tools = create_action_tools()

        model = BedrockModel(model_id=MODEL_ID, temperature=AGENT_TEMPERATURE)
        agent = Agent(
            model=model,
            system_prompt=ORCHESTRATOR_SYSTEM_PROMPT,
            tools=[
                telemetry_tools["read_all_telemetry"],
                telemetry_tools["get_crop_catalog"],
                *action_tools.values(),
            ],
        )

        response = agent(prompt)
        yield {
            "data": json.dumps(
                {
                    "event": "query_response",
                    "result": str(response.message),
                },
                default=str,
            )
        }


if __name__ == "__main__":
    app.run()
