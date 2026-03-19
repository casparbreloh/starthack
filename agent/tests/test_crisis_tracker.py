"""Unit tests for src/crisis_tracker.py — CrisisOutcomeTracker system.

All LLM and memory API calls are mocked. Tests verify:
  - Crisis recording with correct observation window targets
  - Observation window capture with score deltas and secondary crisis detection
  - Status lifecycle: active → pending → completed
  - force_close_pending() mission-end cleanup
  - LLM synthesis with mocked Agent (patch at src.crisis_tracker.Agent)
  - Rule-based synthesis fallback on exception
  - Memory persistence via persist_learning()
  - Memory retrieval via retrieve_crisis_learnings() with single combined query
  - process_synthesis_batch() rate limiting (max_per_sol)
  - process_synthesis_batch() with memory_context=None (legacy path)
  - Float cast for int overall_score from simulation
  - Secondary crisis detection across observation windows
  - Full lifecycle: record → check windows → synthesize → persist
"""

from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest


# --------------------------------------------------------------------------- #
# Helpers                                                                      #
# --------------------------------------------------------------------------- #


def _make_mock_state(
    score: int | float = 50,
    crisis_ids: list[str] | None = None,
) -> dict:
    """Build a minimal mock telemetry state dict.

    Mimics the dict returned by SimClient.read_all_telemetry().
    All fields used by compact_state_summary() and check_observation_windows()
    are present.

    Args:
        score: Overall score (int is intentional — simulation returns int).
        crisis_ids: List of active crisis IDs to include.
    """
    crises = [{"id": cid, "type": "test_crisis", "severity": "high"} for cid in (crisis_ids or [])]
    return {
        "sim_status": {"current_sol": 0},
        "score_current": {"scores": {"overall_score": score}},
        "active_crises": {"crises": crises},
        "energy_status": {"battery_pct": 80},
        "water_status": {"reservoir_liters": 400},
        "greenhouse_environment": {"zones": [{"temp_c": 22}]},
        "crops_status": {"crops": []},
        "crew_nutrition": {"days_of_food_remaining": 30},
        "nutrients_status": {"nutrient_stock_remaining_pct": 90},
        "weather_current": {},
        "weather_history": [],
        "weather_forecast": [],
    }


def _make_tracker_with_record(sol: int = 10, pre_score: float = 60.0, pre_crisis_ids: set[str] | None = None):
    """Create a tracker with one active CrisisRecord at the given sol."""
    from src.crisis_tracker import CrisisOutcomeTracker

    tracker = CrisisOutcomeTracker()
    record = tracker.record_crisis(
        crisis_id="crisis-001",
        crisis_type="water_shortage",
        severity="high",
        sol=sol,
        pre_crisis_snapshot="bat=80% water=200L score=60.0 crises=0",
        pre_crisis_score=pre_score,
        pre_crisis_ids=pre_crisis_ids or set(),
        response_actions=["[crisis]irrigate(zone=A)"],
        specialist_output="Emergency irrigation activated.",
    )
    return tracker, record


def _fill_all_windows(record, base_score: float = 65.0) -> None:
    """Fill all observation windows with ObservationSnapshot instances."""
    from src.crisis_tracker import ObservationSnapshot

    for window_sol in list(record.observation_windows.keys()):
        record.observation_windows[window_sol] = ObservationSnapshot(
            sol=window_sol,
            state_summary="bat=85%",
            score=base_score,
            score_delta=base_score - record.pre_crisis_score,
        )


# --------------------------------------------------------------------------- #
# Task 1.1-1.2: Data model and record_crisis                                  #
# --------------------------------------------------------------------------- #


def test_record_crisis():
    """record_crisis() creates a CrisisRecord with correct fields and 3 window targets."""
    from src.crisis_tracker import CrisisOutcomeTracker

    tracker = CrisisOutcomeTracker()
    record = tracker.record_crisis(
        crisis_id="c1",
        crisis_type="water_shortage",
        severity="high",
        sol=10,
        pre_crisis_snapshot="bat=80%",
        pre_crisis_score=60.0,
        pre_crisis_ids={"existing-1"},
        response_actions=["[crisis]irrigate"],
        specialist_output="Handled.",
    )

    assert record.crisis_id == "c1"
    assert record.crisis_type == "water_shortage"
    assert record.severity == "high"
    assert record.sol_detected == 10
    assert record.pre_crisis_score == 60.0
    assert record.pre_crisis_ids == {"existing-1"}
    assert record.response_actions == ["[crisis]irrigate"]
    assert record.specialist_output == "Handled."
    assert record.status == "active"
    assert record.synthesized_learning is None

    # Observation windows are at sol+5, sol+15, sol+50
    assert set(record.observation_windows.keys()) == {15, 25, 60}
    assert all(v is None for v in record.observation_windows.values())

    # Record is stored in active_records
    assert len(tracker.active_records) == 1
    assert tracker.active_records[0] is record


