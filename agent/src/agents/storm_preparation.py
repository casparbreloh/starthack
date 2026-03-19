"""Storm Preparation specialist agent for the Mars greenhouse.

Triggered by dust storm detection via weather telemetry (dust_opacity > 1.0),
NOT by crisis type. [CRITICAL-2]
"""

from __future__ import annotations

from strands import Agent, tool
from strands.models.bedrock import BedrockModel

from ..config import AGENT_TEMPERATURE, MODEL_ID
from ..prompts import STORM_PREPARATION_PROMPT
from ..tools._state import get_client
from ..tools.actions import create_action_tools


@tool
def storm_preparation_agent(
    energy_status: str,
    weather_forecast: str,
    crops_status: str,
    current_sol: int,
) -> str:
    """Prepare the greenhouse for an incoming dust storm.

    WEATHER-BASED DETECTION: This agent is invoked because the orchestrator
    detected dust_opacity > 1.0 in weather telemetry. Dust storms are NOT
    a crisis type — they do NOT appear in get_active_crises(). [CRITICAL-2]

    Focuses on: battery pre-charging, reducing non-essential consumption,
    photoperiod reduction, and calculating storm survival duration.
    Does NOT call advance_simulation.

    Args:
        energy_status: JSON string from get_energy_status()
        weather_forecast: JSON string from weather forecast (LSTM or simulation)
        crops_status: JSON string from get_crops_status()
        current_sol: Current simulation sol number

    Returns:
        String describing the storm preparation actions taken.
    """
    actions = create_action_tools(get_client())
    model = BedrockModel(model_id=MODEL_ID, temperature=AGENT_TEMPERATURE)
    agent = Agent(
        model=model,
        system_prompt=STORM_PREPARATION_PROMPT,
        tools=[actions["allocate_energy"], actions["set_zone_environment"]],
    )

    prompt = (
        f"Sol {current_sol} — Dust Storm Preparation\n\n"
        "A dust storm has been detected via weather telemetry (dust_opacity > 1.0). "
        "This is a weather-based detection — NOT from get_active_crises().\n\n"
        f"Energy Status:\n{energy_status}\n\n"
        f"Weather Forecast:\n{weather_forecast}\n\n"
        f"Crops Status:\n{crops_status}\n\n"
        "Pre-charge batteries, reduce non-essential consumption, reduce "
        "photoperiods to 12h/sol minimum. Calculate how many sols the "
        "greenhouse can sustain in battery-only mode."
    )

    result = agent(prompt)
    return str(result.message)
