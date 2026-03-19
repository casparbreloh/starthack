"""Energy Crisis specialist agent for the Mars greenhouse.

Handles the energy_disruption crisis type. [CRITICAL-1]
"""

from __future__ import annotations

from strands import Agent, tool
from strands.models.bedrock import BedrockModel

from ..config import AGENT_TEMPERATURE, MODEL_ID
from ..prompts import ENERGY_CRISIS_PROMPT
from ..tools.actions import create_action_tools


@tool
def energy_crisis_agent(
    energy_status: str,
    environment: str,
    weather_forecast: str,
    current_sol: int,
) -> str:
    """Handle an energy_disruption crisis by rebalancing power allocation.

    Pass the exact crisis type string from get_active_crises() as context.
    The crisis type is 'energy_disruption' (NOT 'energy_crisis'). [CRITICAL-1]
    Handles battery preservation, heating priority, and photoperiod reduction.
    Does NOT call advance_simulation.

    Args:
        energy_status: JSON string from get_energy_status()
        environment: JSON string from get_greenhouse_environment()
        weather_forecast: JSON string from get_weather_forecast() or LSTM forecast
        current_sol: Current simulation sol number for context

    Returns:
        String describing the energy crisis response actions taken.
    """
    actions = create_action_tools()
    model = BedrockModel(model_id=MODEL_ID, temperature=AGENT_TEMPERATURE)
    agent = Agent(
        model=model,
        system_prompt=ENERGY_CRISIS_PROMPT,
        tools=[actions["allocate_energy"], actions["set_zone_environment"]],
    )

    prompt = (
        f"Sol {current_sol} — Energy Crisis Response (energy_disruption)\n\n"
        f"Energy Status:\n{energy_status}\n\n"
        f"Greenhouse Environment:\n{environment}\n\n"
        f"Weather Forecast:\n{weather_forecast}\n\n"
        "Analyze the energy situation and take immediate actions to prevent "
        "battery depletion. Prioritize heating over lighting. Reduce "
        "photoperiods to cut consumption. Calculate how many sols the "
        "battery can sustain at current drain rate."
    )

    result = agent(prompt)
    return str(result.message)
