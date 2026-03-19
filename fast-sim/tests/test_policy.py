"""Tests for policy.py — PolicyEngine decision logic."""

from __future__ import annotations

from src.config import DEFAULT_STRATEGY
from src.engine_bridge import create_engine, dispatch_action
from src.policy import PolicyEngine


def test_sol_zero_actions_include_environment_and_plant() -> None:
    """Sol 0 should include greenhouse environment setup and crop planting."""
    engine = create_engine(seed=42, difficulty="normal")
    policy = PolicyEngine(DEFAULT_STRATEGY)
    actions = policy.decide(engine, 0)
    endpoints = [a["endpoint"] for a in actions]
    assert "greenhouse/set_environment" in endpoints
    assert "crops/plant" in endpoints


def test_policy_tracks_planted_area() -> None:
    """Policy should track planted area after plant actions are dispatched."""
    engine = create_engine(seed=42, difficulty="normal")
    policy = PolicyEngine(DEFAULT_STRATEGY)

    actions = policy.decide(engine, 0)
    for a in actions:
        if a["endpoint"] == "crops/plant":
            result = dispatch_action(engine, a["endpoint"], a["body"])
            policy.post_action_plant(
                result.get("crop_id", ""),
                a["body"]["zone_id"],
                a["body"]["area_m2"],
                a["body"]["type"],
            )

    # After planting, planted area should be > 0
    assert policy._planted_area.get("C", 0) > 0  # potato in zone C
    assert policy._planted_area.get("B", 0) > 0  # beans in zone B
    assert policy._planted_area.get("A", 0) > 0  # lettuce + radish in zone A


def test_sol_1_actions_no_duplicate_environment() -> None:
    """After sol 0 setup, subsequent sols should not resend environment setup."""
    engine = create_engine(seed=42, difficulty="normal")
    policy = PolicyEngine(DEFAULT_STRATEGY)

    # Sol 0
    policy.decide(engine, 0)
    engine.advance(1)

    # Sol 1
    actions = policy.decide(engine, 1)
    endpoints = [a["endpoint"] for a in actions]
    assert "greenhouse/set_environment" not in endpoints


def test_irrigation_actions_for_all_zones() -> None:
    """Policy should emit irrigation actions for all configured zones."""
    engine = create_engine(seed=42, difficulty="normal")
    policy = PolicyEngine(DEFAULT_STRATEGY)
    actions = policy.decide(engine, 0)

    irrigation_zones = {
        a["body"]["zone_id"]
        for a in actions
        if a["endpoint"] == "water/set_irrigation"
    }
    assert irrigation_zones == {"A", "B", "C"}


def test_filter_maintenance_on_schedule() -> None:
    """Policy should schedule filter cleaning every N sols."""
    engine = create_engine(seed=42, difficulty="normal")
    policy = PolicyEngine(DEFAULT_STRATEGY)

    # Advance to interval sol
    interval = DEFAULT_STRATEGY.filter_maintenance_interval_sols
    for s in range(interval):
        policy.decide(engine, s)
        engine.advance(1)

    # At the interval sol, should emit maintenance
    actions = policy.decide(engine, interval)
    endpoints = [a["endpoint"] for a in actions]
    assert "water/maintenance" in endpoints


def test_policy_mines_ice_on_sol_0() -> None:
    """Policy should include water/mine_ice in sol-0 actions when reservoir is below ceiling."""
    engine = create_engine(seed=42, difficulty="normal")
    # Drain reservoir below water_ceiling_L (default 550L) to allow mining
    engine.water.state.reservoir_liters = 400.0
    policy = PolicyEngine(DEFAULT_STRATEGY)
    actions = policy.decide(engine, 0)
    endpoints = [a["endpoint"] for a in actions]
    assert "water/mine_ice" in endpoints


def test_policy_skips_mining_when_disabled() -> None:
    """Policy should not mine ice when ice_mining.enabled is False."""
    from src.config import IceMiningConfig, StrategyConfig
    from copy import deepcopy

    config = deepcopy(DEFAULT_STRATEGY)
    config.ice_mining = IceMiningConfig(enabled=False)
    engine = create_engine(seed=42, difficulty="normal")
    engine.water.state.reservoir_liters = 400.0
    policy = PolicyEngine(config)
    actions = policy.decide(engine, 0)
    endpoints = [a["endpoint"] for a in actions]
    assert "water/mine_ice" not in endpoints


def test_policy_skips_mining_when_battery_low() -> None:
    """Policy should not mine when battery is below energy_reserve_wh (default 2000 Wh)."""
    engine = create_engine(seed=42, difficulty="normal")
    engine.energy.state.battery_level_wh = 1000.0  # below 2000 Wh reserve
    engine.water.state.reservoir_liters = 400.0
    policy = PolicyEngine(DEFAULT_STRATEGY)
    actions = policy.decide(engine, 0)
    endpoints = [a["endpoint"] for a in actions]
    assert "water/mine_ice" not in endpoints


def test_policy_maintains_drill_on_schedule() -> None:
    """Policy should emit drill maintenance on sol 4, 8, 12 (default interval=4)."""
    engine = create_engine(seed=42, difficulty="normal")
    policy = PolicyEngine(DEFAULT_STRATEGY)

    for sol in [4, 8, 12]:
        actions = policy.decide(engine, sol)
        maintenance_bodies = [
            a["body"] for a in actions
            if a["endpoint"] == "water/maintenance"
        ]
        assert any(b.get("action") == "maintain_drill" for b in maintenance_bodies), (
            f"Expected drill maintenance on sol {sol}, got: {maintenance_bodies}"
        )
