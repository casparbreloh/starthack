"""Tests for distill.py — learning distillation logic."""

from __future__ import annotations

from src.config import DEFAULT_STRATEGY
from src.distill import (
    distill_crisis_playbook,
    distill_wave_learnings,
    format_for_memory,
)
from src.results import RunResult


def _make_result(
    run_id: str,
    score: int,
    outcome: str = "complete",
    crises: list[dict] | None = None,
    crop_yields: dict | None = None,
    crops_harvested: int = 5,
) -> RunResult:
    """Helper to create a mock RunResult."""
    return RunResult(
        run_id=run_id,
        wave_id="test-wave",
        config_hash="abc",
        seed=42,
        difficulty="normal",
        final_sol=450 if outcome == "complete" else 100,
        mission_outcome=outcome,
        final_score=score,
        survival_score=90 if outcome == "complete" else 0,
        nutrition_score=80,
        resource_efficiency_score=70,
        crisis_mgmt_score=75,
        crises_encountered=len(crises) if crises else 0,
        crises_resolved=sum(1 for c in (crises or []) if c.get("resolved")),
        crisis_log=crises or [],
        crop_yields=crop_yields or {"lettuce": 10.0, "potato": 80.0},
        crops_planted=8,
        crops_harvested=crops_harvested,
        key_decisions=[{"sol": 0, "action": "first_plant lettuce zone A", "reason": "schedule"}],
        strategy_config=DEFAULT_STRATEGY.to_dict(),
        resource_averages={"avg_water_L": 350.0, "avg_battery_pct": 70.0, "avg_food_days": 15.0},
    )


def test_distill_wave_learnings_returns_list() -> None:
    """distill_wave_learnings should return a non-empty list of strings."""
    top_results = [_make_result(f"top-{i}", score=80 + i) for i in range(5)]
    bottom_results = [_make_result(f"bot-{i}", score=30 + i, outcome="failed") for i in range(5)]

    learnings = distill_wave_learnings(top_results, bottom_results)
    assert isinstance(learnings, list)
    assert len(learnings) >= 3


def test_distill_wave_learnings_max_20() -> None:
    """Learnings list should be capped at 20."""
    top_results = [_make_result(f"t{i}", 90) for i in range(10)]
    bottom_results = [_make_result(f"b{i}", 20) for i in range(10)]
    learnings = distill_wave_learnings(top_results, bottom_results)
    assert len(learnings) <= 20


def test_distill_wave_learnings_empty_input() -> None:
    """Empty inputs should return a fallback message."""
    learnings = distill_wave_learnings([], [])
    assert len(learnings) == 1
    assert "No results" in learnings[0]


def test_distill_crisis_playbook_has_entries() -> None:
    """Crisis playbook should have entries for crisis types in results."""
    crises = [
        {"type": "water_shortage", "started_sol": 50, "severity": "warning",
         "resolved": True, "resolved_sol": 55, "duration_sols": 5},
        {"type": "nutrient_depletion", "started_sol": 10, "severity": "warning",
         "resolved": False, "resolved_sol": None, "duration_sols": None},
    ]
    top_results = [_make_result("t1", 85, crises=crises[:1])]
    bottom_results = [_make_result("b1", 25, crises=crises)]

    playbook = distill_crisis_playbook(top_results, bottom_results)
    assert isinstance(playbook, dict)
    assert len(playbook) > 0
    assert "water_shortage" in playbook or "nutrient_depletion" in playbook


def test_format_for_memory() -> None:
    """format_for_memory should produce tagged string with learnings."""
    learnings = ["First learning.", "Second learning."]
    result = format_for_memory(learnings, "wave-001")
    assert "[FAST-SIM WAVE wave-001" in result
    assert "First learning." in result
    assert "Second learning." in result