# --------------------------------------------------------------------------- #
# Task 1.3: check_observation_windows                                         #
# --------------------------------------------------------------------------- #


def test_check_observation_windows_match():
    """Snapshot is created at sol+5 with correct score_delta and secondary crises."""
    tracker, record = _make_tracker_with_record(sol=10, pre_score=60.0, pre_crisis_ids=set())
    state = _make_mock_state(score=65, crisis_ids=["new-crisis-1"])

    updated = tracker.check_observation_windows(15, state)

    assert len(updated) == 1
    assert updated[0] is record

    snap = record.observation_windows[15]
    assert snap is not None
    assert snap.sol == 15
    assert snap.score == 65.0
    assert abs(snap.score_delta - 5.0) < 0.001
    assert "new-crisis-1" in snap.new_crisis_ids_since_detection
    assert record.status == "active"  # Only 1 of 3 windows filled


def test_check_observation_windows_no_match():
    """Sol that doesn't match any window target returns empty list."""
    tracker, record = _make_tracker_with_record(sol=10)
    state = _make_mock_state(score=65)

    updated = tracker.check_observation_windows(99, state)  # No window at sol 99

    assert updated == []
    assert all(v is None for v in record.observation_windows.values())


def test_check_observation_windows_multiple_records():
    """Two records with overlapping windows both updated in one call."""
    from src.crisis_tracker import CrisisOutcomeTracker

    tracker = CrisisOutcomeTracker()
    r1 = tracker.record_crisis("c1", "water_shortage", "high", 10, "", 60.0, set(), [], "")
    r2 = tracker.record_crisis("c2", "energy_disruption", "medium", 10, "", 55.0, set(), [], "")

    # Both have a window at sol 25 (10 + 15)
    state = _make_mock_state(score=65)
    updated = tracker.check_observation_windows(25, state)

    assert len(updated) == 2
    assert r1.observation_windows[25] is not None
    assert r2.observation_windows[25] is not None


def test_auto_transition_to_pending():
    """All 3 windows filled → status transitions to 'pending'."""
    tracker, record = _make_tracker_with_record(sol=10)
    state = _make_mock_state(score=65)

    tracker.check_observation_windows(15, state)
    tracker.check_observation_windows(25, state)
    assert record.status == "active"  # Only 2 of 3 filled

    tracker.check_observation_windows(60, state)
    assert record.status == "pending"  # All 3 filled


# --------------------------------------------------------------------------- #
# Task 1.5: force_close_pending                                               #
# --------------------------------------------------------------------------- #


def test_force_close_pending():
    """Crisis at sol 440 is force-closed at sol 450 with all 3 windows filled."""
    tracker, record = _make_tracker_with_record(sol=440, pre_score=55.0)
    state = _make_mock_state(score=50)

    count = tracker.force_close_pending(450, state)

    assert count == 1
    assert record.status == "pending"
    assert all(v is not None for v in record.observation_windows.values())
    # All windows should have sol=450 (the force-close sol)
    for snap in record.observation_windows.values():
        assert snap is not None
        assert snap.sol == 450


# --------------------------------------------------------------------------- #
# Task 1.4: get_pending_records                                               #
# --------------------------------------------------------------------------- #


def test_get_pending_records():
    """get_pending_records() returns only records with status='pending'."""
    tracker, record = _make_tracker_with_record(sol=10)
    state = _make_mock_state(score=65)

    # Initially no pending records
    assert tracker.get_pending_records() == []

    # Fill all windows to trigger pending transition
    tracker.check_observation_windows(15, state)
    tracker.check_observation_windows(25, state)
    tracker.check_observation_windows(60, state)

    pending = tracker.get_pending_records()
    assert len(pending) == 1
    assert pending[0] is record
    assert pending[0].status == "pending"


# --------------------------------------------------------------------------- #
# Task 2.1: synthesize_learning                                               #
# --------------------------------------------------------------------------- #


