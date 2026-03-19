"""
Simulation engine bridge — environment-aware sys.path setup and engine creation.

All simulation imports are LAZY (inside functions) because sys.path may not be
configured when this module is first imported.

Environment detection:
  - Lambda: AWS_LAMBDA_FUNCTION_NAME is set; PYTHONPATH set by Dockerfile; skip injection
  - Local: inject simulation/ directory onto sys.path using the alias "sim_src" to avoid
    conflicting with fast-sim's own "src" package namespace
"""

from __future__ import annotations

import os
import random
import sys
from pathlib import Path
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    pass  # no top-level simulation imports -- all are lazy

# Module-level cache for lazily-loaded simulation classes
_sim_engine_cls: Any = None
_sim_difficulty_cls: Any = None
_sim_croptype_cls: Any = None
_sim_crisistype_cls: Any = None


def _get_simulation_root() -> Path:
    """Resolve the path to the simulation/ directory."""
    this_file = Path(__file__).resolve()
    # fast-sim/src/engine_bridge.py -> fast-sim/ -> project root -> simulation/
    return this_file.parent.parent.parent / "simulation"


def setup_simulation_path() -> None:
    """
    Set up sys.path and sys.modules for simulation imports in local execution.

    In Lambda, PYTHONPATH is configured by the Dockerfile and this is a no-op.
    Locally, we load simulation sub-modules using importlib and register them
    under their canonical names (src.engine, src.enums, etc.) in sys.modules,
    after temporarily setting sys.path so the simulation's own internal imports
    (from src.xxx) resolve correctly.
    """
    if os.environ.get("AWS_LAMBDA_FUNCTION_NAME"):
        # Lambda: PYTHONPATH already set by Dockerfile. No injection needed.
        return

    sim_root = _get_simulation_root()
    sim_str = str(sim_root)

    # Ensure simulation/ is at the front of sys.path so simulation's own
    # `from src.xxx import` statements resolve to simulation/src/.
    # We remove any existing entry first to avoid duplicates.
    if sim_str in sys.path:
        return  # already set up

    # Temporarily replace the fast-sim src package in sys.modules with a
    # sentinel, then load simulation's src, then restore.
    # Strategy: add simulation root to sys.path at index 0, which means
    # `from src.engine import SimulationEngine` will find simulation/src/engine.py.
    # BUT: Python caches `sys.modules["src"]` = fast-sim/src/__init__.py.
    # We must temporarily remove fast-sim's `src` from sys.modules while
    # loading simulation modules, then restore it afterward.
    #
    # To avoid this dance at every import, we do it ONCE here and register all
    # needed simulation modules under their canonical names in sys.modules.
    _bootstrap_simulation_modules(sim_root, sim_str)


def _bootstrap_simulation_modules(sim_root: Path, sim_str: str) -> None:
    """
    Load simulation modules into sys.modules once, resolving the src namespace conflict.

    Fast-sim owns the 'src' namespace at runtime. Simulation also uses 'src.*' imports
    internally. We resolve this by:
    1. Saving fast-sim's src entries from sys.modules
    2. Inserting simulation root into sys.path at index 0
    3. Clearing fast-sim's src entries so simulation's src.* imports resolve fresh
    4. Import all needed simulation modules (this populates sys.modules["src.*"] with simulation)
    5. Restore fast-sim's src entries
    """
    # Step 1: Save fast-sim src entries
    fast_sim_src_keys = {k: v for k, v in sys.modules.items() if k == "src" or k.startswith("src.")}

    # Step 2: Insert simulation root at index 0
    sys.path.insert(0, sim_str)

    # Step 3: Remove fast-sim src entries so simulation's `from src.xxx import` resolves correctly
    for key in fast_sim_src_keys:
        del sys.modules[key]

    try:
        # Step 4: Import all simulation modules we need (triggers all internal imports)
        import src.engine  # noqa: PLC0415  # type: ignore[import]
        import src.enums  # noqa: PLC0415  # type: ignore[import]
        import src.models.crops  # noqa: PLC0415  # type: ignore[import]
        import src.models.events  # noqa: PLC0415,F401  # type: ignore[import]

        # Register simulation modules under "sim_src.*" aliases for our use
        # so they don't conflict after we restore fast-sim's src
        _sim_modules = {k: v for k, v in sys.modules.items() if k == "src" or k.startswith("src.")}

    finally:
        # Step 5: Restore fast-sim src entries (they take precedence)
        for key in fast_sim_src_keys:
            sys.modules[key] = fast_sim_src_keys[key]

    # Register simulation modules under "sim_src.*" namespace so we can find them later
    for key, mod in _sim_modules.items():
        alias = key.replace("src", "sim_src", 1)
        if alias not in sys.modules:
            sys.modules[alias] = mod

    # Mark as done so we don't bootstrap again
    sys.path  # sim_str already at index 0 - leave it there for simulation's own internal imports
    # but ensure fast-sim src is back in sys.modules (already done in finally)


