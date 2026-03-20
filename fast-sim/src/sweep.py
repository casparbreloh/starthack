"""
Parameter sweep generation.

Generates random and evolutionary strategy configs for systematic policy sweeps.
"""

from __future__ import annotations

import random
from copy import deepcopy
from typing import Any

from src.config import (
    CrisisInjection,
    DEFAULT_STRATEGY,
    EnvironmentTarget,
    FoodShortageResponse,
    HarvestPolicy,
    IceMiningConfig,
    NutrientCorrection,
    PlantingEntry,
    RunConfig,
    ScenarioConfig,
    StrategyConfig,
)
from src.results import RunResult

# Valid crop types and zone IDs (mirrors simulation enums)
VALID_CROP_TYPES = ["lettuce", "potato", "radish", "beans", "herbs"]
VALID_ZONE_IDS = ["A", "B", "C"]
ZONE_AREAS = {"A": 12.0, "B": 18.0, "C": 20.0}
SCENARIO_TYPES = ["water_leak", "dust_storm", "hvac_failure", "pathogen", "energy_disruption"]


def _make_scenario(rng: random.Random, level: int) -> ScenarioConfig:
    """Build a ScenarioConfig for the given level with random injections."""
    if level == 0 or level == 3:
        return ScenarioConfig(level=level, injections=[])

    n_crises = 1 if level == 1 else rng.randint(2, 3)
    chosen = rng.sample(SCENARIO_TYPES, k=min(n_crises, len(SCENARIO_TYPES)))
    injections = []
    for sc in chosen:
        sol = rng.randint(30, 350)
        kwargs: dict = {}
        injections.append(CrisisInjection(sol=sol, scenario=sc, kwargs=kwargs))
    return ScenarioConfig(
        level=level,
        injections=sorted(injections, key=lambda i: i.sol),
    )


def generate_random_configs(
    n: int,
    wave_id: str,
    base: StrategyConfig = DEFAULT_STRATEGY,
    perturbation_pct: float = 0.30,
    scenario_level: int = 3,
) -> list[RunConfig]:
    """
    Generate n configs by randomly perturbing the base strategy.

    Each numeric parameter is perturbed by +/- perturbation_pct (default 30%).
    Energy allocations are re-normalized to sum to 100 after perturbation.
    """
    configs: list[RunConfig] = []
    rng = random.Random()

    for i in range(n):
        # 30% fully random strategies for exploration diversity
        if rng.random() < 0.30:
            strategy = _random_strategy(rng)
        else:
            strategy = _perturb_strategy(base, rng, perturbation_pct)
        strategy.scenario = _make_scenario(rng, scenario_level)
        run_id = f"{wave_id}-{i:04d}"
        configs.append(
            RunConfig(
                strategy=strategy,
                seed=rng.randint(0, 2**31 - 1),
                difficulty="normal",
                run_id=run_id,
                wave_id=wave_id,
            )
        )

    return configs


def evolve_configs(
    top_k_results: list[RunResult],
    n: int,
    wave_id: str,
    mutation_rate: float = 0.15,
) -> list[RunConfig]:
    """
    Generate n configs by evolving from top-k parents.

    For each child:
    - Pick a random parent from top-k
    - Apply Gaussian perturbation (sigma = mutation_rate * param_range)
    - 30% chance of crossover (mix planting from parent A, energy from parent B)
    """
    if not top_k_results:
        return generate_random_configs(n, wave_id)

    rng = random.Random()
    configs: list[RunConfig] = []

    parent_strategies = [
        StrategyConfig.from_dict(r.strategy_config) for r in top_k_results if r.strategy_config
    ]
    if not parent_strategies:
        return generate_random_configs(n, wave_id)

    for i in range(n):
        parent_a = rng.choice(parent_strategies)

        # 30% chance of crossover
        if len(parent_strategies) > 1 and rng.random() < 0.30:
            parent_b = rng.choice([p for p in parent_strategies if p is not parent_a])
            child = _crossover(parent_a, parent_b, rng)
        else:
            child = deepcopy(parent_a)

        # Apply mutation
        child = _mutate_strategy(child, rng, mutation_rate)

        run_id = f"{wave_id}-{i:04d}"
        configs.append(
            RunConfig(
                strategy=child,
                seed=rng.randint(0, 2**31 - 1),
                difficulty="normal",
                run_id=run_id,
                wave_id=wave_id,
            )
        )

    return configs


