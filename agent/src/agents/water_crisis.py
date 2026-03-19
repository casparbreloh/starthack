"""Water Crisis specialist agent for the Mars greenhouse.

Handles water_recycling_decline and water_shortage crisis types. [H-4]
"""

from __future__ import annotations

from strands import Agent, tool
from strands.models.bedrock import BedrockModel

from ..config import AGENT_TEMPERATURE, MODEL_ID
from ..prompts import WATER_CRISIS_PROMPT
from ..tools._state import get_client
from ..tools.actions import create_action_tools


@tool
def water_crisis_agent(
    water_status: str,
    crops_status: str,
    crisis_type: str,
    current_sol: int,
) -> str:
    """Handle a water crisis by analyzing status and taking corrective actions.

    Pass the exact crisis type string from get_active_crises() as crisis_type.
    Handles 'water_recycling_decline' (filter degradation) and 'water_shortage'
    (reservoir critically low). Tool set: clean_water_filters, set_irrigation,
    remove_crop. Does NOT call advance_simulation.

    Args:
        water_status: JSON string from get_water_status()
        crops_status: JSON string from get_crops_status()
        crisis_type: Exact crisis type from get_active_crises()
                     (e.g., 'water_recycling_decline' or 'water_shortage')
        current_sol: Current simulation sol number for context

    Returns:
        String describing the crisis response actions taken.
    """
    actions = create_action_tools(get_client())
    model = BedrockModel(model_id=MODEL_ID, temperature=AGENT_TEMPERATURE)
    agent = Agent(
        model=model,
        system_prompt=WATER_CRISIS_PROMPT,
        tools=[
            actions["clean_water_filters"],
            actions["set_irrigation"],
            actions["remove_crop"],
        ],
    )

    prompt = (
        f"Sol {current_sol} — Water Crisis Response\n\n"
        f"Crisis type: {crisis_type}\n\n"
        f"Water Status:\n{water_status}\n\n"
        f"Crops Status:\n{crops_status}\n\n"
        "Analyze the water system status and take appropriate actions to "
        "resolve the crisis. Prioritize based on crisis type: "
        "for water_recycling_decline, clean filters and reduce load; "
        "for water_shortage, reduce irrigation aggressively and prioritize "
        "high-value crops."
    )

    result = agent(prompt)
    return str(result.message)