def _load_sim_classes() -> None:
    """Lazily load and cache simulation classes."""
    global _sim_engine_cls, _sim_difficulty_cls, _sim_croptype_cls, _sim_crisistype_cls

    if _sim_engine_cls is not None:
        return

    setup_simulation_path()

    # Use sim_src aliases registered by bootstrap
    engine_mod = sys.modules.get("sim_src.engine") or sys.modules.get("src.engine")
    enums_mod = sys.modules.get("sim_src.enums") or sys.modules.get("src.enums")

    if engine_mod is None or enums_mod is None:
        raise RuntimeError(
            "Simulation modules not loaded. Did setup_simulation_path() run successfully?"
        )

    _sim_engine_cls = engine_mod.SimulationEngine
    _sim_difficulty_cls = enums_mod.Difficulty
    _sim_croptype_cls = enums_mod.CropType
    _sim_crisistype_cls = enums_mod.CrisisType


def create_engine(
    seed: int = 42,
    difficulty: str = "normal",
    suppress_autonomous: bool = False,
) -> Any:
    """
    Create and initialise a SimulationEngine with deterministic RNG seeding.

    Seeding happens AFTER engine.reset() because reset() -> _init_state()
    re-creates autonomous_events with a hardcoded seed 42, overwriting any
    pre-reset seeding.

    Args:
        seed: RNG seed for deterministic runs.
        difficulty: "easy" | "normal" | "hard".
        suppress_autonomous: If True, replace autonomous_events.tick with a
            no-op so no probabilistic events fire. Used for controlled
            scenario experiments (levels 0-2).

    Returns:
        Initialised SimulationEngine at sol 0 with correct difficulty and seed.
    """
    _load_sim_classes()

    engine = _sim_engine_cls()
    engine.reset(difficulty=_sim_difficulty_cls(difficulty))

    # Seed AFTER reset (reset re-creates autonomous_events with hardcoded seed 42)
    engine.autonomous_events._rng = random.Random(seed)
    random.seed(seed)  # covers crew.py random.random() illness rolls

    if suppress_autonomous:
        # Replace the tick method with a no-op that returns empty list
        engine.autonomous_events.tick = lambda sol, eng: []

    return engine


# Scenario injection map — method name on SimulationEngine for each scenario type
_SCENARIO_METHODS: dict[str, str] = {
    "water_leak": "scenario_water_leak",
    "dust_storm": "scenario_dust_storm",
    "hvac_failure": "scenario_hvac_failure",
    "pathogen": "scenario_pathogen",
    "energy_disruption": "scenario_energy_disruption",
}


def inject_scenario(engine: Any, scenario: str, **kwargs: Any) -> None:
    """Inject a named scenario into the engine."""
    method_name = _SCENARIO_METHODS.get(scenario)
    if method_name is None:
        raise ValueError(f"Unknown scenario: {scenario!r}. Valid: {list(_SCENARIO_METHODS)}")
    method = getattr(engine, method_name)
    method(**kwargs)


