"""Orchestrator agent for the Mars greenhouse mission.

The orchestrator LLM reasons about EVERY decision EVERY sol:
environment, irrigation, energy, planting, harvesting, nutrients.
Specialist sub-agents handle crisis escalation with focused context.
"""

from __future__ import annotations

import json
import logging
import time
from datetime import datetime

from strands import Agent
from strands.models.bedrock import BedrockModel

from ..config import AGENT_TEMPERATURE, AGENTCORE_GATEWAY_URL, MISSION_SOLS, MODEL_ID
from ..energy_projection import project_energy_budget, summarize_energy_projection
from ..journal import CrossSessionLearning, DecisionJournal, compact_state_summary
from ..mcp_client import create_mcp_client, discover_kb_tools
from ..prompts import ORCHESTRATOR_SYSTEM_PROMPT
from ..sim_client import SimClient
from ..tools.actions import (
    adjust_nutrients,
    advance_simulation,
    allocate_energy,
    clean_water_filters,
    harvest_crop,
    plant_crop,
    remove_crop,
    set_irrigation,
    set_zone_environment,
)
from ..tools.telemetry import get_crop_catalog, read_all_telemetry
from ..weather_integration import WeatherForecaster
from .climate_emergency import climate_emergency_agent
from .energy_crisis import energy_crisis_agent
from .nutrition_planner import nutrition_planner_agent
from .pathogen_response import pathogen_response_agent
from .storm_preparation import storm_preparation_agent
from .triage import triage_agent
from .water_crisis import water_crisis_agent

logger = logging.getLogger(__name__)

# All 8 action tools (NOT advance_simulation)
ACTION_TOOLS = [
    allocate_energy,
    set_zone_environment,
    set_irrigation,
    clean_water_filters,
    plant_crop,
    harvest_crop,
    remove_crop,
    adjust_nutrients,
]

# All 7 specialist agent tools
SPECIALIST_TOOLS = [
    water_crisis_agent,
    energy_crisis_agent,
    pathogen_response_agent,
    climate_emergency_agent,
    nutrition_planner_agent,
    storm_preparation_agent,
    triage_agent,
]


def create_orchestrator(
    cross_session_context: str = "",
    kb_tools: list | None = None,
) -> Agent:
    """Create a fresh orchestrator Agent instance.

    Creates a new Agent each sol to prevent unbounded internal message history
    accumulation. [R8-M6] Cross-sol context comes from the decision journal,
    not Agent state.

    Tool count: 1 read_all_telemetry + 1 get_crop_catalog + 8 action tools +
    7 specialist agent tools + N MCP KB tools = 17 + N tools. [SC-2, R6-MCP5]
    advance_simulation is NOT included — it is called programmatically. [H-7]

    Args:
        cross_session_context: Previous run summaries formatted for prompt injection. [R5-H7]
        kb_tools: List of MCP KB tool objects discovered from AgentCore gateway. [R6-MCP1]

    Returns:
        Configured Strands Agent ready to run a sol.
    """
    n_kb = len(kb_tools or [])
    logger.info("Creating orchestrator with %d KB tools", n_kb)  # [R10-M2]
    if n_kb == 0 and AGENTCORE_GATEWAY_URL:
        logger.warning(
            "No KB tools available — orchestrator running without Syngenta KB."
        )

    system_prompt = ORCHESTRATOR_SYSTEM_PROMPT
    if cross_session_context:
        system_prompt = (
            system_prompt + "\n\n## Previous Run Learnings\n" + cross_session_context
        )

    tools = [
        read_all_telemetry,
        get_crop_catalog,
        *ACTION_TOOLS,
        *SPECIALIST_TOOLS,
        *(kb_tools or []),
    ]

    model = BedrockModel(model_id=MODEL_ID, temperature=AGENT_TEMPERATURE)
    return Agent(
        model=model,
        system_prompt=system_prompt,
        tools=tools,
    )


