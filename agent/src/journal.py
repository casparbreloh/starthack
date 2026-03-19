"""Decision journal with feedback loop and cross-session learning.

Provides:
  - compact_state_summary(): Converts full telemetry state to a one-line string
  - DecisionJournal: In-memory store of per-sol decisions with outcomes
  - CrossSessionLearning: Reads/writes end-of-run summaries for future runs
"""

from __future__ import annotations

import json
import logging
from pathlib import Path

from .config import SESSION_LOGS_DIR

logger = logging.getLogger(__name__)


def compact_state_summary(state: dict) -> str:
    """Convert full telemetry state dict to a compact one-line summary string.

    Used for journal state_snapshot field and LLM context injection.

    Args:
        state: The dict returned by SimClient.read_all_telemetry()

    Returns:
        Compact string like:
        "bat=85% water=450L temp=21C crops=12 score=72.3 food=45.2d nutr=85% crises=0"
    """
    try:
        battery_pct = state["energy_status"].get("battery_pct", 0)
    except (KeyError, TypeError):
        battery_pct = 0

    try:
        reservoir_liters = state["water_status"].get("reservoir_liters", 0)
    except (KeyError, TypeError):
        reservoir_liters = 0

    try:
        # [R9-C1] greenhouse_environment returns {"zones": [...], ...}
        # zone field is "temp_c" NOT "current_temp_c"
        zones = state["greenhouse_environment"]["zones"]
        avg_temp = sum(z["temp_c"] for z in zones) / len(zones) if zones else 0
    except (KeyError, TypeError, ZeroDivisionError):
        avg_temp = 0

    try:
        # [R9-C3] crops_status returns {"crops": [...], ...}
        crop_count = len(state["crops_status"]["crops"])
    except (KeyError, TypeError):
        crop_count = 0

    try:
        overall_score = state["score_current"]["scores"]["overall_score"]
    except (KeyError, TypeError):
        overall_score = 0.0

    try:
        # [R9-C4] crew_nutrition has days_of_food_remaining
        food_days = state["crew_nutrition"]["days_of_food_remaining"]
    except (KeyError, TypeError):
        food_days = 0.0

    try:
        # [R10-M1] nutrient stock percentage
        nutrient_pct = state["nutrients_status"]["nutrient_stock_remaining_pct"]
    except (KeyError, TypeError):
        nutrient_pct = 0

    try:
        # [R7-H2] active_crises returns {"crises": [...]}
        crisis_count = len(state["active_crises"].get("crises", []))
    except (KeyError, TypeError):
        crisis_count = 0

    return (
        f"bat={battery_pct:.0f}% "
        f"water={reservoir_liters:.0f}L "
        f"temp={avg_temp:.0f}C "
        f"crops={crop_count} "
        f"score={overall_score:.1f} "
        f"food={food_days:.1f}d "
        f"nutr={nutrient_pct:.0f}% "
        f"crises={crisis_count}"
    )


