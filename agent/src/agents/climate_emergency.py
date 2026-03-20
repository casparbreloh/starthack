"""Climate Emergency specialist agent for the Mars greenhouse.

Handles temperature_failure and co2_imbalance crisis types. [C-4]
Advisory-only: returns text recommendations, does NOT execute actions.
"""

from __future__ import annotations

from strands import Agent, tool
from strands.models.bedrock import BedrockModel

from ..config import AGENT_TEMPERATURE, SPECIALIST_MODEL_ID
from ..prompts import CLIMATE_EMERGENCY_PROMPT


@tool
def climate_emergency_agent(
    environment: str,
    energy_status: str,
    crops_status: str,
    nutrients_status: str,
    crisis_type: str,
    current_sol: int,
) -> str:
    """Get expert advice on handling a climate emergency.

    Returns text recommendations for climate management. The orchestrator
    should read the advice and then execute actions itself.

    Args:
        environment: JSON string from get_greenhouse_environment()
        energy_status: JSON string from get_energy_status()
        crops_status: JSON string from get_crops_status()
        nutrients_status: JSON string from get_nutrients_status()
        crisis_type: Exact crisis type from get_active_crises()
                     (e.g., 'temperature_failure' or 'co2_imbalance')
        current_sol: Current simulation sol number for context

    Returns:
        String describing recommended climate emergency response actions.
    """
    model = BedrockModel(model_id=SPECIALIST_MODEL_ID, temperature=AGENT_TEMPERATURE)
    agent = Agent(
        model=model,
        system_prompt=CLIMATE_EMERGENCY_PROMPT
        + "\n\nIMPORTANT: You are an ADVISOR. Describe exactly what actions "
        "should be taken with specific parameter values, but do NOT call any "
        "action tools. The orchestrator will execute your recommendations.",
    )

    prompt = (
        f"Sol {current_sol} — Climate Emergency Response\n\n"
        f"Crisis type: {crisis_type}\n\n"
        f"Greenhouse Environment:\n{environment}\n\n"
        f"Energy Status:\n{energy_status}\n\n"
        f"Crops Status:\n{crops_status}\n\n"
        f"Nutrients Status:\n{nutrients_status}\n\n"
        "Analyze the climate situation and recommend corrective actions. "
        "For temperature_failure: recommend setpoint adjustments (max 2C/hour), "
        "energy rebalancing. For co2_imbalance: recommend CO2 target adjustments, "
        "nutrient pump allocation. Be specific with exact parameter values."
    )

    result = agent(prompt)
    return str(result.message)
