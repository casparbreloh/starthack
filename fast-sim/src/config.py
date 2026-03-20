"""
Strategy configuration schema for fast-sim policy sweeps.

StrategyConfig defines all parameterizable dimensions of the policy engine.
RunConfig packages a strategy with run metadata.
DEFAULT_STRATEGY provides a sensible baseline based on the crop catalog.
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from typing import Any

# ---------------------------------------------------------------------------
# StrategyConfig — all parameterizable policy dimensions
# ---------------------------------------------------------------------------


@dataclass
class EnergyAllocation:
    """Energy allocation percentages (must sum to ~100)."""

    heating_pct: float = 47.0
    lighting_pct: float = 30.0
    water_recycling_pct: float = 12.0
    nutrient_pumps_pct: float = 5.0
    reserve_pct: float = 6.0


@dataclass
class HarvestPolicy:
    """When to harvest normally vs. salvage harvest."""

    min_growth_pct: float = 95.0  # harvest when age_days >= growth_days * 0.95
    salvage_health_threshold: float = 0.3  # salvage if health drops below this
    salvage_growth_pct: float = 75.0  # salvage only if partially grown


@dataclass
class NutrientCorrection:
    """Thresholds for nutrient intervention."""

    ph_tolerance: float = 0.5  # correct pH if drift exceeds this from optimal (6.0)
    nitrogen_threshold_ppm: float = 120.0  # boost N when below this
    potassium_threshold_ppm: float = 150.0  # boost K when below this


@dataclass
class FoodShortageResponse:
    """Emergency crop planting when food is low."""

    min_days_food: float = 5.0  # plant emergency crops when food buffer below this
    emergency_crop: str = "radish"  # fastest crop (25-sol cycle)




@dataclass
class CrisisInjection:
    """A single crisis to inject at a specific sol."""

    sol: int
    scenario: str  # "water_leak" | "dust_storm" | "hvac_failure" | "pathogen" | "energy_disruption"
    kwargs: dict[str, Any] = field(default_factory=dict)


@dataclass
class ScenarioConfig:
    """Controls crisis injection for controlled experiments.

    Levels:
      0 — no autonomous events, no injected crises (pure baseline)
      1 — no autonomous events, 1 injected crisis at a random sol
      2 — no autonomous events, 2-3 injected crises
      3 — full autonomous events (original behavior)
    """

    level: int = 3  # default: full autonomous (backwards compatible)
    injections: list[CrisisInjection] = field(default_factory=list)

    @property
    def suppress_autonomous(self) -> bool:
        return self.level < 3


@dataclass
class IceMiningConfig:
    """Ice mining parameters for drill-based water replenishment."""

    enabled: bool = True
    drill_maintenance_interval_sols: int = 4  # maintain every 4 sols to keep drill 80-100%
    energy_reserve_wh: float = 2000.0  # skip mining when battery below this
    water_ceiling_L: float = 550.0  # skip mining when reservoir above this
    drill_health_maintenance_threshold_pct: float = 40.0  # emergency maintenance trigger

@dataclass
class EnvironmentTarget:
    """Target environment parameters for a zone."""

    temp_c: float = 21.0
    humidity_pct: float = 60.0
    co2_ppm: float = 1000.0
    par_umol_m2s: float = 220.0
    photoperiod_hours: float = 16.0


@dataclass
class PlantingEntry:
    """A single entry in the planting schedule."""

    sol: int
    crop_type: str
    zone_id: str
    area_m2: float


@dataclass
class StrategyConfig:
    """
    Complete parameterizable strategy for the fast-sim policy engine.

    All fields are JSON-serializable for SQS fan-out and S3 result storage.
    """

    planting_schedule: list[PlantingEntry] = field(default_factory=list)
    energy_allocation: dict[str, Any] = field(default_factory=dict)
    irrigation: dict[str, float] = field(default_factory=dict)
    irrigation_crisis_multiplier: float = 0.7
    harvest_policy: HarvestPolicy = field(default_factory=HarvestPolicy)
    environment_targets: dict[str, EnvironmentTarget] = field(default_factory=dict)
    filter_maintenance_interval_sols: int = 40
    filter_health_threshold_pct: float = 60.0
    nutrient_correction: NutrientCorrection = field(default_factory=NutrientCorrection)
    crisis_response: dict[str, Any] = field(default_factory=dict)
    replant_on_death: bool = True
    food_shortage_response: FoodShortageResponse = field(default_factory=FoodShortageResponse)
    ice_mining: IceMiningConfig = field(default_factory=IceMiningConfig)
    scenario: ScenarioConfig = field(default_factory=ScenarioConfig)

    def to_dict(self) -> dict[str, Any]:
        """Serialize to a JSON-compatible dictionary."""
        return {
            "planting_schedule": [
                {
                    "sol": e.sol,
                    "crop_type": e.crop_type,
                    "zone_id": e.zone_id,
                    "area_m2": e.area_m2,
                }
                for e in self.planting_schedule
            ],
            "energy_allocation": self.energy_allocation,
            "irrigation": self.irrigation,
            "irrigation_crisis_multiplier": self.irrigation_crisis_multiplier,
            "harvest_policy": {
                "min_growth_pct": self.harvest_policy.min_growth_pct,
                "salvage_health_threshold": self.harvest_policy.salvage_health_threshold,
                "salvage_growth_pct": self.harvest_policy.salvage_growth_pct,
            },
            "environment_targets": {
                zone_id: {
                    "temp_c": t.temp_c,
                    "humidity_pct": t.humidity_pct,
                    "co2_ppm": t.co2_ppm,
                    "par_umol_m2s": t.par_umol_m2s,
                    "photoperiod_hours": t.photoperiod_hours,
                }
                for zone_id, t in self.environment_targets.items()
            },
            "filter_maintenance_interval_sols": self.filter_maintenance_interval_sols,
            "filter_health_threshold_pct": self.filter_health_threshold_pct,
            "nutrient_correction": {
                "ph_tolerance": self.nutrient_correction.ph_tolerance,
                "nitrogen_threshold_ppm": self.nutrient_correction.nitrogen_threshold_ppm,
                "potassium_threshold_ppm": self.nutrient_correction.potassium_threshold_ppm,
            },
            "crisis_response": self.crisis_response,
            "replant_on_death": self.replant_on_death,
            "food_shortage_response": {
                "min_days_food": self.food_shortage_response.min_days_food,
                "emergency_crop": self.food_shortage_response.emergency_crop,
            },
            "ice_mining": {
                "enabled": self.ice_mining.enabled,
                "drill_maintenance_interval_sols": self.ice_mining.drill_maintenance_interval_sols,
                "energy_reserve_wh": self.ice_mining.energy_reserve_wh,
                "water_ceiling_L": self.ice_mining.water_ceiling_L,
                "drill_health_maintenance_threshold_pct": self.ice_mining.drill_health_maintenance_threshold_pct,
            },
            "scenario": {
                "level": self.scenario.level,
                "injections": [
                    {"sol": inj.sol, "scenario": inj.scenario, "kwargs": inj.kwargs}
                    for inj in self.scenario.injections
                ],
            },
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> StrategyConfig:
        """Deserialize from a JSON-compatible dictionary."""
        cfg = cls()
        cfg.planting_schedule = [
            PlantingEntry(
                sol=e["sol"],
                crop_type=e["crop_type"],
                zone_id=e["zone_id"],
                area_m2=e["area_m2"],
            )
            for e in data.get("planting_schedule", [])
        ]
        cfg.energy_allocation = data.get("energy_allocation", {})
        cfg.irrigation = {k: float(v) for k, v in data.get("irrigation", {}).items()}
        cfg.irrigation_crisis_multiplier = float(data.get("irrigation_crisis_multiplier", 0.7))
        hp = data.get("harvest_policy", {})
        cfg.harvest_policy = HarvestPolicy(
            min_growth_pct=float(hp.get("min_growth_pct", 95.0)),
            salvage_health_threshold=float(hp.get("salvage_health_threshold", 0.3)),
            salvage_growth_pct=float(hp.get("salvage_growth_pct", 75.0)),
        )
        cfg.environment_targets = {
            zone_id: EnvironmentTarget(
                temp_c=float(t.get("temp_c", 21.0)),
                humidity_pct=float(t.get("humidity_pct", 60.0)),
                co2_ppm=float(t.get("co2_ppm", 1000.0)),
                par_umol_m2s=float(t.get("par_umol_m2s", 220.0)),
                photoperiod_hours=float(t.get("photoperiod_hours", 16.0)),
            )
            for zone_id, t in data.get("environment_targets", {}).items()
        }
        cfg.filter_maintenance_interval_sols = int(data.get("filter_maintenance_interval_sols", 40))
        cfg.filter_health_threshold_pct = float(data.get("filter_health_threshold_pct", 60.0))
        nc = data.get("nutrient_correction", {})
        cfg.nutrient_correction = NutrientCorrection(
            ph_tolerance=float(nc.get("ph_tolerance", 0.5)),
            nitrogen_threshold_ppm=float(nc.get("nitrogen_threshold_ppm", 120.0)),
            potassium_threshold_ppm=float(nc.get("potassium_threshold_ppm", 150.0)),
        )
        cfg.crisis_response = data.get("crisis_response", {})
        cfg.replant_on_death = bool(data.get("replant_on_death", True))
        fsr = data.get("food_shortage_response", {})
        cfg.food_shortage_response = FoodShortageResponse(
            min_days_food=float(fsr.get("min_days_food", 5.0)),
            emergency_crop=str(fsr.get("emergency_crop", "radish")),
        )
        im = data.get("ice_mining", {})
        cfg.ice_mining = IceMiningConfig(
            enabled=bool(im.get("enabled", True)),
            drill_maintenance_interval_sols=int(im.get("drill_maintenance_interval_sols", 4)),
            energy_reserve_wh=float(im.get("energy_reserve_wh", 2000.0)),
            water_ceiling_L=float(im.get("water_ceiling_L", 550.0)),
            drill_health_maintenance_threshold_pct=float(im.get("drill_health_maintenance_threshold_pct", 40.0)),
        )
        sc = data.get("scenario", {})
        cfg.scenario = ScenarioConfig(
            level=int(sc.get("level", 3)),
            injections=[
                CrisisInjection(
                    sol=int(inj["sol"]),
                    scenario=str(inj["scenario"]),
                    kwargs=dict(inj.get("kwargs", {})),
                )
                for inj in sc.get("injections", [])
            ],
        )
        return cfg


# ---------------------------------------------------------------------------
# RunConfig — wraps strategy with run metadata
# ---------------------------------------------------------------------------


@dataclass
class RunConfig:
    """
    A single simulation run specification.

    difficulty is str (not Difficulty enum) for JSON serialization.
    engine_bridge.create_engine() coerces via Difficulty(difficulty) at call time.
    """

    strategy: StrategyConfig
    seed: int
    difficulty: str  # "easy" | "normal" | "hard" -- kept as str for JSON round-trip
    run_id: str
    wave_id: str

    def to_dict(self) -> dict[str, Any]:
        return {
            "strategy": self.strategy.to_dict(),
            "seed": self.seed,
            "difficulty": self.difficulty,
            "run_id": self.run_id,
            "wave_id": self.wave_id,
        }

    def to_json(self) -> str:
        return json.dumps(self.to_dict())

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> RunConfig:
        return cls(
            strategy=StrategyConfig.from_dict(data["strategy"]),
            seed=int(data["seed"]),
            difficulty=str(data["difficulty"]),
            run_id=str(data["run_id"]),
            wave_id=str(data["wave_id"]),
        )

    @classmethod
    def from_json(cls, json_str: str) -> RunConfig:
        return cls.from_dict(json.loads(json_str))


# ---------------------------------------------------------------------------
# DEFAULT_STRATEGY — baseline heuristics derived from crop catalog (ice mining era)
# ---------------------------------------------------------------------------
#
# Zone areas:
#   A = 12 m2  (lettuce, small crops)
#   B = 18 m2  (beans, medium crops)
#   C = 20 m2  (potatoes, caloric backbone)
#
# Water budget: 600L initial + ice mining (~10 L/sol average, replenishable via ice mining).
# Net daily use = 0.84 + 0.2*irrigation L/sol; mining adds ~10 L/sol on average.
# Strategy: moderate irrigation with ice mining sustaining water supply.
# The sweeper will optimize these parameters.
#
# Crop cycles:
#   Lettuce: 35 sols  Potato: 90 sols  Radish: 25 sols  Beans: 60 sols  Herbs: 15 sols
#
# Rotation strategy:
#   - Sol 0: plant potatoes (C, 12m2), beans (B, 10m2), staggered lettuce (A, 3x3m2)
#   - Increased areas now that water is replenishable via ice mining
#   - Lettuce staggered for continuous micronutrient supply


def _build_default_planting_schedule() -> list[PlantingEntry]:
    """Build the default planting rotation for 450 sols.

    Maximizes caloric output by filling all zone capacity:
      Zone C (20m²): potatoes — highest kcal/m²/sol (128 kcal/m²/sol)
      Zone B (18m²): beans — protein source + decent calories (83 kcal/m²/sol)
      Zone A (12m²): 9m² staggered lettuce (micronutrients) + 3m² radish (emergency buffer)

    Water demand: A=22.5+4.5=27, B=39.6, C=40 → total 106.6 L/sol
    Ice mining sustains ~10 L/sol + recycling covers rest.
    """
    schedule: list[PlantingEntry] = []

    # --- Zone C: Potatoes (90-sol cycle, 16m2 — water: 32 L/sol) ---
    # 16m² balances yield vs water sustainability (20m² causes water stress)
    for sol in range(0, 450, 90):
        schedule.append(PlantingEntry(sol=sol, crop_type="potato", zone_id="C", area_m2=16.0))

    # --- Zone B: Beans (60-sol cycle, 14m2 — water: 30.8 L/sol) ---
    for sol in range(0, 450, 60):
        schedule.append(PlantingEntry(sol=sol, crop_type="beans", zone_id="B", area_m2=14.0))

    # --- Zone A: Lettuce — 3 staggered batches of 3m2 each (water: 22.5 L/sol total) ---
    for offset in [0, 5, 10]:
        for sol in range(offset, 450, 35):
            schedule.append(PlantingEntry(sol=sol, crop_type="lettuce", zone_id="A", area_m2=3.0))

    # --- Zone A: Small radish batch (3m2 — water: 4.5 L/sol) ---
    for sol in range(0, 450, 25):
        schedule.append(PlantingEntry(sol=sol, crop_type="radish", zone_id="A", area_m2=3.0))

    return sorted(schedule, key=lambda e: e.sol)


DEFAULT_STRATEGY = StrategyConfig(
    planting_schedule=_build_default_planting_schedule(),
    energy_allocation={
        "default": {
            "heating_pct": 47.0,
            "lighting_pct": 28.0,  # reduced by 2% to fund larger reserve for ice mining
            "water_recycling_pct": 12.0,
            "nutrient_pumps_pct": 5.0,
            "reserve_pct": 8.0,  # reserve must cover ice mining energy cost (800 Wh/sol)
        },
        "crisis": {
            "heating_pct": 55.0,
            "lighting_pct": 13.0,  # reduced by 2% to fund larger reserve
            "water_recycling_pct": 15.0,
            "nutrient_pumps_pct": 5.0,
            "reserve_pct": 12.0,  # reserve must cover ice mining energy cost (800 Wh/sol)
        },
    },
    # Water budget: 600L initial + ice mining (~14 L/sol).
    # Sustainable irrigation: ~66L/sol (after recycling + mining breakeven).
    # Zone A: lettuce 2.5×9m²=22.5 + radish 1.5×3m²=4.5 = 27 L/sol
    # Zone B: beans 2.2×14m² = 30.8 L/sol
    # Zone C: potato 2.0×16m² = 32 L/sol
    # Total ~90 L/sol — slight deficit but reservoir stays high enough.
    irrigation={"A": 27.0, "B": 31.0, "C": 32.0},
    irrigation_crisis_multiplier=0.6,
    harvest_policy=HarvestPolicy(
        min_growth_pct=85.0,  # harvest at 85% to get beans (sol 51) and potatoes (sol 77) earlier
        salvage_health_threshold=0.3,
        salvage_growth_pct=75.0,
    ),
    environment_targets={
        "A": EnvironmentTarget(
            temp_c=18.0,  # lettuce prefers cooler
            humidity_pct=65.0,
            co2_ppm=1000.0,
            par_umol_m2s=200.0,
            photoperiod_hours=16.0,
        ),
        "B": EnvironmentTarget(
            temp_c=22.0,  # beans like warmer
            humidity_pct=60.0,
            co2_ppm=1000.0,
            par_umol_m2s=280.0,
            photoperiod_hours=16.0,
        ),
        "C": EnvironmentTarget(
            temp_c=18.0,  # potato: 15-20C optimal
            humidity_pct=60.0,
            co2_ppm=1000.0,
            par_umol_m2s=250.0,
            photoperiod_hours=16.0,
        ),
    },
    filter_maintenance_interval_sols=40,
    filter_health_threshold_pct=60.0,
    nutrient_correction=NutrientCorrection(
        ph_tolerance=0.5,
        nitrogen_threshold_ppm=120.0,
        potassium_threshold_ppm=150.0,
    ),
    crisis_response={
        "energy_disruption": {
            "reduce_lighting_pct": 15.0,
            "increase_reserve_pct": 10.0,
        },
        "water_shortage": {
            "reduce_irrigation_pct": 40.0,
            "suppress_flush": True,
        },
        "water_recycling_decline": {
            "reduce_irrigation_pct": 30.0,
            "suppress_flush": True,
        },
        "temperature_failure": {
            "increase_heating_pct": 10.0,
        },
        "dust_storm": {
            "reduce_lighting_pct": 0.0,  # no action — solar already reduced
            "increase_reserve_pct": 5.0,
        },
    },
    replant_on_death=True,
    food_shortage_response=FoodShortageResponse(
        min_days_food=5.0,
        emergency_crop="radish",
    ),
    ice_mining=IceMiningConfig(),
)