class DecisionJournal:
    """In-memory journal of per-sol decisions with outcomes.

    Provides a feedback loop: the last N sols of decisions (including their
    outcomes from the following sol) are injected into each LLM prompt.
    """

    def __init__(self) -> None:
        self.entries: list[dict] = []

    def record_decision(
        self,
        sol: int,
        reasoning: str,
        actions: list[str],
        state_snapshot: str,
    ) -> None:
        """Record the decision made on a given sol.

        Args:
            sol: The sol number when the decision was made
            reasoning: LLM's reasoning summary for this sol
            actions: List of action strings, e.g.:
                     ["set_irrigation zone_A 5.0 L/sol", "plant potato zone_C 6m2"]
                     [R5-H6] These are extracted from the LLM's tool call history.
            state_snapshot: Compact state summary from compact_state_summary()
                            [R5-SC2] NOT the full telemetry dict.
        """
        self.entries.append(
            {
                "sol": sol,
                "reasoning": reasoning,
                "actions": actions,
                "state_snapshot": state_snapshot,
                "outcome_next_sol": None,
            }
        )

    def update_previous_outcome(self, outcome: dict) -> None:
        """Update the most recent entry with the outcome observed the following sol.

        Args:
            outcome: Dict with keys:
                     - score_delta: float — change in overall score since last sol
                     - state_summary: str — compact state from compact_state_summary()
        """
        if self.entries:
            self.entries[-1]["outcome_next_sol"] = outcome

    def last_n(self, n: int = 30) -> list[dict]:
        """Return the last N journal entries.

        Args:
            n: Number of entries to return (default 30)

        Returns:
            List of entry dicts, most recent last.
        """
        return self.entries[-n:] if len(self.entries) > n else list(self.entries)

    def format_for_prompt(self, n: int = 30) -> str:
        """Format the last N entries as a compact string for LLM context injection.

        Args:
            n: Number of entries to include (default 30)

        Returns:
            Multi-line string with sol, reasoning, actions, state, and outcome.
            Returns empty string if no entries.
        """
        entries = self.last_n(n)
        if not entries:
            return ""

        lines = [f"## Decision Journal (last {len(entries)} sols)\n"]
        for entry in entries:
            reasoning_short = (entry["reasoning"] or "")[:200]
            if len(entry["reasoning"] or "") > 200:
                reasoning_short += "..."

            actions_str = ", ".join(entry["actions"][:5])
            if len(entry["actions"]) > 5:
                actions_str += f" (+{len(entry['actions']) - 5} more)"

            outcome_str = "pending"
            if entry["outcome_next_sol"] is not None:
                delta = entry["outcome_next_sol"].get("score_delta", 0)
                outcome_str = f"score_delta={delta:+.2f}"

            lines.append(
                f"Sol {entry['sol']}: {reasoning_short}\n"
                f"  Actions: {actions_str}\n"
                f"  State: {entry['state_snapshot']}\n"
                f"  Outcome: {outcome_str}\n"
            )
        return "\n".join(lines)


class CrossSessionLearning:
    """Reads and writes end-of-run summaries for cross-session learning.

    After each 450-sol run, the LLM generates a structured summary saved
    to session_logs/. On subsequent runs, previous summaries are injected
    into the orchestrator's system prompt so the agent learns over time.
    """

    def __init__(self, session_logs_dir: str = SESSION_LOGS_DIR) -> None:
        self.dir = Path(session_logs_dir)
        self.dir.mkdir(parents=True, exist_ok=True)

    def load_previous_summaries(self) -> list[dict]:
        """Load all previous run summaries from the session logs directory.

        Returns:
            List of summary dicts sorted by run_id (chronological order).
            Empty list if no previous runs exist.
        """
        summaries = []
        for json_file in self.dir.glob("*.json"):
            try:
                with open(json_file) as f:
                    summaries.append(json.load(f))
            except Exception as exc:
                logger.warning("Failed to load session log %s: %s", json_file, exc)

        return sorted(summaries, key=lambda s: s.get("run_id", ""))

    def save_summary(self, summary: dict) -> None:
        """Save a run summary to the session logs directory.

        Args:
            summary: Dict with keys: run_id, final_score, total_crises,
                     crises_resolved, avg_daily_kcal, key_learnings (list),
                     worst_decision (str), best_decision (str).
        """
        run_id = summary.get("run_id", "unknown")
        output_path = self.dir / f"{run_id}.json"
        try:
            with open(output_path, "w") as f:
                json.dump(summary, f, indent=2)
            logger.info("Saved run summary to %s", output_path)
        except Exception as exc:
            logger.error("Failed to save run summary: %s", exc)

    def format_for_prompt(self) -> str:
        """Format previous run summaries for system prompt injection.

        Loads at most the 5 most recent summaries (sorted by run_id descending).
        [R7-M5] Prevents unbounded growth of cross-session context.

        Returns:
            Multi-line string with summaries of up to 5 previous runs.
            Empty string if no previous runs.
        """
        all_summaries = self.load_previous_summaries()
        if not all_summaries:
            return ""

        # Take the 5 most recent (run_id sorts chronologically so reverse for recency)
        recent = all_summaries[-5:][::-1]

        lines = ["## Previous Run Summaries (most recent first)\n"]
        for summary in recent:
            run_id = summary.get("run_id", "unknown")
            final_score = summary.get("final_score", 0)
            key_learnings = summary.get("key_learnings", [])
            learnings_str = "; ".join(str(item) for item in key_learnings[:5])

            lines.append(
                f"Run {run_id}: score={final_score:.1f}\n"
                f"  Learnings: {learnings_str}\n"
                f"  Best: {summary.get('best_decision', 'N/A')}\n"
                f"  Worst: {summary.get('worst_decision', 'N/A')}\n"
            )

        return "\n".join(lines)
