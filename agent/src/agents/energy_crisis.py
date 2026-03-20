"""Energy Crisis specialist agent for the Mars greenhouse.

Handles the energy_disruption crisis type. [CRITICAL-1]
Advisory-only: returns text recommendations, does NOT execute actions.
"""

from __future__ import annotations

from strands import Agent, tool
from strands.models.bedrock import BedrockModel

from ..config import AGENT_TEMPERATURE, SPECIALIST_MODEL_ID
from ..prompts import ENERGY_CRISIS_PROMPT


@tool
def energy_crisis_agent(
    energy_status: str,
    environment: str,
    weather_forecast: str,
    current_sol: int,
) -> str:
    """Get expert advice on handling an energy_disruption crisis.

    Returns text recommendations for energy rebalancing. The orchestrator
    should read the advice and then execute actions itself.

    Args:
        energy_status: JSON string from get_energy_status()
        environment: JSON string from get_greenhouse_environment()
        weather_forecast: JSON string from get_weather_forecast() or LSTM forecast
        current_sol: Current simulation sol number for context

    Returns:
        String describing recommended energy crisis response actions.
    """
    model = BedrockModel(model_id=SPECIALIST_MODEL_ID, temperature=AGENT_TEMPERATURE)
    agent = Agent(
        model=model,
        system_prompt=ENERGY_CRISIS_PROMPT
        + "\n\nIMPORTANT: You are an ADVISOR. Describe exactly what actions "
        "should be taken with specific parameter values, but do NOT call any "
        "action tools. The orchestrator will execute your recommendations.",
    )

    prompt = (
        f"Sol {current_sol} — Energy Crisis Response (energy_disruption)\n\n"
        f"Energy Status:\n{energy_status}\n\n"
        f"Greenhouse Environment:\n{environment}\n\n"
        f"Weather Forecast:\n{weather_forecast}\n\n"
        "Analyze the energy situation and recommend immediate actions to prevent "
        "battery depletion. Prioritize heating over lighting. Recommend "
        "photoperiod reductions. Calculate how many sols the battery can sustain "
        "at current drain rate. Be specific with exact parameter values."
    )

    result = agent(prompt)
    return str(result.message)
