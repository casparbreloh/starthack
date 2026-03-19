"""Tests for runner.py — full simulation run."""

from __future__ import annotations

from src.config import DEFAULT_STRATEGY, RunConfig
from src.runner import run_simulation, run_simulation_batch


def test_run_simulation_completes_or_fails_gracefully() -> None:
    """Simulation should reach sol 450 or fail with valid outcome."""
    config = RunConfig(
        strategy=DEFAULT_STRATEGY,
        seed=42,
        difficulty="normal",
        run_id="test-run",
        wave_id="test-wave",
    )
    result = run_simulation(config)
    assert result.final_sol >= 1
    assert result.mission_outcome in ("complete", "failed")
    assert result.final_score >= 0


def test_run_simulation_result_is_well_formed() -> None:
    """RunResult should have all required fields populated."""
    config = RunConfig(
        strategy=DEFAULT_STRATEGY,
        seed=42,
        difficulty="normal",
        run_id="test-run",
        wave_id="test-wave",
    )
    result = run_simulation(config)
    assert result.run_id == "test-run"
    assert result.wave_id == "test-wave"
    assert result.seed == 42
    assert result.difficulty == "normal"
    assert isinstance(result.final_score, int)
    assert isinstance(result.crops_planted, int)
    assert isinstance(result.duration_seconds, float)


def test_run_simulation_score_above_minimum() -> None:
    """Default strategy should achieve at least 30 points."""
    config = RunConfig(
        strategy=DEFAULT_STRATEGY,
        seed=42,
        difficulty="normal",
        run_id="test-score",
        wave_id="test-wave",
    )
    result = run_simulation(config)
    assert result.final_score >= 30, f"Score {result.final_score} below minimum 30"


def test_run_simulation_plants_crops() -> None:
    """Simulation should plant at least one crop."""
    config = RunConfig(
        strategy=DEFAULT_STRATEGY,
        seed=42,
        difficulty="normal",
        run_id="test-crops",
        wave_id="test-wave",
    )
    result = run_simulation(config)
    assert result.crops_planted > 0


def test_run_simulation_batch() -> None:
    """Batch runner should return results for all configs."""
    configs = [
        RunConfig(
            strategy=DEFAULT_STRATEGY,
            seed=i,
            difficulty="normal",
            run_id=f"batch-{i}",
            wave_id="batch-wave",
        )
        for i in range(3)
    ]
    results = run_simulation_batch(configs)
    assert len(results) == 3
    for r in results:
        assert r.final_score >= 0


def test_run_simulation_json_round_trip() -> None:
    """RunResult should survive JSON round-trip."""
    config = RunConfig(
        strategy=DEFAULT_STRATEGY,
        seed=42,
        difficulty="normal",
        run_id="rt-test",
        wave_id="rt-wave",
    )
    result = run_simulation(config)
    j = result.to_json()
    r2 = type(result).from_json(j)
    assert r2.run_id == result.run_id
    assert r2.final_score == result.final_score
