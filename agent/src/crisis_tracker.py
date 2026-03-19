"""Crisis outcome tracker for the Mars Greenhouse Agent.

Tracks crisis responses over 5/15/50-sol observation windows, detects
secondary crises, synthesizes learnings via LLM, and persists them to
AgentCore Memory for cross-session improvement.

Follows the same patterns as DecisionJournal in journal.py.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Literal, TypedDict

from strands import Agent
from strands.models.bedrock import BedrockModel

from .config import MODEL_ID
from .journal import compact_state_summary

if TYPE_CHECKING:
    pass

logger = logging.getLogger(__name__)


# --------------------------------------------------------------------------- #
# TypedDicts                                                                   #
# --------------------------------------------------------------------------- #


class MemoryContext(TypedDict):
    memory_client: object
    memory_id: str
    actor_id: str
    session_id: str


# --------------------------------------------------------------------------- #
# Dataclasses                                                                  #
# --------------------------------------------------------------------------- #


@dataclass
class ObservationSnapshot:
    """State snapshot captured at a single observation window."""

    sol: int
    state_summary: str
    score: float
    score_delta: float
    active_crisis_ids: set[str] = field(default_factory=set)
    new_crisis_ids_since_detection: set[str] = field(default_factory=set)


@dataclass
class CrisisRecord:
    """Full record of a single crisis and its long-term outcome tracking."""

    crisis_id: str
    crisis_type: str
    sol_detected: int
    severity: str
    pre_crisis_snapshot: str
    pre_crisis_score: float
    pre_crisis_ids: set[str] = field(default_factory=set)
    response_actions: list[str] = field(default_factory=list)
    specialist_output: str = ""
    observation_windows: dict[int, ObservationSnapshot | None] = field(
        default_factory=dict
    )
    synthesized_learning: str | None = None
    status: Literal["active", "pending", "completed"] = "active"


# --------------------------------------------------------------------------- #
# Tracker class                                                                #
# --------------------------------------------------------------------------- #


class CrisisOutcomeTracker:
    """Tracks crisis outcomes over 5/15/50-sol observation windows.

    Lifecycle:
      - record_crisis(): capture at detection time → status="active"
      - check_observation_windows(): fill snapshots each sol → auto-transitions
        to status="pending" when all 3 windows filled
      - process_synthesis_batch(): synthesize + persist pending records →
        status="completed", moved to completed_records
      - force_close_pending(): mission-end cleanup — fills any remaining None
        windows with current state and marks all as pending
    """

    def __init__(self) -> None:
        self.active_records: list[CrisisRecord] = []
        self.completed_records: list[CrisisRecord] = []

    def record_crisis(
        self,
        crisis_id: str,
        crisis_type: str,
        severity: str,
        sol: int,
        pre_crisis_snapshot: str,
        pre_crisis_score: float,
        pre_crisis_ids: set[str],
        response_actions: list[str],
        specialist_output: str,
    ) -> CrisisRecord:
        """Record a newly detected crisis for outcome tracking.

        Registers the crisis with observation windows at sol+5, sol+15, sol+50.

        Args:
            crisis_id: Unique identifier from the simulation.
            crisis_type: Crisis category (e.g. "water_shortage").
            severity: Crisis severity string (e.g. "high").
            sol: Sol number at detection.
            pre_crisis_snapshot: Compact state summary from compact_state_summary().
            pre_crisis_score: Overall score float at detection time.
            pre_crisis_ids: Set of active crisis IDs at detection — used for
                secondary crisis detection at observation windows.
            response_actions: List of action strings taken by the specialist.
            specialist_output: Truncated specialist agent response text.

        Returns:
            The created CrisisRecord.
        """
        windows: dict[int, ObservationSnapshot | None] = {
            sol + 5: None,
            sol + 15: None,
            sol + 50: None,
        }
        record = CrisisRecord(
            crisis_id=crisis_id,
            crisis_type=crisis_type,
            sol_detected=sol,
            severity=severity,
            pre_crisis_snapshot=pre_crisis_snapshot,
            pre_crisis_score=pre_crisis_score,
            pre_crisis_ids=set(pre_crisis_ids),
            response_actions=list(response_actions),
            specialist_output=specialist_output,
            observation_windows=windows,
        )
        self.active_records.append(record)
        logger.info(
            "Tracking crisis %s (%s) at sol %d, windows at %s",
            crisis_id,
            crisis_type,
            sol,
            list(windows.keys()),
        )
        return record

    def check_observation_windows(
        self, current_sol: int, current_state: dict
    ) -> list[CrisisRecord]:
        """Check all active records for observation windows matching current_sol.

        Captures state snapshots at each matching window. No LLM calls —
        pure data capture. Transitions records to "pending" when all 3 windows
        are filled.

        Args:
            current_sol: The current mission sol number.
            current_state: Full dict from client.read_all_telemetry() (14 keys).

        Returns:
            List of CrisisRecords that had at least one window filled this sol.
        """
        updated: list[CrisisRecord] = []

        for record in self.active_records:
            if record.status != "active":
                continue

            if current_sol not in record.observation_windows:
                continue

            if record.observation_windows[current_sol] is not None:
                continue

            # Fill this window
            score = float(current_state["score_current"]["scores"]["overall_score"])
            current_ids = {
                c["id"]
                for c in current_state.get("active_crises", {}).get("crises", [])
            }
            new_crisis_ids = current_ids - record.pre_crisis_ids

            snapshot = ObservationSnapshot(
                sol=current_sol,
                state_summary=compact_state_summary(current_state),
                score=score,
                score_delta=score - record.pre_crisis_score,
                active_crisis_ids=current_ids,
                new_crisis_ids_since_detection=new_crisis_ids,
            )
            record.observation_windows[current_sol] = snapshot
            updated.append(record)

            # Transition to pending if all windows are now filled
            if all(v is not None for v in record.observation_windows.values()):
                record.status = "pending"
                logger.debug(
                    "Crisis %s all windows filled, transitioning to pending",
                    record.crisis_id,
                )

        return updated

    def get_pending_records(self) -> list[CrisisRecord]:
        """Return all active records with status='pending' awaiting synthesis.

        Returns:
            List of CrisisRecord instances ready for LLM synthesis.
        """
        return [r for r in self.active_records if r.status == "pending"]

    def force_close_pending(self, current_sol: int, current_state: dict) -> int:
        """Force-close all active records at mission end.

        Fills any unfilled observation windows with a snapshot from current_state,
        then marks all active records as "pending" so they can be synthesized.

        Args:
            current_sol: The final mission sol number.
            current_state: Full telemetry dict from client.read_all_telemetry().

        Returns:
            Count of records force-closed (all active records regardless of status).
        """
        score = float(current_state["score_current"]["scores"]["overall_score"])
        current_ids = {
            c["id"] for c in current_state.get("active_crises", {}).get("crises", [])
        }

        count = 0
        for record in self.active_records:
            if record.status == "completed":
                continue

            # Fill any None windows
            for window_sol in list(record.observation_windows.keys()):
                if record.observation_windows[window_sol] is None:
                    new_crisis_ids = current_ids - record.pre_crisis_ids
                    snapshot = ObservationSnapshot(
                        sol=current_sol,
                        state_summary=compact_state_summary(current_state),
                        score=score,
                        score_delta=score - record.pre_crisis_score,
                        active_crisis_ids=current_ids,
                        new_crisis_ids_since_detection=new_crisis_ids,
                    )
                    record.observation_windows[window_sol] = snapshot

            record.status = "pending"
            count += 1

        logger.info(
            "Force-closed %d pending crisis records at sol %d", count, current_sol
        )
        return count

    def process_synthesis_batch(
        self,
        memory_context: MemoryContext | None = None,
        max_per_sol: int = 2,
    ) -> list[str]:
        """Synthesize learnings for pending records, up to max_per_sol per call.

        For each pending record: calls synthesize_learning(), optionally persists
        to AgentCore Memory via persist_learning(), then marks completed.
        Unprocessed pending records remain for the next call.

        Args:
            memory_context: MemoryContext dict for AgentCore Memory persistence.
                If None, synthesis runs but learnings are kept in-memory only.
            max_per_sol: Maximum number of records to synthesize per call (rate limit).

        Returns:
            List of synthesized learning strings (one per record processed).
        """
        pending = self.get_pending_records()
        to_process = pending[:max_per_sol]
        learnings: list[str] = []

        for record in to_process:
            learning = synthesize_learning(record)
            record.synthesized_learning = learning

            if memory_context is not None:
                persist_learning(
                    memory_client=memory_context["memory_client"],
                    memory_id=memory_context["memory_id"],
                    actor_id=memory_context["actor_id"],
                    session_id=memory_context["session_id"],
                    record=record,
                )

            record.status = "completed"
            self.active_records.remove(record)
            self.completed_records.append(record)
            learnings.append(learning)

        return learnings


# --------------------------------------------------------------------------- #
# Standalone synthesis / persistence / retrieval functions                     #
# --------------------------------------------------------------------------- #


def synthesize_learning(record: CrisisRecord) -> str:
    """Synthesize a strategic learning from a completed crisis record.

    Uses a focused LLM call (no tools) to produce a 2-3 sentence strategic
    learning. Falls back to a rule-based string on any exception.

    Args:
        record: A CrisisRecord with all observation windows filled.

    Returns:
        A string containing the synthesized learning.
    """
    try:
        # Build observation window lines
        window_labels = ["immediate", "short-term", "long-term"]
        window_lines = []
        for idx, (window_sol, snapshot) in enumerate(
            sorted(record.observation_windows.items())
        ):
            if snapshot is not None:
                label = window_labels[idx] if idx < len(window_labels) else "follow-up"
                window_lines.append(
                    f"- Sol {window_sol} ({label}): "
                    f"score_delta={snapshot.score_delta:+.1f}, "
                    f"state={snapshot.state_summary}, "
                    f"new_crises={snapshot.new_crisis_ids_since_detection}"
                )

        prompt = (
            "Analyze this crisis response and its long-term outcome. "
            "Produce a 2-3 sentence strategic learning.\n\n"
            f"Crisis: {record.crisis_type} (severity: {record.severity}) "
            f"at sol {record.sol_detected}\n"
            f"Pre-crisis state: {record.pre_crisis_snapshot}\n"
            f"Response actions: {record.response_actions}\n\n"
            "Observation windows:\n"
            + "\n".join(window_lines)
            + "\n\nWrite a concise strategic learning for future missions "
            "facing this crisis type."
        )

        synthesis_agent = Agent(
            model=BedrockModel(model_id=MODEL_ID, temperature=0.3),
            system_prompt=(
                "You are a mission analyst for a Mars greenhouse operation. "
                "Your job is to extract concise, actionable strategic learnings "
                "from crisis response data."
            ),
            tools=[],
        )
        synthesis_result = synthesis_agent(prompt)

        # Extract text from result.message
        msg = synthesis_result.message
        if isinstance(msg, dict):
            content = msg.get("content", [])
            texts = []
            for block in content:
                if isinstance(block, dict) and block.get("type") == "text":
                    texts.append(block.get("text", ""))
            return " ".join(texts).strip() or str(msg)
        return str(msg).strip()

    except Exception as exc:
        logger.warning("synthesize_learning failed for %s: %s", record.crisis_id, exc)
        # Rule-based fallback
        windows_with_data = {
            sol: snap
            for sol, snap in record.observation_windows.items()
            if snap is not None
        }
        window_count = len(windows_with_data)
        all_secondary: set[str] = set()
        final_delta = 0.0
        if windows_with_data:
            last_snap = windows_with_data[max(windows_with_data.keys())]
            final_delta = last_snap.score_delta
            all_secondary = last_snap.new_crisis_ids_since_detection

        return (
            f"Crisis {record.crisis_type} at sol {record.sol_detected}: "
            f"score delta {final_delta:+.1f} after {window_count} observations. "
            f"{len(all_secondary)} secondary crises detected."
        )


def persist_learning(
    memory_client: object,
    memory_id: str,
    actor_id: str,
    session_id: str,
    record: CrisisRecord,
) -> None:
    """Persist a synthesized crisis learning to AgentCore Memory.

    No-op if record.synthesized_learning is None.

    Args:
        memory_client: MemoryClient instance (typed as object to avoid import).
        memory_id: AgentCore memory resource ID.
        actor_id: Actor ID (e.g. "mars-agent").
        session_id: Session/run ID string.
        record: CrisisRecord with synthesized_learning set.
    """
    if record.synthesized_learning is None:
        return

    tagged = (
        f"[CRISIS LEARNING — {record.crisis_type} sol {record.sol_detected}]\n"
        f"{record.synthesized_learning}"
    )
    try:
        memory_client.create_event(  # type: ignore[attr-defined]
            memory_id=memory_id,
            actor_id=actor_id,
            session_id=session_id,
            messages=[("user", tagged)],
        )
        logger.info(
            "Persisted crisis learning for %s (sol %d) to memory",
            record.crisis_type,
            record.sol_detected,
        )
    except Exception as exc:
        logger.warning(
            "Failed to persist crisis learning for %s: %s", record.crisis_id, exc
        )


def retrieve_crisis_learnings(
    memory_client: object,
    memory_id: str,
    actor_id: str,
    crisis_types: list[str],
) -> str:
    """Retrieve past crisis learnings from AgentCore Memory via a single query.

    Uses a combined query across all crisis types to minimize API calls.

    Args:
        memory_client: MemoryClient instance (typed as object to avoid import).
        memory_id: AgentCore memory resource ID.
        actor_id: Actor ID for scoping retrieval.
        crisis_types: List of crisis type strings to retrieve learnings for.

    Returns:
        Formatted string with past learnings, or empty string if none found.
    """
    if not crisis_types:
        return ""

    combined_query = f"crisis response outcome learning {' '.join(set(crisis_types))}"
    try:
        results = memory_client.retrieve_memories(  # type: ignore[attr-defined]
            memory_id=memory_id,
            namespace="/",
            query=combined_query,
            actor_id=actor_id,
            top_k=5,
        )
        texts: list[str] = []
        for item in results:
            if isinstance(item, dict):
                text = (
                    item.get("content")
                    or item.get("text")
                    or item.get("memory", "")
                    or str(item)
                )
                if text:
                    texts.append(str(text))
            elif isinstance(item, str):
                texts.append(item)

        if not texts:
            return ""

        return "## Past Crisis Learnings\n" + "\n".join(f"- {t}" for t in texts)

    except Exception as exc:
        logger.warning("retrieve_crisis_learnings failed: %s", exc)
        return ""