def test_synthesize_learning_success():
    """synthesize_learning() calls Agent with prompt containing crisis type."""
    from src.crisis_tracker import CrisisRecord, ObservationSnapshot, synthesize_learning

    record = CrisisRecord(
        crisis_id="c1",
        crisis_type="water_shortage",
        sol_detected=10,
        severity="high",
        pre_crisis_snapshot="bat=80%",
        pre_crisis_score=60.0,
        specialist_output="Handled.",
    )
    record.observation_windows = {
        15: ObservationSnapshot(sol=15, state_summary="bat=82%", score=65.0, score_delta=5.0),
        25: ObservationSnapshot(sol=25, state_summary="bat=83%", score=68.0, score_delta=8.0),
        60: ObservationSnapshot(sol=60, state_summary="bat=88%", score=72.0, score_delta=12.0),
    }

    mock_result = MagicMock()
    mock_result.message = {"content": [{"type": "text", "text": "Important water lesson."}]}
    mock_agent_inst = MagicMock()
    mock_agent_inst.return_value = mock_result

    with (
        patch("src.crisis_tracker.Agent", return_value=mock_agent_inst) as mock_agent_cls,
        patch("src.crisis_tracker.BedrockModel"),
    ):
        result = synthesize_learning(record)

    assert "Important water lesson." in result
    # Verify prompt was built (agent was called)
    mock_agent_inst.assert_called_once()
    call_args = mock_agent_inst.call_args
    prompt = call_args[0][0]
    assert "water_shortage" in prompt
    assert "sol 10" in prompt


def test_synthesize_learning_fallback():
    """synthesize_learning() returns rule-based fallback when Agent raises."""
    from src.crisis_tracker import CrisisRecord, ObservationSnapshot, synthesize_learning

    record = CrisisRecord(
        crisis_id="c2",
        crisis_type="energy_disruption",
        sol_detected=20,
        severity="medium",
        pre_crisis_snapshot="bat=50%",
        pre_crisis_score=55.0,
        specialist_output="Power restored.",
    )
    record.observation_windows = {
        25: ObservationSnapshot(sol=25, state_summary="", score=57.0, score_delta=2.0),
        35: ObservationSnapshot(sol=35, state_summary="", score=58.0, score_delta=3.0),
        70: ObservationSnapshot(sol=70, state_summary="", score=60.0, score_delta=5.0, new_crisis_ids_since_detection={"secondary-1"}),
    }

    mock_agent_inst = MagicMock()
    mock_agent_inst.side_effect = RuntimeError("AWS credentials not configured")

    with (
        patch("src.crisis_tracker.Agent", return_value=mock_agent_inst),
        patch("src.crisis_tracker.BedrockModel"),
    ):
        result = synthesize_learning(record)

    # Rule-based fallback: contains crisis type, sol, score delta, secondary count
    assert "energy_disruption" in result
    assert "sol 20" in result
    assert "5.0" in result or "+5.0" in result  # final score delta
    assert "1" in result  # 1 secondary crisis


# --------------------------------------------------------------------------- #
# Task 2.2: persist_learning                                                  #
# --------------------------------------------------------------------------- #


def test_persist_learning_calls_create_event():
    """persist_learning() calls create_event with [CRISIS LEARNING] tag."""
    from src.crisis_tracker import CrisisRecord, persist_learning

    record = CrisisRecord(
        crisis_id="c3",
        crisis_type="pathogen_outbreak",
        sol_detected=30,
        severity="critical",
        pre_crisis_snapshot="bat=90%",
        pre_crisis_score=70.0,
        specialist_output="Quarantine applied.",
        synthesized_learning="Pathogens spread fast — isolate zone B immediately.",
    )

    mock_client = MagicMock()
    persist_learning(mock_client, "mem-id", "mars-agent", "run-001", record)

    assert mock_client.create_event.call_count == 1
    call_kwargs = mock_client.create_event.call_args.kwargs
    assert call_kwargs["memory_id"] == "mem-id"
    assert call_kwargs["actor_id"] == "mars-agent"
    assert call_kwargs["session_id"] == "run-001"
    messages = call_kwargs["messages"]
    assert len(messages) == 1
    role, content = messages[0]
    assert role == "user"
    assert "[CRISIS LEARNING — pathogen_outbreak sol 30]" in content
    assert "Pathogens spread fast" in content


