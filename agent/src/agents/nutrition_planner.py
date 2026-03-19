"""Nutrition Planner specialist agent for the Mars greenhouse.

Handles food_shortage and nutrient_depletion crisis types. [C-5]
"""

from __future__ import annotations

from strands import Agent, tool
from strands.models.bedrock import BedrockModel

from ..config import AGENT_TEMPERATURE, MODEL_ID
from ..prompts import NUTRITION_PLANNER_PROMPT
from ..tools._state import get_client
from ..tools.actions import create_action_tools
from ..tools.telemetry import create_telemetry_tools


@tool
def nutrition_planner_agent(
    crew_nutrition: str,
    crops_status: str,
    nutrients_status: str,
    crisis_type: str,
    current_sol: int,
    mission_sols: int = 450,
) -> str:
    """Handle a food_shortage or nutrient_depletion crisis.

    Pass the exact crisis type string from get_active_crises() as crisis_type.
    Handles 'food_shortage' (crew food reserves low — emergency harvests and
    planting) and 'nutrient_depletion' (N < 120 ppm or K < 180 ppm —
    targeted nutrient boosts). [C-5, HIGH-2]
    Does NOT call advance_simulation.

    Args:
        crew_nutrition: JSON string from get_crew_nutrition()
        crops_status: JSON string from get_crops_status()
        nutrients_status: JSON string from get_nutrients_status()
        crisis_type: Exact crisis type from get_active_crises()
                     (e.g., 'food_shortage' or 'nutrient_depletion')
        current_sol: Current simulation sol number
        mission_sols: Total mission length (default 450)

    Returns:
        String describing the nutrition crisis response actions taken.
    """
    client = get_client()
    actions = create_action_tools(client)
    telemetry = create_telemetry_tools(client)
    model = BedrockModel(model_id=MODEL_ID, temperature=AGENT_TEMPERATURE)
    agent = Agent(
        model=model,
        system_prompt=NUTRITION_PLANNER_PROMPT,
        tools=[
            actions["harvest_crop"],
            actions["plant_crop"],
            telemetry["get_crops_status"],
            actions["adjust_nutrients"],
        ],
    )

    sols_remaining = mission_sols - current_sol

    prompt = (
        f"Sol {current_sol} — Nutrition Crisis Response ({sols_remaining} sols remaining)\n\n"
        f"Crisis type: {crisis_type}\n\n"
        f"Crew Nutrition:\n{crew_nutrition}\n\n"
        f"Crops Status:\n{crops_status}\n\n"
        f"Nutrients Status:\n{nutrients_status}\n\n"
        "For food_shortage: emergency harvest any crop with growth_pct >= 80%, "
        "then plant fastest crops (radish) immediately. For nutrient_depletion: "
        "apply targeted boosts (N-boost when N < 120 ppm, K-boost when K < 180 ppm). "
        "Conserve nutrient stock if stock_remaining_pct < 20%."
    )

    result = agent(prompt)
    return str(result.message)
