"""Climate Emergency specialist agent for the Mars greenhouse.

Handles temperature_failure and co2_imbalance crisis types. [C-4]
"""

from __future__ import annotations

from strands import Agent, tool
from strands.models.bedrock import BedrockModel

from ..config import AGENT_TEMPERATURE, MODEL_ID
from ..prompts import CLIMATE_EMERGENCY_PROMPT
from ..tools._state import get_client
from ..tools.actions import create_action_tools


@tool
def climate_emergency_agent(
    environment: str,
    energy_status: str,
    crops_status: str,
    nutrients_status: str,
    crisis_type: str,
    current_sol: int,
) -> str:
    """Handle a climate emergency (temperature_failure or co2_imbalance).

    Pass the exact crisis type string from get_active_crises() as crisis_type.
    Handles 'temperature_failure' (too hot >28C or too cold <15C) and
    'co2_imbalance' (CO2 < 500 ppm = STRESS_CO2_LOW_PPM). [C-4, MEDIUM-4]
    Temperature changes must not exceed 2C/hour to avoid thermal shock.
    Does NOT call advance_simulation.

    Args:
        environment: JSON string from get_greenhouse_environment()
        energy_status: JSON string from get_energy_status()
        crops_status: JSON string from get_crops_status()
        nutrients_status: JSON string from get_nutrients_status()
        crisis_type: Exact crisis type from get_active_crises()
                     (e.g., 'temperature_failure' or 'co2_imbalance')
        current_sol: Current simulation sol number for context

    Returns:
        String describing the climate emergency response actions taken.
    """
    actions = create_action_tools(get_client())
    model = BedrockModel(model_id=MODEL_ID, temperature=AGENT_TEMPERATURE)
    agent = Agent(
        model=model,
        system_prompt=CLIMATE_EMERGENCY_PROMPT,
        tools=[
            actions["set_zone_environment"],
            actions["allocate_energy"],
            actions["adjust_nutrients"],
        ],
    )

    prompt = (
        f"Sol {current_sol} — Climate Emergency Response\n\n"
        f"Crisis type: {crisis_type}\n\n"
        f"Greenhouse Environment:\n{environment}\n\n"
        f"Energy Status:\n{energy_status}\n\n"
        f"Crops Status:\n{crops_status}\n\n"
        f"Nutrients Status:\n{nutrients_status}\n\n"
        "Analyze the climate situation and take appropriate corrective actions. "
        "For temperature_failure: adjust setpoints (max 2C/hour change), "
        "rebalance energy for heating/cooling. For co2_imbalance: adjust CO2 "
        "targets (stress threshold is 500 ppm), check nutrient pump allocation."
    )

    result = agent(prompt)
    return str(result.message)