def test_persist_learning_noop_when_no_learning():
    """persist_learning() does nothing when synthesized_learning is None."""
    from src.crisis_tracker import CrisisRecord, persist_learning

    record = CrisisRecord(
        crisis_id="c4",
        crisis_type="water_shortage",
        sol_detected=5,
        severity="low",
        pre_crisis_snapshot="",
        pre_crisis_score=50.0,
        specialist_output="",
        synthesized_learning=None,
    )

    mock_client = MagicMock()
    persist_learning(mock_client, "mem-id", "actor", "session", record)

    mock_client.create_event.assert_not_called()


# --------------------------------------------------------------------------- #
# Task 2.3: process_synthesis_batch                                           #
# --------------------------------------------------------------------------- #


def test_process_synthesis_batch_rate_limited():
    """3 pending records with max_per_sol=2 → only 2 are processed."""
    from src.crisis_tracker import CrisisOutcomeTracker

    tracker = CrisisOutcomeTracker()
    for i in range(3):
        tracker, _ = _make_tracker_with_record(sol=10 + i)
        # Reset to get a fresh tracker each time
    tracker = CrisisOutcomeTracker()
    for i in range(3):
        r = tracker.record_crisis(
            crisis_id=f"c{i}",
            crisis_type="water_shortage",
            severity="high",
            sol=10 + i,
            pre_crisis_snapshot="bat=80%",
            pre_crisis_score=60.0,
            pre_crisis_ids=set(),
            response_actions=[],
            specialist_output="",
        )
        _fill_all_windows(r)
        r.status = "pending"

    mock_result = MagicMock()
    mock_result.message = {"content": [{"type": "text", "text": "Learning text."}]}
    mock_agent_inst = MagicMock()
    mock_agent_inst.return_value = mock_result

    with (
        patch("src.crisis_tracker.Agent", return_value=mock_agent_inst),
        patch("src.crisis_tracker.BedrockModel"),
    ):
        learnings = tracker.process_synthesis_batch(memory_context=None, max_per_sol=2)

    assert len(learnings) == 2
    assert len(tracker.completed_records) == 2
    remaining_pending = [r for r in tracker.active_records if r.status == "pending"]
    assert len(remaining_pending) == 1


def test_process_synthesis_batch_no_memory():
    """memory_context=None: synthesis runs but persist_learning is not called."""
    from src.crisis_tracker import CrisisOutcomeTracker

    tracker = CrisisOutcomeTracker()
    r = tracker.record_crisis("c1", "water_shortage", "high", 10, "bat=80%", 60.0, set(), [], "")
    _fill_all_windows(r)
    r.status = "pending"

    mock_result = MagicMock()
    mock_result.message = {"content": [{"type": "text", "text": "Learning."}]}
    mock_agent_inst = MagicMock()
    mock_agent_inst.return_value = mock_result

    with (
        patch("src.crisis_tracker.Agent", return_value=mock_agent_inst),
        patch("src.crisis_tracker.BedrockModel"),
        patch("src.crisis_tracker.persist_learning") as mock_persist,
    ):
        learnings = tracker.process_synthesis_batch(memory_context=None)

    assert len(learnings) == 1
    mock_persist.assert_not_called()  # No memory_context → persist skipped


# --------------------------------------------------------------------------- #
# Task 2.4: retrieve_crisis_learnings                                         #
# --------------------------------------------------------------------------- #


def test_retrieve_crisis_learnings_combined_query():
    """retrieve_crisis_learnings() makes a single API call with all crisis types combined."""
    from src.crisis_tracker import retrieve_crisis_learnings

    mock_client = MagicMock()
    mock_client.retrieve_memories.return_value = [
        {"content": "Past learning 1"},
        {"text": "Past learning 2"},
    ]

    result = retrieve_crisis_learnings(
        mock_client, "mem-id", "mars-agent", ["water_shortage", "energy_disruption"]
    )

    # Single API call regardless of number of crisis types
    assert mock_client.retrieve_memories.call_count == 1
    call_kwargs = mock_client.retrieve_memories.call_args.kwargs
    assert call_kwargs["memory_id"] == "mem-id"
    assert call_kwargs["actor_id"] == "mars-agent"
    assert call_kwargs["namespace"] == "/"
    assert "water_shortage" in call_kwargs["query"]
    assert "energy_disruption" in call_kwargs["query"]

    assert "## Past Crisis Learnings" in result
    assert "Past learning 1" in result
    assert "Past learning 2" in result