def run_sol(
    client: SimClient,
    sol: int,
    orchestrator: Agent,
    weather_forecaster: WeatherForecaster,
    journal: DecisionJournal,
    prev_score: float | None = None,
) -> dict:
    """Run one sol of the mission — the core agent loop.

    Flow [ARCH-6]:
    1. Read telemetry, capture pre-advance crises
    2. Compute LSTM weather forecast and energy projection
    3. Update journal with previous sol outcome
    4. LLM routine decisions (with retry) [HIGH-4]
    5. Advance simulation (middle, not end) [ARCH-6]
    6b. Log crop death events [R10-C2]
    7. Post-advance crisis detection via get_active_crises() [ARCH-6, R8-H4]
       Compare pre/post crisis IDs to find NEW crises only [R7-H1]
    8. Return result dict [R7-H4]

    Args:
        client: SimClient instance
        sol: Current sol number (0-indexed; advance makes sim sol = sol+1)
        orchestrator: Freshly-created orchestrator Agent
        weather_forecaster: WeatherForecaster for LSTM forecasts
        journal: DecisionJournal for feedback loop
        prev_score: Overall score from previous sol (for score_delta)

    Returns:
        Dict with keys: sol, actions, crises_handled, score, advance_response, mission_phase
    """
    logger.info("=== Sol %d ===", sol)
    actions_list: list[str] = []
    crises_handled: list[str] = []

    # ------------------------------------------------------------------ #
    # Step 1: Read all telemetry                                          #
    # ------------------------------------------------------------------ #
    state = client.read_all_telemetry()
    pre_advance_crises = state["active_crises"]  # [R7-H1]

    # ------------------------------------------------------------------ #
    # Step 2: LSTM weather forecast + energy projection [ARCH-1, ARCH-2] #
    # ------------------------------------------------------------------ #
    weather_context = weather_forecaster.get_full_context(
        sol,
        weather_history=state["weather_history"],
        current_weather=state["weather_current"],
    )
    energy_projection = project_energy_budget(
        weather_context["forecast_7sol"],
        state["energy_status"],
        state["weather_current"],
    )  # [R8-H3, R9-C2]
    energy_summary = summarize_energy_projection(energy_projection)

    # ------------------------------------------------------------------ #
    # Step 3: Update previous sol's journal outcome [ARCH-4, R5-C4]      #
    # ------------------------------------------------------------------ #
    current_score = state["score_current"]["scores"]["overall_score"]
    if prev_score is not None:
        score_delta = current_score - prev_score
        journal.update_previous_outcome(
            {
                "score_delta": score_delta,
                "state_summary": compact_state_summary(state),
            }
        )

    # ------------------------------------------------------------------ #
    # Step 4: LLM routine decisions with retry [HIGH-4]                  #
    # ------------------------------------------------------------------ #
    per_sol_prompt = _build_sol_prompt(
        sol, state, weather_context, energy_summary, journal
    )
    result = None

    try:
        result = orchestrator(per_sol_prompt)
    except Exception as exc:
        logger.warning(
            "Sol %d: orchestrator call failed (%s), retrying in 5s...", sol, exc
        )
        time.sleep(5)
        try:
            result = orchestrator(per_sol_prompt)
        except Exception as exc2:
            logger.warning(
                "Sol %d: orchestrator retry also failed (%s). Skipping LLM decisions.",
                sol,
                exc2,
            )
            client.log_decision(sol, decisions=["[SKIPPED — LLM call failed]"])
            result = None

    # Extract actions from LLM tool call history [R5-H6, R8-H1]
    reasoning = ""
    if result is not None:
        try:
            content = result.message.get("content", [])
            for block in content:
                if isinstance(block, dict):
                    if block.get("type") == "tool_use":
                        action_str = (
                            f"{block['name']}({json.dumps(block.get('input', {}))})"  # type: ignore[typeddict-item]
                        )
                        actions_list.append(action_str)
                    elif block.get("type") == "text":
                        reasoning += block.get("text", "")
        except (AttributeError, TypeError, KeyError):
            reasoning = str(result.message) if result else ""

        # Log decisions via POST /agent/log_decision
        client.log_decision(
            sol,
            decisions=actions_list or ["no tools called"],  # type: ignore[arg-type]
            risk_assessment=reasoning[:500] if reasoning else "nominal",
        )

    # Record in journal [R5-SC2]
    journal.record_decision(
        sol, reasoning[:500], actions_list, compact_state_summary(state)
    )

    # ------------------------------------------------------------------ #
    # Step 6: Advance simulation [ARCH-6, R7-H5]                         #
    # ------------------------------------------------------------------ #
    advance_response: dict = {}
    mission_phase = "active"
    try:
        advance_response = advance_simulation(1)
        mission_phase = advance_response.get("mission_phase", "active")
    except Exception as exc:
        logger.warning("Sol %d: advance_simulation failed (%s)", sol, exc)
        # Check if mission is complete
        try:
            sim_status = client.get_sim_status()
            mission_phase = sim_status.get("mission_phase", "active")
        except Exception:
            pass

    # Step 6b: Log crop death events [R10-C2]
    advance_events = advance_response.get("events", [])
    for event in advance_events:
        if (
            "died" in str(event).lower()
            or "death" in str(event).lower()
            or "dead" in str(event).lower()
        ):
            logger.warning("Sol %d crop death: %s", sol, event)

    # ------------------------------------------------------------------ #
    # Step 7: Post-advance crisis detection [ARCH-6, R7-H1, R8-H4]      #
    # ------------------------------------------------------------------ #
    try:
        post_crises = client.get_active_crises()
    except Exception as exc:
        logger.warning("Sol %d: get_active_crises failed (%s)", sol, exc)
        post_crises = {"crises": []}

    # Compare by crisis ID to find NEW crises only [R7-H1, R8-H6]
    pre_ids = {c["id"] for c in pre_advance_crises.get("crises", [])}
    new_crises = [c for c in post_crises.get("crises", []) if c["id"] not in pre_ids]

    if new_crises:
        logger.info(
            "Sol %d: %d new crisis(es) detected post-advance", sol, len(new_crises)
        )
        # [R7-M2] Dust storms detected pre-advance from weather; crises post-advance
        # Build minimal prompt for post-advance crisis react [R7-M3]
        crisis_prompt = (
            f"Sol {sol} post-advance: New crises detected.\n"
            f"New crises: {json.dumps(new_crises, indent=2)}\n"
            f"Pre-advance state: {compact_state_summary(state)}\n"
            "Please call the appropriate specialist agent(s) to handle these crises."
        )
        try:
            crisis_orchestrator = create_orchestrator()
            crisis_result = crisis_orchestrator(crisis_prompt)
            # Track which crisis types were handled
            crises_handled = [c.get("type", "unknown") for c in new_crises]
            # Extract additional actions
            try:
                content = crisis_result.message.get("content", [])
                for block in content:
                    if isinstance(block, dict) and block.get("type") == "tool_use":
                        actions_list.append(
                            f"[crisis]{block['name']}({json.dumps(block.get('input', {}))})"  # type: ignore[typeddict-item]
                        )
            except (AttributeError, TypeError):
                pass
            journal.record_decision(
                sol,
                f"Crisis response: {crises_handled}",
                crises_handled,
                compact_state_summary(state),
            )
        except Exception as exc:
            logger.warning("Sol %d: crisis response failed (%s)", sol, exc)

    return {
        "sol": sol,
        "actions": actions_list,
        "crises_handled": crises_handled,
        "score": current_score,
        "advance_response": advance_response,
        "mission_phase": mission_phase,
    }


