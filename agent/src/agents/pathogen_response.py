"""Pathogen Response specialist agent for the Mars greenhouse.

Handles the pathogen_outbreak crisis type. [CRITICAL-3]
"""

from __future__ import annotations

from strands import Agent, tool
from strands.models.bedrock import BedrockModel

from ..config import AGENT_TEMPERATURE, MODEL_ID
from ..prompts import PATHOGEN_RESPONSE_PROMPT
from ..tools.actions import create_action_tools


@tool
def pathogen_response_agent(
    crops_status: str,
    environment: str,
    current_sol: int,
) -> str:
    """Handle a pathogen_outbreak crisis by triaging crops and controlling spread.

    The crisis type is 'pathogen_outbreak' — it is returned by get_active_crises()
    after admin injection via events.open_crisis(). [CRITICAL-3]
    Triages crops: remove health < 20% (lost cause), keep health > 20%
    (recoverable). Adjusts humidity to < 70% to reduce fungal risk.
    Does NOT call advance_simulation.

    Args:
        crops_status: JSON string from get_crops_status()
        environment: JSON string from get_greenhouse_environment()
        current_sol: Current simulation sol number for context

    Returns:
        String describing the pathogen response actions taken.
    """
    actions = create_action_tools()
    model = BedrockModel(model_id=MODEL_ID, temperature=AGENT_TEMPERATURE)
    agent = Agent(
        model=model,
        system_prompt=PATHOGEN_RESPONSE_PROMPT,
        tools=[
            actions["remove_crop"],
            actions["plant_crop"],
            actions["set_zone_environment"],
        ],
    )

    prompt = (
        f"Sol {current_sol} — Pathogen Outbreak Response\n\n"
        f"Crops Status:\n{crops_status}\n\n"
        f"Greenhouse Environment:\n{environment}\n\n"
        "Identify infected crops and assess their health. Remove crops with "
        "health < 20% (lost cause). Adjust zone humidity to < 70% to reduce "
        "fungal spread risk. For freed area, plan replanting based on "
        f"current sol ({current_sol}): if sol < 350, prefer potatoes; "
        "otherwise use fast crops (radish)."
    )

    result = agent(prompt)
    return str(result.message)
