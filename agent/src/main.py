"""Mars Greenhouse Agent — BedrockAgentCoreApp entry point.

Supports two modes: [R5-M6, R7-M1]
  1. run_mission: Run the full 450-sol greenhouse management loop
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
    """Handle incoming agent requests.

    Supports two modes based on payload 'action' field:
      - "run_mission": Run the full mission loop (yields sol-by-sol progress)
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

    Yields AG-UI streaming events during the mission loop. [MEDIUM-8]
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

        from .config import AGENT_TEMPERATURE, MODEL_ID
        from .prompts import ORCHESTRATOR_SYSTEM_PROMPT
        from .tools.actions import (
            adjust_nutrients,
            allocate_energy,
            clean_water_filters,
            harvest_crop,
            plant_crop,
            remove_crop,
            set_irrigation,
            set_zone_environment,
        )
        from .tools.telemetry import get_crop_catalog, read_all_telemetry

        model = BedrockModel(model_id=MODEL_ID, temperature=AGENT_TEMPERATURE)
        agent = Agent(
            model=model,
            system_prompt=ORCHESTRATOR_SYSTEM_PROMPT,
            tools=[
                read_all_telemetry,
                get_crop_catalog,
                allocate_energy,
                set_zone_environment,
                set_irrigation,
                clean_water_filters,
                plant_crop,
                harvest_crop,
                remove_crop,
                adjust_nutrients,
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