def _build_sol_prompt(
    sol: int,
    state: dict,
    weather_context: dict,
    energy_summary: str,
    journal: DecisionJournal,
) -> str:
    """Build the per-sol prompt for the orchestrator LLM."""
    prompt_parts = [
        f"## Sol {sol} — Greenhouse Status\n",
        "### Current Telemetry\n",
        f"Use `read_all_telemetry()` to get all current data. "
        f"Or use the pre-fetched snapshot summary: {_extract_key_stats(state)}\n",
    ]

    if weather_context.get("forecast_7sol"):
        prompt_parts.append(
            f"\n### LSTM Weather Forecast (7-sol)\n"
            f"{json.dumps(weather_context['forecast_7sol'][:3], indent=2)}...\n"
        )
    else:
        prompt_parts.append(
            "\n### LSTM Weather Forecast\n"
            "Unavailable (first ~30 sols — use simulation's /weather/forecast instead).\n"
        )

    if weather_context.get("sensor_anomalies"):
        prompt_parts.append(
            f"\n### Sensor Anomalies (treat as probable sensor errors)\n"
            f"{json.dumps(weather_context['sensor_anomalies'], indent=2)}\n"
        )

    prompt_parts.append(f"\n### Energy Projection\n{energy_summary}\n")

    journal_str = journal.format_for_prompt(30)
    if journal_str:
        prompt_parts.append(f"\n{journal_str}\n")

    if sol == 0:
        prompt_parts.append(
            "\n### Sol 0 Initialization\n"
            "FIRST: Call `get_crop_catalog()` to retrieve exact crop parameters "
            "(growth days, yields, kcal/kg, protein/kg, water demand). "
            "Memorize these for the entire mission.\n"
        )

    prompt_parts.append(
        "\n### Your Tasks This Sol\n"
        "1. Call `read_all_telemetry()` to get full current state\n"
        "2. Make ALL routine decisions: environment setpoints, irrigation, "
        "energy allocation, planting (check free area), harvesting (check is_ready), "
        "nutrient adjustments\n"
        "3. Check weather for dust_opacity > 1.0 → call storm_preparation_agent if detected\n"
        "4. After all decisions, provide reasoning summary for decision logging\n"
    )

    return "".join(prompt_parts)


def _extract_key_stats(state: dict) -> str:
    """Extract key statistics from telemetry state for prompt injection."""
    try:
        from ..journal import compact_state_summary

        return compact_state_summary(state)
    except Exception:
        return "state available via read_all_telemetry()"