def dispatch_action(engine: Any, endpoint: str, body: dict[str, Any]) -> dict[str, Any]:
    """
    Synchronous copy of _dispatch_action from simulation/src/tick_loop.py (lines 191-262).

    Handles all 8 action endpoints identically to the WebSocket-based simulation.
    Includes the flush_solution water deduction path from nutrients/adjust.
    Policy guard: suppress flush during active water crisis.
    """
    _load_sim_classes()

    CropType = _sim_croptype_cls
    CrisisType = _sim_crisistype_cls

    if endpoint == "energy/allocate":
        engine.energy.allocate(body)
        return {"allocation": engine.energy.state.allocation}

    if endpoint == "greenhouse/set_environment":
        zone_id = body.get("zone_id")
        zone_body = {k: v for k, v in body.items() if k != "zone_id"}
        zone = engine.climate.set_zone(zone_id=zone_id, **zone_body)
        return {"zone_id": zone.zone_id, "target_temp_c": zone.target_temp_c}

    if endpoint == "water/set_irrigation":
        zone_id = body["zone_id"]
        liters = body["irrigation_liters_per_sol"]
        engine.water.set_irrigation(zone_id, liters)
        return {"zone_id": zone_id, "irrigation_liters_per_sol": liters}

    if endpoint == "water/maintenance":
        action_name = body.get("action", "clean_filters")
        result = engine.water.maintenance(action_name)
        if result.get("result") == "success":
            engine.scoring.record_preventive_action()
        return result

    if endpoint == "water/mine_ice":
        result = engine.water.mine_ice(
            current_sol=engine.current_sol,
            battery_wh=engine.energy.state.battery_level_wh,
        )
        if result.get("result") == "success":
            engine.energy.state.battery_level_wh = max(
                0.0, engine.energy.state.battery_level_wh - result["energy_cost_wh"]
            )
            engine.scoring.record_preventive_action()
        return result

    if endpoint == "crops/plant":
        crop_type = CropType(body["type"])
        batch = engine.crops.plant(
            current_sol=engine.current_sol,
            crop_type=crop_type,
            zone_id=body["zone_id"],
            area_m2=body["area_m2"],
            batch_name=body.get("batch_name"),
        )
        return {"crop_id": batch.crop_id, "planted_sol": batch.planted_sol}

    if endpoint == "crops/harvest":
        crop_id = body["crop_id"]
        result = engine.crops.harvest(crop_id)
        engine.crew.add_harvest(
            kcal=result["calories_kcal"],
            protein_g=result["protein_g"],
            has_micronutrients=result["provides_micronutrients"],
        )
        engine.scoring.record_harvest(result["yield_kg"])
        return result

    if endpoint == "crops/remove":
        crop_id = body["crop_id"]
        reason = body.get("reason", "")
        result = engine.crops.remove(crop_id, reason)
        engine.scoring.record_crop_removed(result["waste_kg"])
        return result

    if endpoint == "nutrients/adjust":
        zone_id = body["zone_id"]

        # Policy guard: suppress flush_solution during active water crises
        want_flush = body.get("flush_solution", False)
        active_crisis_types = {c.type for c in engine.events.active_crises()}
        water_crisis_active = (
            CrisisType.WATER_SHORTAGE in active_crisis_types
            or CrisisType.WATER_RECYCLING_DECLINE in active_crisis_types
        )
        do_flush = want_flush and not water_crisis_active

        engine.nutrients.adjust(
            zone_id=zone_id,
            target_ph=body.get("target_ph"),
            nitrogen_boost=body.get("nitrogen_boost", False),
            potassium_boost=body.get("potassium_boost", False),
            flush_solution=do_flush,
        )
        if do_flush:
            engine.water.state.reservoir_liters = max(
                0.0, engine.water.state.reservoir_liters - 10.0
            )
        return {"zone_id": zone_id, "status": "adjusted"}

    raise ValueError(f"Unknown action endpoint: {endpoint}")