def select_top_k(results: list[RunResult], k: int) -> list[RunResult]:
    """Select the top-k results by final_score descending."""
    return sorted(results, key=lambda r: r.final_score, reverse=True)[:k]


# ------------------------------------------------------------------
# Internal helpers
# ------------------------------------------------------------------


def _random_strategy(rng: random.Random) -> StrategyConfig:
    """Generate a fully random strategy — not a perturbation of baseline.

    Explores fundamentally different approaches:
    - Random crop areas (1-20 m2)
    - Random irrigation rates (0-40 L/sol per zone)
    - Random planting schedules
    - Different crop type priorities
    """
    from src.config import (
        EnvironmentTarget,
        FoodShortageResponse,
        HarvestPolicy,
        IceMiningConfig,
        NutrientCorrection,
        PlantingEntry,
        StrategyConfig,
    )

    # Random planting schedule
    schedule: list[PlantingEntry] = []
    # Pick 1-3 primary crops
    primary_crops = rng.sample(VALID_CROP_TYPES, k=rng.randint(1, 3))
    growth_days = {"lettuce": 35, "potato": 90, "radish": 25, "beans": 60, "herbs": 15}

    for crop in primary_crops:
        zone = rng.choice(VALID_ZONE_IDS)
        area = round(rng.uniform(2.0, ZONE_AREAS[zone]), 1)
        cycle = growth_days.get(crop, 60)
        for sol in range(0, 450, cycle):
            schedule.append(PlantingEntry(sol=sol, crop_type=crop, zone_id=zone, area_m2=area))

    # Always include some lettuce for micronutrients (in staggered batches)
    if "lettuce" not in primary_crops:
        zone = rng.choice(VALID_ZONE_IDS)
        area = round(rng.uniform(2.0, 5.0), 1)
        for offset in [0, 5, 10]:
            for sol in range(offset, 450, 35):
                schedule.append(PlantingEntry(sol=sol, crop_type="lettuce", zone_id=zone, area_m2=area))

    schedule.sort(key=lambda e: e.sol)

    # Random irrigation (0-40 L/sol per zone — includes zero-irrigation strategies)
    irrigation = {z: round(rng.uniform(0.0, 40.0), 1) for z in VALID_ZONE_IDS}

    # Random energy allocation
    raw = {k: rng.uniform(5.0, 50.0) for k in ["heating_pct", "lighting_pct", "water_recycling_pct", "nutrient_pumps_pct", "reserve_pct"]}
    total = sum(raw.values())
    default_alloc = {k: round(v / total * 100.0, 1) for k, v in raw.items()}
    crisis_alloc = {k: round(rng.uniform(5.0, 40.0), 1) for k in default_alloc}
    crisis_total = sum(crisis_alloc.values())
    crisis_alloc = {k: round(v / crisis_total * 100.0, 1) for k, v in crisis_alloc.items()}

    # Random harvest policy
    harvest = HarvestPolicy(
        min_growth_pct=rng.uniform(50.0, 100.0),
        salvage_health_threshold=rng.uniform(0.1, 0.5),
        salvage_growth_pct=rng.uniform(30.0, 90.0),
    )

    # Random environment targets
    env = {}
    for z in VALID_ZONE_IDS:
        env[z] = EnvironmentTarget(
            temp_c=round(rng.uniform(14.0, 26.0), 1),
            humidity_pct=round(rng.uniform(40.0, 80.0), 1),
            co2_ppm=round(rng.uniform(600.0, 1500.0), 0),
            par_umol_m2s=round(rng.uniform(100.0, 400.0), 0),
            photoperiod_hours=round(rng.uniform(10.0, 20.0), 1),
        )

    # Random ice mining config
    ice_mining = IceMiningConfig(
        enabled=rng.random() > 0.1,  # 90% chance enabled
        drill_maintenance_interval_sols=rng.randint(2, 10),
        energy_reserve_wh=round(rng.uniform(800.0, 5000.0), 0),
        water_ceiling_L=round(rng.uniform(200.0, 600.0), 0),
        drill_health_maintenance_threshold_pct=round(rng.uniform(15.0, 80.0), 1),
    )

    return StrategyConfig(
        planting_schedule=schedule,
        energy_allocation={"default": default_alloc, "crisis": crisis_alloc},
        irrigation=irrigation,
        irrigation_crisis_multiplier=round(rng.uniform(0.2, 0.8), 2),
        harvest_policy=harvest,
        environment_targets=env,
        filter_maintenance_interval_sols=rng.randint(15, 60),
        filter_health_threshold_pct=round(rng.uniform(30.0, 80.0), 1),
        nutrient_correction=NutrientCorrection(
            ph_tolerance=round(rng.uniform(0.2, 1.0), 2),
            nitrogen_threshold_ppm=round(rng.uniform(60.0, 180.0), 1),
            potassium_threshold_ppm=round(rng.uniform(80.0, 200.0), 1),
        ),
        crisis_response={},
        replant_on_death=rng.random() > 0.3,
        food_shortage_response=FoodShortageResponse(
            min_days_food=round(rng.uniform(3.0, 15.0), 1),
            emergency_crop=rng.choice(["radish", "herbs", "lettuce"]),
        ),
        ice_mining=ice_mining,
    )


