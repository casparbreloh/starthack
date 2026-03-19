"""Orchestrator agent for the Mars greenhouse mission.

The orchestrator LLM reasons about EVERY decision EVERY sol:
environment, irrigation, energy, planting, harvesting, nutrients.
Specialist sub-agents handle crisis escalation with focused context.

Memory paths:
  - memory_enabled=True (BEDROCK_AGENTCORE_MEMORY_ID set): single persistent Agent
    with AgentCoreMemorySessionManager + strategic_memory tool
  - memory_enabled=False (local dev, no env var): per-sol fresh Agent +
    CrossSessionLearning file-based (legacy path)
"""

from __future__ import annotations

import json
import logging
import re
import time
from datetime import datetime
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from bedrock_agentcore.memory.integrations.strands.session_manager import (
        AgentCoreMemorySessionManager,
    )

from strands import Agent
from strands.models.bedrock import BedrockModel

from ..config import (
    AGENT_TEMPERATURE,
    AGENTCORE_GATEWAY_URL,
    MISSION_SOLS,
    MODEL_ID,
)
from ..energy_projection import project_energy_budget, summarize_energy_projection
from ..journal import CrossSessionLearning, DecisionJournal, compact_state_summary
from ..mcp_client import create_mcp_client, discover_kb_tools
from ..prompts import MEMORY_PROMPT_SECTION, ORCHESTRATOR_SYSTEM_PROMPT
from ..tools.actions import bind_action_accumulator, create_action_tools
from ..tools.telemetry import create_telemetry_tools
from ..weather_integration import WeatherForecaster
from .climate_emergency import climate_emergency_agent
from .energy_crisis import energy_crisis_agent
from .nutrition_planner import nutrition_planner_agent
from .pathogen_response import pathogen_response_agent
from .storm_preparation import storm_preparation_agent
from .triage import triage_agent
from .water_crisis import water_crisis_agent

logger = logging.getLogger(__name__)

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


def _collect_text_fragments(value: Any) -> list[str]:
    """Recursively collect string fragments from a model result payload."""
    if value is None:
        return []
    if isinstance(value, str):
        text = value.strip()
        return [text] if text else []
    if isinstance(value, dict):
        fragments: list[str] = []
        for item in value.values():
            fragments.extend(_collect_text_fragments(item))
        return fragments
    if isinstance(value, list):
        fragments: list[str] = []
        for item in value:
            fragments.extend(_collect_text_fragments(item))
        return fragments
    return []


def create_orchestrator(
    snapshot: dict[str, Any],
    cross_session_context: str = "",
    kb_tools: list | None = None,
    session_manager: AgentCoreMemorySessionManager | None = None,
    extra_tools: list | None = None,
    action_accumulator: list[dict] | None = None,
) -> Agent:
    """Create an orchestrator Agent with tools reading from a snapshot.

    Args:
        snapshot: Consultation snapshot dict — telemetry tools read from this.
        cross_session_context: Previous run summaries for prompt injection.
        kb_tools: MCP KB tool objects from AgentCore gateway.
        session_manager: AgentCoreMemorySessionManager for context management.
        extra_tools: Additional @tool functions to include.
        action_accumulator: Mutable list that action tools append to when called.

    Returns:
        Agent instance ready for a single consultation.
    """
    n_kb = len(kb_tools or [])
    logger.info("Creating orchestrator with %d KB tools", n_kb)
    if n_kb == 0 and AGENTCORE_GATEWAY_URL:
        logger.warning(
            "No KB tools available — orchestrator running without Syngenta KB."
        )

    system_prompt = ORCHESTRATOR_SYSTEM_PROMPT
    if cross_session_context:
        system_prompt = (
            system_prompt + "\n\n## Previous Run Learnings\n" + cross_session_context
        )
    if session_manager is not None:
        system_prompt = system_prompt + "\n\n" + MEMORY_PROMPT_SECTION

    telemetry_tools = create_telemetry_tools(snapshot)
    action_tools = create_action_tools(action_accumulator=action_accumulator)

    tools = [
        telemetry_tools["read_all_telemetry"],
        telemetry_tools["get_crop_catalog"],
        *action_tools.values(),
        *SPECIALIST_TOOLS,
        *(kb_tools or []),
        *(extra_tools or []),
    ]

    model = BedrockModel(model_id=MODEL_ID, temperature=AGENT_TEMPERATURE)

    if session_manager is not None:
        return Agent(
            model=model,
            system_prompt=system_prompt,
            tools=tools,
            session_manager=session_manager,
        )
    return Agent(
        model=model,
        system_prompt=system_prompt,
        tools=tools,
    )


