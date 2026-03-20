"""Storm Preparation specialist agent for the Mars greenhouse.

Triggered by dust storm detection via weather telemetry (dust_opacity > 1.0),
NOT by crisis type. [CRITICAL-2]
Advisory-only: returns text recommendations, does NOT execute actions.
"""

from __future__ import annotations

from strands import Agent, tool
from strands.models.bedrock import BedrockModel

from ..config import AGENT_TEMPERATURE, SPECIALIST_MODEL_ID
from ..prompts import STORM_PREPARATION_PROMPT


@tool
def storm_preparation_agent(
    energy_status: str,
    weather_forecast: str,
    crops_status: str,
    current_sol: int,
) -> str:
    """Get expert advice on preparing for a dust storm.

    Returns text recommendations for storm preparation. The orchestrator
    should read the advice and then execute actions itself.

    Args:
        energy_status: JSON string from get_energy_status()
        weather_forecast: JSON string from weather forecast (LSTM or simulation)
        crops_status: JSON string from get_crops_status()
        current_sol: Current simulation sol number

    Returns:
        String describing recommended storm preparation actions.
    """
    model = BedrockModel(model_id=SPECIALIST_MODEL_ID, temperature=AGENT_TEMPERATURE)
    agent = Agent(
        model=model,
        system_prompt=STORM_PREPARATION_PROMPT
        + "\n\nIMPORTANT: You are an ADVISOR. Describe exactly what actions "
        "should be taken with specific parameter values, but do NOT call any "
        "action tools. The orchestrator will execute your recommendations.",
    )

    prompt = (
        f"Sol {current_sol} — Dust Storm Preparation\n\n"
        "A dust storm has been detected via weather telemetry (dust_opacity > 1.0). "
        "This is a weather-based detection — NOT from get_active_crises().\n\n"
        f"Energy Status:\n{energy_status}\n\n"
        f"Weather Forecast:\n{weather_forecast}\n\n"
        f"Crops Status:\n{crops_status}\n\n"
        "Recommend: battery pre-charging allocations, non-essential consumption "
        "reduction, photoperiod targets (12h/sol minimum). Calculate how many sols "
        "the greenhouse can sustain in battery-only mode. Be specific with exact "
        "parameter values."
    )

    result = agent(prompt)
    return str(result.message)
