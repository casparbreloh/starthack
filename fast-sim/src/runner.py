"""
Simulation runner — full 450-sol loop.

Ties together PolicyEngine + SimulationEngine to run complete missions
and return well-formed RunResult objects.
"""

from __future__ import annotations

import time
from typing import Any

from src.config import RunConfig
from src.engine_bridge import create_engine, dispatch_action, inject_scenario
from src.policy import PolicyEngine
from src.results import RunResult, compute_config_hash

# Mission duration constant
MISSION_DURATION_SOLS = 450

# MissionPhase string value for active
_ACTIVE = "active"


def run_simulation(config: RunConfig) -> RunResult:
    """
    Run a full 450-sol simulation using the given RunConfig.

    Returns a RunResult with all per-run metrics.
    """
    start_time = time.monotonic()

    # 1. Create engine (handles reset + RNG seeding in correct order)
    scenario = config.strategy.scenario
    engine = create_engine(
        seed=config.seed,
        difficulty=config.difficulty,
        suppress_autonomous=scenario.suppress_autonomous,
    )

    # Build sol→injections lookup for controlled crisis injection
    injection_schedule: dict[int, list[tuple[str, dict]]] = {}
    for inj in scenario.injections:
        injection_schedule.setdefault(inj.sol, []).append((inj.scenario, inj.kwargs))

    # 2. Create policy engine
    policy = PolicyEngine(config.strategy)

    # 3. Initialize tracking
    crisis_log: list[dict[str, Any]] = []
    seen_crisis_ids: set[str] = set()
    crop_yields: dict[str, float] = {}
    crop_deaths = 0
    crops_planted = 0
    crops_harvested = 0
    key_decisions: list[dict[str, Any]] = []

    # Resource tracking
    water_samples: list[float] = []
    battery_samples: list[float] = []
    food_samples: list[float] = []
    water_min = float("inf")
    water_max = float("-inf")
    battery_min = float("inf")
    battery_max = float("-inf")
    food_min = float("inf")
    nutrient_min = float("inf")
    drill_health_min = float("inf")

    # Planting callback to update policy tracking
    def _handle_plant_result(
        result: dict[str, Any], zone_id: str, area_m2: float, crop_type: str
    ) -> None:
        nonlocal crops_planted
        crop_id = result.get("crop_id")
        if crop_id:
            policy.post_action_plant(crop_id, zone_id, area_m2, crop_type)
            crops_planted += 1
            if crops_planted == 1:
                key_decisions.append(
                    {
                        "sol": engine.current_sol,
                        "action": f"first_plant {crop_type} zone {zone_id}",
                        "reason": "schedule",
                    }
                )

    def _handle_harvest_result(result: dict[str, Any], crop_type: str) -> None:
        nonlocal crops_harvested
        crops_harvested += 1
        yield_kg = float(result.get("yield_kg", 0.0))
        crop_type_str = str(crop_type)
        crop_yields[crop_type_str] = crop_yields.get(crop_type_str, 0.0) + yield_kg

    # 4. Main 450-sol loop
    for sol in range(MISSION_DURATION_SOLS):
        if str(engine.mission_phase) != _ACTIVE:
            break

        # a. Get policy actions
        actions = policy.decide(engine, sol)

        # b. Dispatch each action
        for action in actions:
            endpoint = action["endpoint"]
            body = action["body"]

            try:
                result = dispatch_action(engine, endpoint, body)

                # Track crop events
                if endpoint == "crops/plant":
                    _handle_plant_result(
                        result,
                        body.get("zone_id", "?"),
                        float(body.get("area_m2", 0.0)),
                        body.get("type", "?"),
                    )
                elif endpoint == "crops/harvest":
                    # Find crop type from batches (it may have just been removed)
                    crop_type = result.get("crop_type", str(body.get("crop_id", "unknown")))
                    # harvest result contains type info
                    _handle_harvest_result(result, result.get("crop_type", crop_type))

            except (ValueError, KeyError) as exc:
                # Log but continue — policy may attempt invalid actions
                key_decisions.append(
                    {
                        "sol": sol,
                        "action": f"action_error {endpoint}",
                        "reason": str(exc)[:80],
                    }
                )

        # Accumulate policy's own key decisions
        if policy.key_decisions:
            key_decisions.extend(policy.key_decisions)
            policy.key_decisions.clear()

        # c. Advance engine by 1 sol
        engine.advance(1)

        # c2. Inject scheduled crises (controlled scenarios)
        if sol in injection_schedule:
            for scenario_name, kwargs in injection_schedule[sol]:
                call_kwargs = dict(kwargs)
                # Pathogen needs a crop_id — pick first active crop if not specified
                if scenario_name == "pathogen" and not call_kwargs.get("crop_id"):
                    active_crops = [
                        b for b in engine.crops.batches.values()
                        if hasattr(b, "health") and b.health > 0.1
                    ]
                    if active_crops:
                        call_kwargs["crop_id"] = active_crops[0].crop_id
                    else:
                        continue  # no crops to infect — skip
                inject_scenario(engine, scenario_name, **call_kwargs)

        # d. Track per-sol resources
        water_l = engine.water.state.reservoir_liters
        battery = engine.energy.battery_pct
        food_d = engine.crew.days_of_food

        water_samples.append(water_l)
        battery_samples.append(battery)
        food_samples.append(food_d)

        water_min = min(water_min, water_l)
        water_max = max(water_max, water_l)
        battery_min = min(battery_min, battery)
        battery_max = max(battery_max, battery)
        food_min = min(food_min, food_d)

        # Nutrient min (worst zone, nitrogen as proxy)
        if engine.nutrients.state:
            nut_pct = engine.nutrients.stock_remaining_pct
            nutrient_min = min(nutrient_min, nut_pct)

        # Drill health min
        drill_health = engine.water.state.drill_health_pct
        drill_health_min = min(drill_health_min, drill_health)

        # e. Detect new crises
        for crisis in engine.events.all_crises():
            if crisis.id not in seen_crisis_ids:
                seen_crisis_ids.add(crisis.id)
                crisis_log.append(
                    {
                        "type": str(crisis.type),
                        "started_sol": crisis.started_sol,
                        "severity": str(crisis.severity),
                        "resolved": crisis.resolved,
                        "resolved_sol": crisis.resolved_sol,
                        "duration_sols": (
                            (crisis.resolved_sol - crisis.started_sol)
                            if crisis.resolved and crisis.resolved_sol is not None
                            else None
                        ),
                    }
                )

        # Update crisis log resolutions
        for entry in crisis_log:
            matching = next(
                (
                    c
                    for c in engine.events.all_crises()
                    if str(c.type) == entry["type"] and c.started_sol == entry["started_sol"]
                ),
                None,
            )
            if matching and matching.resolved and not entry["resolved"]:
                entry["resolved"] = True
                entry["resolved_sol"] = matching.resolved_sol
                entry["duration_sols"] = (
                    matching.resolved_sol - matching.started_sol
                    if matching.resolved_sol is not None
                    else None
                )

    # 5. Post-loop: collect final state
    final_sol = engine.current_sol
    mission_outcome = "complete" if str(engine.mission_phase) == "complete" else "failed"
    if str(engine.mission_phase) == _ACTIVE:
        mission_outcome = "complete"  # Loop ended at 450 sols normally

    snapshot = engine.scoring.snapshot
    final_score = snapshot.overall_score

    crises_resolved = sum(1 for entry in crisis_log if entry["resolved"])

    # Resource extremes — handle inf defaults (no data)
    if water_min == float("inf"):
        water_min = water_max = 0.0
    if battery_min == float("inf"):
        battery_min = battery_max = 0.0
    if food_min == float("inf"):
        food_min = 0.0
    if nutrient_min == float("inf"):
        nutrient_min = 100.0
    if drill_health_min == float("inf"):
        drill_health_min = 100.0

    resource_extremes = {
        "water_min_L": round(water_min, 1),
        "water_max_L": round(water_max, 1),
        "battery_min_pct": round(battery_min, 1),
        "battery_max_pct": round(battery_max, 1),
        "food_min_days": round(food_min, 1),
        "nutrient_min_pct": round(nutrient_min, 1),
        "total_mined_liters": round(engine.water.state.total_mined_liters, 1),
        "drill_health_min_pct": round(drill_health_min, 1),
    }

    resource_averages = {
        "avg_water_L": round(sum(water_samples) / len(water_samples), 1) if water_samples else 0.0,
        "avg_battery_pct": (
            round(sum(battery_samples) / len(battery_samples), 1) if battery_samples else 0.0
        ),
        "avg_food_days": round(sum(food_samples) / len(food_samples), 1) if food_samples else 0.0,
    }

    config_dict = config.to_dict()
    config_hash = compute_config_hash(config_dict)

    duration = time.monotonic() - start_time

    return RunResult(
        run_id=config.run_id,
        wave_id=config.wave_id,
        config_hash=config_hash,
        seed=config.seed,
        difficulty=config.difficulty,
        final_sol=final_sol,
        mission_outcome=mission_outcome,
        final_score=final_score,
        survival_score=snapshot.survival["score"],
        nutrition_score=snapshot.nutrition["score"],
        resource_efficiency_score=snapshot.resource_efficiency["score"],
        crisis_mgmt_score=snapshot.crisis_management["score"],
        crises_encountered=len(crisis_log),
        crises_resolved=crises_resolved,
        crisis_log=crisis_log,
        crop_yields=crop_yields,
        crop_deaths=crop_deaths,
        crops_planted=crops_planted,
        crops_harvested=crops_harvested,
        resource_extremes=resource_extremes,
        resource_averages=resource_averages,
        key_decisions=key_decisions[:50],  # cap at 50 for storage
        strategy_config=config.strategy.to_dict(),
        duration_seconds=round(duration, 3),
    )


def run_simulation_batch(configs: list[RunConfig]) -> list[RunResult]:
    """
    Run multiple simulations sequentially.

    Used by Lambda worker that pulls batches from SQS.
    """
    return [run_simulation(config) for config in configs]