def run_mission(
    client: SimClient,
    seed: int = 0,
    difficulty: str = "normal",
    mission_sols: int = MISSION_SOLS,
) -> dict:
    """Run the full Mars greenhouse mission.

    Args:
        client: SimClient instance
        seed: Random seed for simulation reset
        difficulty: Difficulty level ('easy', 'normal', 'hard')
        mission_sols: Number of sols to run (default 450)

    Returns:
        Mission summary dict with final score and stats.
    """
    # Step 1: Reset simulation
    client.reset(seed=seed, difficulty=difficulty)
    logger.info(
        "Simulation reset: seed=%d, difficulty=%s, sols=%d",
        seed,
        difficulty,
        mission_sols,
    )

    # Step 2: Initialize cross-session learning [ARCH-5]
    cross_session = CrossSessionLearning()
    cross_session_context = cross_session.format_for_prompt()

    # Step 3-4: Create MCP client and discover KB tools [R6-MCP4]
    mcp_client = create_mcp_client()
    with mcp_client:
        kb_tools = discover_kb_tools(mcp_client)

        # Step 5: Create orchestrator with cross-session context + KB tools [R5-H7]
        # (Fresh instance per sol in the loop; this is just for setup)
        logger.info("KB tools discovered: %d", len(kb_tools))

        # Step 6: Initialize WeatherForecaster [ARCH-1]
        weather_forecaster = WeatherForecaster()

        # Step 7: Initialize DecisionJournal [ARCH-4]
        journal = DecisionJournal()

        # Step 9: Mission loop [R5-M8, R8-M6]
        run_id = datetime.utcnow().strftime("%Y%m%d_%H%M%S")  # [R5-IR3]
        prev_score: float | None = None
        last_advance_response: dict = {}
        total_crises_seen = 0

        for sol in range(mission_sols):
            if sol % 50 == 0:
                logger.info("Progress: sol %d / %d", sol, mission_sols)

            # [R8-M6] Fresh orchestrator per sol to prevent history accumulation
            orchestrator = create_orchestrator(cross_session_context, kb_tools)

            sol_result = run_sol(
                client, sol, orchestrator, weather_forecaster, journal, prev_score
            )
            prev_score = sol_result["score"]
            last_advance_response = sol_result["advance_response"]
            total_crises_seen += len(sol_result["crises_handled"])

            # [R5-H8] Check for mission completion
            if sol_result["mission_phase"] == "complete":
                logger.info("Mission completed at sol %d", sol)
                break

        # Step 11: Fetch final score [R5-H8]
        last_phase = last_advance_response.get("mission_phase", "active")
        if last_phase == "complete":
            try:
                final_score_data = client.get_score_final()
            except Exception:
                final_score_data = client.get_score_current()
        else:
            final_score_data = client.get_score_current()

        final_score = final_score_data.get("scores", {}).get("overall_score", 0.0)
        logger.info("Final score: %.2f", final_score)

        # Step 12: Generate cross-session summary [ARCH-5, R5-M4, R8-M4]
        summary_agent = create_orchestrator()  # [R9-M4] No KB tools for summary
        summary_prompt = (
            "Generate a structured mission summary as JSON in a ```json code block.\n\n"
            f"Run ID: {run_id}\n"
            f"Final score: {final_score}\n"
            f"Total crises handled: {total_crises_seen}\n\n"
            f"Journal (last 50 sols):\n{journal.format_for_prompt(50)}\n\n"
            "Return JSON with exactly these keys:\n"
            '{"run_id": "...", "final_score": 0.0, "total_crises": 0, '
            '"crises_resolved": 0, "avg_daily_kcal": 0.0, '
            '"key_learnings": ["..."], "worst_decision": "...", "best_decision": "..."}\n'
        )
        try:
            summary_result = summary_agent(summary_prompt)
            summary_text = str(summary_result.message)
            # Parse JSON from response [R8-M4]
            start = summary_text.find("```json")
            end = summary_text.find("```", start + 7) if start != -1 else -1
            if start != -1 and end != -1:
                json_str = summary_text[start + 7 : end].strip()
                summary = json.loads(json_str)
            else:
                raise ValueError("No JSON block found in summary response")
        except Exception as exc:
            logger.warning("Failed to parse LLM summary: %s", exc)
            summary = {
                "run_id": run_id,
                "final_score": final_score,
                "total_crises": total_crises_seen,
                "crises_resolved": total_crises_seen,
                "avg_daily_kcal": 0.0,
                "key_learnings": ["Parse error — manual review needed"],
                "worst_decision": "N/A",
                "best_decision": "N/A",
            }

        cross_session.save_summary(summary)

        return {
            "run_id": run_id,
            "final_score": final_score,
            "mission_phase": last_phase,
            "total_crises": total_crises_seen,
            "summary": summary,
        }
