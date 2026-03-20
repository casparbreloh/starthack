"""Nutrition Planner specialist agent for the Mars greenhouse.

Handles food_shortage and nutrient_depletion crisis types. [C-5]
Advisory-only: returns text recommendations, does NOT execute actions.
"""

from __future__ import annotations

from strands import Agent, tool
from strands.models.bedrock import BedrockModel

from ..config import AGENT_TEMPERATURE, SPECIALIST_MODEL_ID
from ..prompts import NUTRITION_PLANNER_PROMPT


@tool
def nutrition_planner_agent(
    crew_nutrition: str,
    crops_status: str,
    nutrients_status: str,
    crisis_type: str,
    current_sol: int,
    mission_sols: int = 450,
) -> str:
    """Get expert advice on handling a nutrition crisis.

    Returns text recommendations for nutrition management. The orchestrator
    should read the advice and then execute actions itself.

    Args:
        crew_nutrition: JSON string from get_crew_nutrition()
        crops_status: JSON string from get_crops_status()
        nutrients_status: JSON string from get_nutrients_status()
        crisis_type: Exact crisis type from get_active_crises()
                     (e.g., 'food_shortage' or 'nutrient_depletion')
        current_sol: Current simulation sol number
        mission_sols: Total mission length (default 450)

    Returns:
        String describing recommended nutrition crisis response actions.
    """
    model = BedrockModel(model_id=SPECIALIST_MODEL_ID, temperature=AGENT_TEMPERATURE)
    agent = Agent(
        model=model,
        system_prompt=NUTRITION_PLANNER_PROMPT
        + "\n\nIMPORTANT: You are an ADVISOR. Describe exactly what actions "
        "should be taken with specific parameter values, but do NOT call any "
        "action tools. The orchestrator will execute your recommendations.",
    )

    sols_remaining = mission_sols - current_sol

    prompt = (
        f"Sol {current_sol} — Nutrition Crisis Response ({sols_remaining} sols remaining)\n\n"
        f"Crisis type: {crisis_type}\n\n"
        f"Crew Nutrition:\n{crew_nutrition}\n\n"
        f"Crops Status:\n{crops_status}\n\n"
        f"Nutrients Status:\n{nutrients_status}\n\n"
        "For food_shortage: recommend emergency harvests (crops with growth_pct >= 80%), "
        "then fastest replanting (radish). For nutrient_depletion: recommend targeted "
        "boosts (N-boost when N < 120 ppm, K-boost when K < 180 ppm). "
        "Conserve nutrient stock if stock_remaining_pct < 20%. Be specific with "
        "exact parameter values and crop IDs."
    )

    result = agent(prompt)
    return str(result.message)
