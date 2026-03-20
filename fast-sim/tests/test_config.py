"""Tests for config.py — StrategyConfig + RunConfig serialization."""

from __future__ import annotations

import json

from src.config import DEFAULT_STRATEGY, RunConfig, StrategyConfig


def test_default_strategy_round_trip() -> None:
    """StrategyConfig should survive JSON serialization round-trip."""
    d = DEFAULT_STRATEGY.to_dict()
    s2 = StrategyConfig.from_dict(d)
    d2 = s2.to_dict()
    assert d == d2


def test_default_strategy_has_planting_schedule() -> None:
    """DEFAULT_STRATEGY should have a non-empty planting schedule."""
    assert len(DEFAULT_STRATEGY.planting_schedule) > 0
    # Should have entries for all 3 zones
    zones = {e.zone_id for e in DEFAULT_STRATEGY.planting_schedule}
    assert "A" in zones
    assert "B" in zones
    assert "C" in zones


def test_default_strategy_crop_types_valid() -> None:
    """All planting schedule entries should reference valid crop types."""
    valid = {"lettuce", "potato", "radish", "beans", "herbs"}
    for entry in DEFAULT_STRATEGY.planting_schedule:
        assert entry.crop_type in valid, f"Invalid crop type: {entry.crop_type}"


def test_default_strategy_energy_sums_to_100() -> None:
    """Energy allocation percentages should sum to ~100."""
    for key in ["default", "crisis"]:
        alloc = DEFAULT_STRATEGY.energy_allocation.get(key, {})
        total = sum(float(alloc.get(k, 0)) for k in [
            "heating_pct", "lighting_pct", "water_recycling_pct",
            "nutrient_pumps_pct", "reserve_pct"
        ])
        assert abs(total - 100.0) < 1.0, f"{key} allocation sums to {total}"


def test_run_config_json_round_trip() -> None:
    """RunConfig should survive JSON round-trip."""
    rc = RunConfig(
        strategy=DEFAULT_STRATEGY,
        seed=42,
        difficulty="normal",
        run_id="test-001",
        wave_id="wave-001",
    )
    j = rc.to_json()
    rc2 = RunConfig.from_json(j)
    assert rc2.seed == 42
    assert rc2.difficulty == "normal"
    assert rc2.run_id == "test-001"
    assert len(rc2.strategy.planting_schedule) == len(rc.strategy.planting_schedule)


def test_run_config_difficulty_is_string() -> None:
    """RunConfig.difficulty must be str (not enum) for JSON serialization."""
    rc = RunConfig(strategy=DEFAULT_STRATEGY, seed=1, difficulty="hard", run_id="x", wave_id="y")
    parsed = json.loads(rc.to_json())
    assert isinstance(parsed["difficulty"], str)
    assert parsed["difficulty"] == "hard"


def test_ice_mining_config_roundtrip() -> None:
    """IceMiningConfig should survive to_dict/from_dict round-trip."""
    from src.config import IceMiningConfig, StrategyConfig

    config = StrategyConfig(
        ice_mining=IceMiningConfig(
            enabled=False,
            drill_maintenance_interval_sols=6,
            energy_reserve_wh=3000.0,
            water_ceiling_L=480.0,
            drill_health_maintenance_threshold_pct=35.0,
        )
    )
    d = config.to_dict()
    config2 = StrategyConfig.from_dict(d)
    assert config2.ice_mining.enabled is False
    assert config2.ice_mining.drill_maintenance_interval_sols == 6
    assert config2.ice_mining.energy_reserve_wh == 3000.0
    assert config2.ice_mining.water_ceiling_L == 480.0
    assert config2.ice_mining.drill_health_maintenance_threshold_pct == 35.0


def test_ice_mining_config_defaults_on_missing() -> None:
    """StrategyConfig.from_dict({}) should apply ice mining defaults."""
    config = StrategyConfig.from_dict({})
    assert config.ice_mining.enabled is True
    assert config.ice_mining.drill_maintenance_interval_sols == 4
    assert config.ice_mining.energy_reserve_wh == 2000.0
    assert config.ice_mining.water_ceiling_L == 550.0
    assert config.ice_mining.drill_health_maintenance_threshold_pct == 40.0
