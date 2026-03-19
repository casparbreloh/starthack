"""Mars Greenhouse Agent — BedrockAgentCoreApp entry point.

Supports two modes: [R5-M6, R7-M1]
  1. run_mission: Run the full 450-sol greenhouse management loop
  2. query: Interactive single-prompt query mode (for hackathon demo)
"""

from __future__ import annotations

import json
from typing import Any

from bedrock_agentcore.runtime import BedrockAgentCoreApp, RequestContext

from .config import VALID_DIFFICULTIES

logger = logging.getLogger(__name__)

app = BedrockAgentCoreApp()


@app.entrypoint
async def agent_handler(payload: dict[str, Any], context: RequestContext):
    """Handle incoming agent requests.

    Supports two modes based on payload 'action' field:
      - "run_mission": Run the full mission loop (yields start/complete/error events)
      - "query" (or no action): Answer a single question about the greenhouse

    Payload schema:
        {
            "action": "run_mission" | "query",  # optional, default "query"
            "prompt": "...",                      # for query mode
            "config": {                           # for run_mission mode
                "seed": 0,
                "difficulty": "normal",           # validated against VALID_DIFFICULTIES
                "sols": 450
            }
        }

    Yields mission_start, mission_complete/mission_error, or query_response events.
    """
    action = payload.get("action", "query")

    if action == "run_mission":
        # [C-6] Validate difficulty before starting mission
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

        # Lazy import to avoid loading ML/Strands deps at startup time
        from .agents.orchestrator import run_mission
        from .config import SIM_BASE_URL
        from .sim_client import SimClient

        client = SimClient(SIM_BASE_URL)

        try:
            # Run mission with progress streaming [MEDIUM-8]
            # We wrap run_mission in a simple loop that yields progress events
            # run_mission handles the full sol loop internally
            result = run_mission(
                client,
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
        # query mode: interactive single-prompt response for hackathon demo
        prompt = payload.get("prompt", "Give me a status report on the greenhouse.")

        from strands import Agent
        from strands.models.bedrock import BedrockModel

        from .config import AGENT_TEMPERATURE, MODEL_ID, SIM_BASE_URL
        from .prompts import ORCHESTRATOR_SYSTEM_PROMPT
        from .sim_client import SimClient
        from .tools._state import set_client
        from .tools.actions import create_action_tools
        from .tools.telemetry import create_telemetry_tools

        query_client = SimClient(SIM_BASE_URL)
        set_client(query_client)
        telemetry_tools = create_telemetry_tools(query_client)
        action_tools = create_action_tools(query_client)
        action_tools.pop("advance_simulation")  # not for query mode

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
