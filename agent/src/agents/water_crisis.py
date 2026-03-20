"""Water Crisis specialist agent for the Mars greenhouse.

Handles water_recycling_decline and water_shortage crisis types. [H-4]
Advisory-only: returns text recommendations, does NOT execute actions.
"""

from __future__ import annotations

from strands import Agent, tool
from strands.models.bedrock import BedrockModel

from ..config import AGENT_TEMPERATURE, SPECIALIST_MODEL_ID
from ..prompts import WATER_CRISIS_PROMPT


@tool
def water_crisis_agent(
    water_status: str,
    crops_status: str,
    crisis_type: str,
    current_sol: int,
) -> str:
    """Get expert advice on handling a water crisis.

    Returns text recommendations for water management. The orchestrator
    should read the advice and then execute actions itself.

    Args:
        water_status: JSON string from get_water_status()
        crops_status: JSON string from get_crops_status()
        crisis_type: Exact crisis type from get_active_crises()
                     (e.g., 'water_recycling_decline' or 'water_shortage')
        current_sol: Current simulation sol number for context

    Returns:
        String describing recommended water crisis response actions.
    """
    model = BedrockModel(model_id=SPECIALIST_MODEL_ID, temperature=AGENT_TEMPERATURE)
    agent = Agent(
        model=model,
        system_prompt=WATER_CRISIS_PROMPT
        + "\n\nIMPORTANT: You are an ADVISOR. Describe exactly what actions "
        "should be taken with specific parameter values, but do NOT call any "
        "action tools. The orchestrator will execute your recommendations.",
    )

    prompt = (
        f"Sol {current_sol} — Water Crisis Response\n\n"
        f"Crisis type: {crisis_type}\n\n"
        f"Water Status:\n{water_status}\n\n"
        f"Crops Status:\n{crops_status}\n\n"
        "Analyze the water system status and recommend appropriate actions. "
        "For water_recycling_decline: recommend filter cleaning and load reduction. "
        "For water_shortage: recommend aggressive irrigation reduction and "
        "prioritize high-value crops. Be specific with exact parameter values."
    )

    result = agent(prompt)
    return str(result.message)