def _perturb_float(value: float, rng: random.Random, pct: float) -> float:
    """Perturb a float by +/- pct."""
    delta = value * pct
    return max(0.0, value + rng.uniform(-delta, delta))


def _normalize_energy_alloc(alloc: dict[str, Any]) -> dict[str, Any]:
    """Normalize energy allocation percentages to sum to 100."""
    keys = [
        "heating_pct",
        "lighting_pct",
        "water_recycling_pct",
        "nutrient_pumps_pct",
        "reserve_pct",
    ]
    total = sum(float(alloc.get(k, 0)) for k in keys)
    if total <= 0:
        return alloc
    result = dict(alloc)
    for k in keys:
        result[k] = round(float(alloc.get(k, 0)) / total * 100.0, 1)
    return result


def _perturb_strategy(base: StrategyConfig, rng: random.Random, pct: float) -> StrategyConfig:
    """Create a new StrategyConfig with perturbed parameters."""
    s = deepcopy(base)

    # Perturb planting schedule — aggressively explore different area/timing combos
    new_schedule: list[PlantingEntry] = []
    for entry in s.planting_schedule:
        # 15% chance to drop this entry entirely (explore "skip this crop" strategies)
        if rng.random() < 0.15:
            continue
        sol_shift = rng.randint(-15, 15)
        new_sol = max(0, entry.sol + sol_shift)
        # Wide area perturbation: 1m2 to zone max
        new_area = max(
            1.0,
            min(
                ZONE_AREAS.get(entry.zone_id, 20.0),
                _perturb_float(entry.area_m2, rng, pct * 2.0),  # 2x wider perturbation
            ),
        )
        # 10% chance swap zone, 5% chance swap crop type
        zone_id = entry.zone_id
        crop_type = entry.crop_type
        if rng.random() < 0.10:
            zone_id = rng.choice(VALID_ZONE_IDS)
        if rng.random() < 0.05:
            crop_type = rng.choice(VALID_CROP_TYPES)
        new_schedule.append(
            PlantingEntry(
                sol=new_sol,
                crop_type=crop_type,
                zone_id=zone_id,
                area_m2=round(new_area, 1),
            )
        )
    s.planting_schedule = sorted(new_schedule, key=lambda e: e.sol)

    # Perturb energy allocation
    new_energy: dict[str, Any] = {}
    for alloc_key in ["default", "crisis"]:
        if alloc_key in s.energy_allocation:
            alloc = dict(s.energy_allocation[alloc_key])
            energy_keys = [
                "heating_pct",
                "lighting_pct",
                "water_recycling_pct",
                "nutrient_pumps_pct",
                "reserve_pct",
            ]
            for k in energy_keys:
                alloc[k] = max(1.0, _perturb_float(float(alloc.get(k, 0)), rng, 0.10))
            new_energy[alloc_key] = _normalize_energy_alloc(alloc)
    s.energy_allocation = new_energy

    # Perturb irrigation — wide range (0 to 60 L/sol per zone)
    s.irrigation = {
        z: max(0.0, round(_perturb_float(v, rng, pct * 3.0), 1)) for z, v in s.irrigation.items()
    }
    s.irrigation_crisis_multiplier = max(
        0.3, min(1.0, _perturb_float(s.irrigation_crisis_multiplier, rng, pct))
    )

    # Perturb harvest policy
    hp = s.harvest_policy
    s.harvest_policy = HarvestPolicy(
        min_growth_pct=max(60.0, min(100.0, _perturb_float(hp.min_growth_pct, rng, pct * 0.5))),
        salvage_health_threshold=max(
            0.1, min(0.6, _perturb_float(hp.salvage_health_threshold, rng, pct))
        ),
        salvage_growth_pct=max(40.0, min(95.0, _perturb_float(hp.salvage_growth_pct, rng, pct))),
    )

    # Perturb filter maintenance
    s.filter_maintenance_interval_sols = max(
        10, int(_perturb_float(float(s.filter_maintenance_interval_sols), rng, pct))
    )
    s.filter_health_threshold_pct = max(
        20.0, min(90.0, _perturb_float(s.filter_health_threshold_pct, rng, pct))
    )

    # Perturb nutrient correction
    nc = s.nutrient_correction
    s.nutrient_correction = NutrientCorrection(
        ph_tolerance=max(0.1, min(1.5, _perturb_float(nc.ph_tolerance, rng, pct))),
        nitrogen_threshold_ppm=max(50.0, _perturb_float(nc.nitrogen_threshold_ppm, rng, pct)),
        potassium_threshold_ppm=max(50.0, _perturb_float(nc.potassium_threshold_ppm, rng, pct)),
    )

    # Perturb ice mining parameters
    im = s.ice_mining
    s.ice_mining = IceMiningConfig(
        enabled=(not im.enabled) if rng.random() < 0.05 else im.enabled,  # 5% chance to toggle
        drill_maintenance_interval_sols=max(2, int(_perturb_float(float(im.drill_maintenance_interval_sols), rng, pct))),
        energy_reserve_wh=max(800.0, min(5000.0, _perturb_float(im.energy_reserve_wh, rng, pct))),
        water_ceiling_L=max(200.0, min(600.0, _perturb_float(im.water_ceiling_L, rng, pct))),
        drill_health_maintenance_threshold_pct=max(15.0, min(80.0, _perturb_float(im.drill_health_maintenance_threshold_pct, rng, pct))),
    )

    # Perturb environment targets
    new_env: dict[str, EnvironmentTarget] = {}
    for zone_id, t in s.environment_targets.items():
        new_env[zone_id] = EnvironmentTarget(
            temp_c=max(10.0, min(30.0, _perturb_float(t.temp_c, rng, pct * 0.3))),
            humidity_pct=max(30.0, min(90.0, _perturb_float(t.humidity_pct, rng, pct * 0.3))),
            co2_ppm=max(400.0, min(2000.0, _perturb_float(t.co2_ppm, rng, pct * 0.3))),
            par_umol_m2s=max(50.0, min(500.0, _perturb_float(t.par_umol_m2s, rng, pct * 0.3))),
            photoperiod_hours=max(
                8.0, min(22.0, _perturb_float(t.photoperiod_hours, rng, pct * 0.2))
            ),
        )
    s.environment_targets = new_env

    return s


def _mutate_strategy(
    strategy: StrategyConfig, rng: random.Random, mutation_rate: float
) -> StrategyConfig:
    """Apply Gaussian mutation to all numeric parameters."""
    return _perturb_strategy(strategy, rng, mutation_rate)


def _crossover(
    parent_a: StrategyConfig, parent_b: StrategyConfig, rng: random.Random
) -> StrategyConfig:
    """
    Create a child by mixing parents.

    Takes planting schedule from parent A, energy allocation from parent B.
    """
    child = deepcopy(parent_a)
    child.energy_allocation = deepcopy(parent_b.energy_allocation)
    child.irrigation = deepcopy(parent_b.irrigation)
    child.ice_mining = deepcopy(parent_b.ice_mining)
    return child