def test_retrieve_crisis_learnings_empty():
    """Empty crisis_types list returns empty string without API call."""
    from src.crisis_tracker import retrieve_crisis_learnings

    mock_client = MagicMock()
    result = retrieve_crisis_learnings(mock_client, "mem-id", "actor", [])

    assert result == ""
    mock_client.retrieve_memories.assert_not_called()


def test_retrieve_crisis_learnings_no_results():
    """Empty results from API returns empty string."""
    from src.crisis_tracker import retrieve_crisis_learnings

    mock_client = MagicMock()
    mock_client.retrieve_memories.return_value = []

    result = retrieve_crisis_learnings(mock_client, "mem-id", "actor", ["water_shortage"])

    assert result == ""


# --------------------------------------------------------------------------- #
# Additional edge case tests                                                   #
# --------------------------------------------------------------------------- #


def test_score_delta_uses_float():
    """Int score from simulation state produces correct float score_delta."""
    tracker, record = _make_tracker_with_record(sol=10, pre_score=60.0)
    # Score from simulation is int (not float)
    state = _make_mock_state(score=65)  # int

    tracker.check_observation_windows(15, state)
    snap = record.observation_windows[15]

    assert snap is not None
    assert isinstance(snap.score, float)
    assert isinstance(snap.score_delta, float)
    assert snap.score == 65.0
    assert snap.score_delta == 5.0


def test_secondary_crisis_detection():
    """New crisis appearing after detection is flagged as secondary in observation windows."""
    tracker, record = _make_tracker_with_record(
        sol=10, pre_crisis_ids={"original-crisis-1"}
    )

    # At sol 15, a new crisis appears that wasn't there at detection
    state = _make_mock_state(
        score=55,
        crisis_ids=["original-crisis-1", "new-secondary-crisis"]
    )
    tracker.check_observation_windows(15, state)

    snap = record.observation_windows[15]
    assert snap is not None
    assert "new-secondary-crisis" in snap.new_crisis_ids_since_detection
    assert "original-crisis-1" not in snap.new_crisis_ids_since_detection


def test_full_lifecycle():
    """Full lifecycle: record → check windows → all pending → synthesize → persist → completed."""
    from src.crisis_tracker import CrisisOutcomeTracker

    tracker = CrisisOutcomeTracker()
    record = tracker.record_crisis(
        crisis_id="lifecycle-001",
        crisis_type="water_shortage",
        severity="high",
        sol=10,
        pre_crisis_snapshot="bat=80%",
        pre_crisis_score=60.0,
        pre_crisis_ids=set(),
        response_actions=["[crisis]irrigate(zone=A)"],
        specialist_output="Irrigation activated.",
    )

    # Check at sol 15 (match: sol+5), sol 20 (no match), sol 25 (match: sol+15), sol 60 (match: sol+50)
    state = _make_mock_state(score=65)
    updated = tracker.check_observation_windows(15, state)
    assert len(updated) == 1
    assert record.status == "active"

    updated = tracker.check_observation_windows(20, state)
    assert len(updated) == 0  # No window at sol 20

    tracker.check_observation_windows(25, state)
    assert record.status == "active"  # Still one window missing

    tracker.check_observation_windows(60, state)
    assert record.status == "pending"  # All 3 filled

    # Synthesize and persist
    mock_result = MagicMock()
    mock_result.message = {"content": [{"type": "text", "text": "Water crisis learning."}]}
    mock_agent_inst = MagicMock()
    mock_agent_inst.return_value = mock_result
    mock_memory_client = MagicMock()

    memory_context = {
        "memory_client": mock_memory_client,
        "memory_id": "mem-id",
        "actor_id": "mars-agent",
        "session_id": "run-001",
    }

    with (
        patch("src.crisis_tracker.Agent", return_value=mock_agent_inst),
        patch("src.crisis_tracker.BedrockModel"),
    ):
        learnings = tracker.process_synthesis_batch(memory_context=memory_context)

    assert len(learnings) == 1
    assert "Water crisis learning." in learnings[0]

    # Record moved to completed
    assert len(tracker.completed_records) == 1
    assert len(tracker.active_records) == 0
    assert tracker.completed_records[0].status == "completed"
    assert "water_shortage" in tracker.completed_records[0].crisis_type

    # Memory was persisted
    assert mock_memory_client.create_event.call_count == 1
    call_kwargs = mock_memory_client.create_event.call_args.kwargs
    assert "[CRISIS LEARNING — water_shortage sol 10]" in call_kwargs["messages"][0][1]
