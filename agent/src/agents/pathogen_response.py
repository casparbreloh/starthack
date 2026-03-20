"""Pathogen Response specialist agent for the Mars greenhouse.

Handles the pathogen_outbreak crisis type. [CRITICAL-3]
Advisory-only: returns text recommendations, does NOT execute actions.
"""

from __future__ import annotations

from strands import Agent, tool
from strands.models.bedrock import BedrockModel

from ..config import AGENT_TEMPERATURE, SPECIALIST_MODEL_ID
from ..prompts import PATHOGEN_RESPONSE_PROMPT


@tool
def pathogen_response_agent(
    crops_status: str,
    environment: str,
    current_sol: int,
) -> str:
    """Get expert advice on handling a pathogen outbreak.

    Returns text recommendations for pathogen response. The orchestrator
    should read the advice and then execute actions itself.

    Args:
        crops_status: JSON string from get_crops_status()
        environment: JSON string from get_greenhouse_environment()
        current_sol: Current simulation sol number for context

    Returns:
        String describing recommended pathogen response actions.
    """
    model = BedrockModel(model_id=SPECIALIST_MODEL_ID, temperature=AGENT_TEMPERATURE)
    agent = Agent(
        model=model,
        system_prompt=PATHOGEN_RESPONSE_PROMPT
        + "\n\nIMPORTANT: You are an ADVISOR. Describe exactly what actions "
        "should be taken with specific parameter values, but do NOT call any "
        "action tools. The orchestrator will execute your recommendations.",
    )

    prompt = (
        f"Sol {current_sol} — Pathogen Outbreak Response\n\n"
        f"Crops Status:\n{crops_status}\n\n"
        f"Greenhouse Environment:\n{environment}\n\n"
        "Identify infected crops and assess their health. Recommend removing crops "
        "with health < 20% (lost cause). Recommend zone humidity < 70% to reduce "
        "fungal spread. For freed area, recommend replanting based on "
        f"current sol ({current_sol}): if sol < 350, prefer potatoes; "
        "otherwise use fast crops (radish). Be specific with crop IDs and exact values."
    )

    result = agent(prompt)
    return str(result.message)