def _dedup_actions(actions: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Deduplicate actions, keeping the last call per endpoint+key.

    When the LLM (or a specialist sub-agent) calls the same tool twice for the
    same target (e.g. set_environment zone B), only the final call should take
    effect.  The dedup key is (endpoint, zone_id or crop_id) so that different
    zones are preserved but repeated calls to the same zone collapse.
    """
    seen: dict[str, int] = {}
    for idx, act in enumerate(actions):
        endpoint = act.get("endpoint", "")
        body = act.get("body", {})
        # Build a key from the endpoint + the most common discriminator
        key_parts = [endpoint]
        for field in ("zone_id", "crop_id"):
            if field in body:
                key_parts.append(f"{field}={body[field]}")
        key = "|".join(key_parts)
        seen[key] = idx  # last write wins

    return [actions[i] for i in sorted(seen.values())]


def _extract_key_stats(snapshot: dict[str, Any]) -> str:
    """Extract a one-line summary from a state snapshot."""
    energy = snapshot.get("energy_status", {})
    water = snapshot.get("water_status", {})
    score = snapshot.get("score_current", {}).get("scores", {})
    crops = snapshot.get("crops_status", {})
    crew = snapshot.get("crew_nutrition", {})
    crises = snapshot.get("active_crises", {})
    n_crops = len(crops.get("crops", [])) if isinstance(crops, dict) else 0
    n_crises = len(crises.get("crises", [])) if isinstance(crises, dict) else 0
    return (
        f"bat={energy.get('battery_pct', '?')}%, "
        f"water={water.get('reservoir_liters', '?')}L, "
        f"crops={n_crops}, score={score.get('overall_score', '?')}, "
        f"food={crew.get('days_of_food_remaining', '?')}d, "
        f"crises={n_crises}"
    )


def _build_consultation_prompt(
    consultation: dict[str, Any],
    weather_context: dict,
    energy_summary: str,
    journal: DecisionJournal,
) -> str:
    """Build the LLM prompt from a WebSocket consultation payload.

    The consultation payload contains: sol, interrupts, snapshot.
    The snapshot has the same structure as read_all_telemetry().
    """
    sol = consultation.get("sol", 0)
    snapshot = consultation.get("snapshot", {})
    interrupts = consultation.get("interrupts", [])

    prompt_parts = [
        f"## Sol {sol} — Greenhouse Status (WebSocket Consultation)\n",
        "### Current Telemetry\n",
        f"Use `read_all_telemetry()` to get all current data. "
        f"Or use the pre-fetched snapshot summary: {_extract_key_stats(snapshot)}\n",
    ]

    if interrupts:
        prompt_parts.append(
            f"\n### Interrupts Triggering This Consultation\n"
            f"{json.dumps(interrupts, indent=2)}\n"
        )

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
        "\n### Your Tasks This Consultation\n"
        "1. Call `read_all_telemetry()` to get full current state\n"
        "2. Make ALL routine decisions: environment setpoints, irrigation, "
        "energy allocation, planting (check free area), harvesting (check is_ready), "
        "nutrient adjustments\n"
        "3. Check weather for dust_opacity > 1.0 → call storm_preparation_agent if detected\n"
        "4. Provide a BRIEF reasoning summary (3-5 sentences, plain text, no markdown)\n"
        "5. Set next_checkin: N where N is sols until next check-in.\n"
        "   IMPORTANT: Use high values to avoid unnecessary consultations:\n"
        "   - Stable, no crises: next_checkin: 7-10\n"
        "   - Minor issues (low nutrients, mild stress): next_checkin: 3-5\n"
        "   - Active crisis, situation CHANGING: next_checkin: 1-2\n"
        "   - Active crisis, situation STABLE/UNRESOLVABLE (e.g. battery stuck at 0% "
        "with solar surplus): next_checkin: 3-5 (you cannot fix it by checking more often)\n"
    )

    return "".join(prompt_parts)


def run_consultation(
    consultation: dict[str, Any],
    weather_forecaster: WeatherForecaster,
    journal: DecisionJournal,
    cross_session_context: str = "",
    kb_tools: list | None = None,
) -> tuple[list[dict[str, Any]], int, str]:
    """Process a single WebSocket consultation and return actions.

    Creates a fresh orchestrator, builds a prompt from the consultation
    payload, runs the LLM, and extracts actions + next_checkin.

    Args:
        consultation: Consultation payload from the server with keys:
                      sol, interrupts, snapshot.
        weather_forecaster: WeatherForecaster for LSTM forecasts.
        journal: DecisionJournal for feedback loop.
        cross_session_context: Previous run summaries for prompt injection.
        kb_tools: MCP KB tool objects.

    Returns:
        Tuple of (actions_list, next_checkin, reasoning) where:
        - actions_list: list of ``{"endpoint": "...", "body": {...}}`` dicts
        - next_checkin: number of sols until next consultation (1-10)
        - reasoning: LLM reasoning text
    """
    sol = consultation.get("sol", 0)
    snapshot = consultation.get("snapshot", {})

    # Weather history is included in the consultation snapshot
    weather_history = snapshot.get("weather_history", [])

    weather_context = weather_forecaster.get_full_context(
        sol,
        weather_history=weather_history,
        current_weather=snapshot.get("weather_current"),
    )
    energy_projection = project_energy_budget(
        weather_context["forecast_7sol"],
        snapshot.get("energy_status", {}),
        snapshot.get("weather_current", {}),
    )
    energy_summary = summarize_energy_projection(energy_projection)

    # Build prompt
    prompt = _build_consultation_prompt(
        consultation, weather_context, energy_summary, journal
    )

    # Create fresh orchestrator with consultation snapshot.
    # The action accumulator collects actions as tools are called by the LLM.
    action_accumulator: list[dict[str, Any]] = []
    orchestrator = create_orchestrator(
        snapshot,
        cross_session_context,
        kb_tools,
        action_accumulator=action_accumulator,
    )

    # Run LLM with retry
    result = None
    try:
        with bind_action_accumulator(action_accumulator):
            result = orchestrator(prompt)
    except Exception as exc:
        logger.warning(
            "Sol %d: orchestrator call failed (%s), retrying in 5s...", sol, exc
        )
        time.sleep(5)
        try:
            with bind_action_accumulator(action_accumulator):
                result = orchestrator(prompt)
        except Exception as exc2:
            logger.warning(
                "Sol %d: orchestrator retry also failed (%s). Skipping.",
                sol,
                exc2,
            )

    # Actions are collected via the accumulator as tools execute
    actions_list = action_accumulator
    reasoning = ""
    next_checkin = 1

    if result is not None:
        message = getattr(result, "message", result)
        candidate_fragments = _collect_text_fragments(message)

        # Keep string fallbacks too; some SDK responses stringify useful text
        # even when the structured payload is sparse.
        for fallback in (str(message), str(result)):
            text = fallback.strip()
            if text:
                candidate_fragments.append(text)

        deduped_fragments: list[str] = []
        for fragment in candidate_fragments:
            if fragment not in deduped_fragments:
                deduped_fragments.append(fragment)

        reasoning = "\n".join(deduped_fragments)

        # Extract next_checkin from any recovered model text. Accept minor
        # formatting variations like markdown emphasis or `next checkin`.
        checkin_match = re.search(
            r"next[_ ]?checkin\s*[:=]\s*\**\s*(\d+)",
            reasoning,
            re.IGNORECASE,
        )
        if checkin_match:
            parsed_checkin = int(checkin_match.group(1))
            next_checkin = max(1, min(10, parsed_checkin))
        else:
            logger.warning(
                "Sol %d: failed to parse next_checkin from model output; defaulting to 1",
                sol,
            )

    # Record in journal
    action_strs = [f"{a['endpoint']}({json.dumps(a['body'])})" for a in actions_list]
    journal.record_decision(
        sol, reasoning[:500], action_strs, compact_state_summary(snapshot)
    )

    return actions_list, next_checkin, reasoning


async def _consultation_loop(
    ws_client: Any,
    kb_tools: list,
    cross_session_context: str,
) -> tuple[dict[str, Any], int, DecisionJournal]:
    """Shared consultation loop for both run_mission and join_mission.

    Receives consultations, runs the LLM, and sends actions back.

    Returns:
        Tuple of (last_snapshot, total_crises_seen, journal).
    """
    weather_forecaster = WeatherForecaster()
    journal = DecisionJournal()
    prev_score: float | None = None
    last_snapshot: dict[str, Any] = {}
    total_crises_seen = 0

    while True:
        consultation = await ws_client.wait_for_consultation()
        if consultation is None:
            logger.info("Mission ended (WS signal)")
            break

        sol = consultation.get("sol", 0)
        logger.info("=== Sol %d (WS consultation) ===", sol)

        snapshot = consultation.get("snapshot", {})
        last_snapshot = snapshot
        current_score = (
            snapshot.get("score_current", {})
            .get("scores", {})
            .get("overall_score", 0.0)
        )
        if prev_score is not None:
            score_delta = current_score - prev_score
            journal.update_previous_outcome(
                {
                    "score_delta": score_delta,
                    "state_summary": compact_state_summary(snapshot),
                }
            )
        prev_score = current_score

        interrupts = consultation.get("interrupts", [])
        crisis_interrupts = [i for i in interrupts if i.get("type") == "new_crisis"]
        total_crises_seen += len(crisis_interrupts)

        import asyncio as _asyncio

        actions, next_checkin, reasoning = await _asyncio.to_thread(
            run_consultation,
            consultation,
            weather_forecaster,
            journal,
            cross_session_context,
            kb_tools,
        )

        # Deduplicate actions (last call per endpoint+target wins)
        raw_count = len(actions)
        actions = _dedup_actions(actions)
        if len(actions) < raw_count:
            logger.info(
                "Sol %d: deduped %d → %d actions",
                sol,
                raw_count,
                len(actions),
            )

        # Log reasoning and actions for observability
        _stats = _extract_key_stats(snapshot)
        logger.info("Sol %d state: %s", sol, _stats)
        if reasoning:
            logger.info("Sol %d reasoning: %s", sol, reasoning[:500])
        for act in actions:
            logger.info(
                "Sol %d action: %s %s",
                sol,
                act.get("endpoint", "?"),
                json.dumps(act.get("body", {})),
            )

        log_decision = {
            "reasoning": reasoning[:500] if reasoning else "nominal",
            "risk_assessment": reasoning[:200] if reasoning else "nominal",
        }
        await ws_client.send_actions(actions, next_checkin, log_decision)

        logger.info(
            "Sol %d: sent %d actions, next_checkin=%d",
            sol,
            len(actions),
            next_checkin,
        )

    return last_snapshot, total_crises_seen, journal


def _generate_mission_summary(
    run_id: str,
    final_score: float,
    total_crises_seen: int,
    cross_session: CrossSessionLearning,
    journal_prompt: str,
) -> dict:
    """Generate and save a cross-session mission summary."""
    summary_agent = create_orchestrator({})
    summary_prompt = (
        "Generate a structured mission summary as JSON in a ```json code block.\n\n"
        f"Run ID: {run_id}\n"
        f"Final score: {final_score}\n"
        f"Total crises handled: {total_crises_seen}\n\n"
        f"Journal (last 50 sols):\n{journal_prompt}\n\n"
        "Return JSON with exactly these keys:\n"
        '{"run_id": "...", "final_score": 0.0, "total_crises": 0, '
        '"crises_resolved": 0, "avg_daily_kcal": 0.0, '
        '"key_learnings": ["..."], "worst_decision": "...", "best_decision": "..."}\n'
    )
    try:
        summary_result = summary_agent(summary_prompt)
        summary_text = str(summary_result.message)
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
    return summary


async def run_mission(
    ws_url: str,
    seed: int = 0,
    difficulty: str = "normal",
    mission_sols: int = MISSION_SOLS,
) -> dict:
    """Run the full Mars greenhouse mission over a WebSocket connection.

    Connects to the simulation's /ws endpoint, creates a new session,
    and runs the consultation loop until the mission ends.

    Args:
        ws_url: WebSocket URL, e.g. ``ws://localhost:8080/ws``
        seed: Random seed for simulation
        difficulty: Difficulty level ('easy', 'normal', 'hard')
        mission_sols: Max number of sols (used for session config)

    Returns:
        Mission summary dict with final score and stats.
    """
    from ..ws_client import SimWebSocketClient

    cross_session = CrossSessionLearning()
    cross_session_context = cross_session.format_for_prompt()

    mcp_client = create_mcp_client()
    with mcp_client:
        kb_tools = discover_kb_tools(mcp_client)
        logger.info("KB tools discovered: %d", len(kb_tools))

        run_id = datetime.utcnow().strftime("%Y%m%d_%H%M%S")

        async with SimWebSocketClient() as ws_client:
            await ws_client.connect(ws_url)

            session_config: dict[str, Any] = {
                "seed": seed,
                "difficulty": difficulty,
                "tick_delay_ms": 0,
                "mission_sols": mission_sols,
                "paused": False,
            }
            session_id = await ws_client.create_session(session_config)
            logger.info(
                "WS session created: id=%s, seed=%d, difficulty=%s",
                session_id,
                seed,
                difficulty,
            )

            last_snapshot, total_crises_seen, journal = await _consultation_loop(
                ws_client, kb_tools, cross_session_context
            )

        mission_end_payload = ws_client.mission_end_payload or {}
        final_snapshot = mission_end_payload.get("snapshot", last_snapshot)
        mission_phase = mission_end_payload.get("mission_phase", "complete")

        final_score = (
            final_snapshot.get("score_current", {})
            .get("scores", {})
            .get("overall_score", 0.0)
        )
        logger.info("Final score: %.2f", final_score)

        summary = _generate_mission_summary(
            run_id,
            final_score,
            total_crises_seen,
            cross_session,
            journal.format_for_prompt(50),
        )

        return {
            "run_id": run_id,
            "final_score": final_score,
            "mission_phase": mission_phase,
            "total_crises": total_crises_seen,
            "summary": summary,
        }


async def join_mission(
    ws_url: str,
    session_id: str,
) -> dict:
    """Join an existing simulation session and run the consultation loop.

    Instead of creating a new session, connects to a session that was
    already created (e.g. by the frontend or simulation auto-invoke).

    Args:
        ws_url: WebSocket URL, e.g. ``ws://localhost:8080/ws``
        session_id: The session ID to join.

    Returns:
        Mission summary dict with final score and stats.
    """
    from ..ws_client import SimWebSocketClient

    cross_session = CrossSessionLearning()
    cross_session_context = cross_session.format_for_prompt()

    mcp_client = create_mcp_client()
    with mcp_client:
        kb_tools = discover_kb_tools(mcp_client)
        logger.info("KB tools discovered: %d", len(kb_tools))

        run_id = datetime.utcnow().strftime("%Y%m%d_%H%M%S")

        async with SimWebSocketClient() as ws_client:
            await ws_client.connect(ws_url)
            confirmed_id = await ws_client.join_session(session_id)
            logger.info("Joined session: %s", confirmed_id)

            last_snapshot, total_crises_seen, journal = await _consultation_loop(
                ws_client, kb_tools, cross_session_context
            )

        mission_end_payload = ws_client.mission_end_payload or {}
        final_snapshot = mission_end_payload.get("snapshot", last_snapshot)
        mission_phase = mission_end_payload.get("mission_phase", "complete")

        final_score = (
            final_snapshot.get("score_current", {})
            .get("scores", {})
            .get("overall_score", 0.0)
        )
        logger.info("Final score: %.2f", final_score)

        summary = _generate_mission_summary(
            run_id,
            final_score,
            total_crises_seen,
            cross_session,
            journal.format_for_prompt(50),
        )

        return {
            "run_id": run_id,
            "final_score": final_score,
            "mission_phase": mission_phase,
            "total_crises": total_crises_seen,
            "summary": summary,
        }


def _record_mission_summary_to_memory(
    memory_client: object,
    memory_id: str,
    actor_id: str,
    session_id: str,
    run_id: str,
    final_score: float,
    total_crises: int,
    journal: DecisionJournal,
) -> None:
    """Record end-of-mission summary to AgentCore Memory for future retrieval.

    Args:
        memory_client: MemoryClient instance.
        memory_id: AgentCore memory resource ID.
        actor_id: Actor ID.
        session_id: Session ID (same as run_id).
        run_id: Unique run identifier.
        final_score: Final overall score (0-100).
        total_crises: Total crises handled during mission.
        journal: DecisionJournal with sol-by-sol records.
    """
    from ..memory import (
        MemoryClient as _MemoryClient,  # noqa: F401 (type reference only)
    )

    summary_content = (
        f"[END-OF-MISSION SUMMARY run={run_id}] "
        f"final_score={final_score:.1f} total_crises={total_crises}. "
        f"Journal highlights: {journal.format_for_prompt(5)[:500]}"
    )
    try:
        memory_client.create_event(  # type: ignore[attr-defined]
            memory_id=memory_id,
            actor_id=actor_id,
            session_id=session_id,
            messages=[("user", summary_content)],
        )
        logger.info("Mission summary recorded to AgentCore Memory for run %s", run_id)
    except Exception as exc:
        logger.warning("Failed to record mission summary to memory: %s", exc)
