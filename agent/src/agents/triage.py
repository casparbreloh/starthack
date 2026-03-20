"""Triage specialist agent for multi-crisis coordination.

Handles multiple simultaneous crises by prioritizing and dispatching to
individual specialist agents in the correct order. [MEDIUM-5]
"""

from __future__ import annotations

from strands import Agent, tool
from strands.models.bedrock import BedrockModel

from ..config import AGENT_TEMPERATURE, SPECIALIST_MODEL_ID
from ..prompts import TRIAGE_PROMPT
from .climate_emergency import climate_emergency_agent
from .energy_crisis import energy_crisis_agent
from .nutrition_planner import nutrition_planner_agent
from .pathogen_response import pathogen_response_agent
from .storm_preparation import storm_preparation_agent
from .water_crisis import water_crisis_agent


@tool
def triage_agent(
    active_crises: str,
    full_state: str,
    current_sol: int,
) -> str:
    """Coordinate response to multiple simultaneous crises.

    Prioritizes crises by severity and cascading risk, then dispatches to
    individual specialists in order. Dust storms are NOT handled here —
    the orchestrator handles them directly via weather telemetry. [CRITICAL-2]

    Priority order (highest first):
    1. energy_disruption (battery death kills everything)
    2. temperature_failure (crops die within hours)
    3. water_shortage (critical if < 50L)
    4. water_recycling_decline (slower-developing)
    5. pathogen_outbreak (crop loss is gradual)
    6. food_shortage (days_of_food_remaining < 5)
    7. nutrient_depletion (slower-developing)
    8. co2_imbalance (above immediate kill threshold)

    Note: Strands SDK handles agents-as-tools synchronously. Specialists
    do NOT call other specialists — no recursion beyond one level. [MEDIUM-5]
    Does NOT call advance_simulation.

    Args:
        active_crises: JSON string from get_active_crises()
        full_state: JSON string with current greenhouse state snapshot
        current_sol: Current simulation sol number

    Returns:
        String summarizing all crisis responses and actions taken.
    """
    model = BedrockModel(model_id=SPECIALIST_MODEL_ID, temperature=AGENT_TEMPERATURE)
    agent = Agent(
        model=model,
        system_prompt=TRIAGE_PROMPT,
        tools=[
            water_crisis_agent,
            energy_crisis_agent,
            pathogen_response_agent,
            climate_emergency_agent,
            nutrition_planner_agent,
            storm_preparation_agent,
        ],
    )

    prompt = (
        f"Sol {current_sol} — Multi-Crisis Triage\n\n"
        f"Active Crises:\n{active_crises}\n\n"
        f"Full State:\n{full_state}\n\n"
        "Multiple crises are active simultaneously. Prioritize by severity "
        "and cascading risk. Dispatch to individual specialists in priority "
        "order. Note: dust storms are handled separately by the orchestrator "
        "via weather telemetry — do not dispatch storm_preparation_agent "
        "unless you have explicit dust storm data in the state."
    )

    result = agent(prompt)
    return str(result.message)
