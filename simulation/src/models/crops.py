"""
Crop Growth Sub-Model — PCSE-style state/rate separation.

Each planted crop is a CropBatch. The CropModel holds all active batches and
runs the growth & stress logic each sol.

Growth model (simplified Wageningen-style):
  - Linear development: age_days increments by 1 per sol (slowed by CO₂/light stress)
  - Water-limited growth: soil moisture affects health
  - Nutrient-limited: N concentration in zone solution affects health
  - Temperature response: cardinal temperature model (Tb, T_opt_low, T_opt_high, Tc)
  - Health [0-1]: degraded by stress, never self-repairs without agent action
  - Yield = base_yield_kg_per_m2 × area_m2 × health at time of harvest
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass, field
from typing import TYPE_CHECKING

from src.catalog import CROP_CATALOG
from src.constants import (
    STRESS_EC_MODERATE,
    STRESS_EC_SEVERE,
    STRESS_K_DEFICIENCY_PPM,
    STRESS_PAR_CRITICAL_LOW,
    STRESS_PAR_HIGH,
    STRESS_PAR_LOW,
    STRESS_PH_CRITICAL_HIGH,
    STRESS_PH_CRITICAL_LOW,
    STRESS_PH_OPTIMAL_HIGH,
    STRESS_PH_OPTIMAL_LOW,
)
from src.enums import CropType

if TYPE_CHECKING:
    from src.models.climate import ClimateModel
    from src.models.nutrients import NutrientModel
    from src.models.water import WaterModel


# Default seed stock per crop type
_DEFAULT_SEEDS: dict[CropType, int] = {
    CropType.LETTUCE: 200,
    CropType.POTATO: 80,
    CropType.RADISH: 300,
    CropType.BEANS: 120,
    CropType.HERBS: 250,
}


@dataclass
class StressIndicator:
    type: str
    since_sol: int
    severity: float  # 0.0 – 1.0


@dataclass
class CropBatch:
    crop_id: str
    crop_type: CropType
    zone_id: str
    planted_sol: int
    area_m2: float
    health: float = 1.0  # 0 – 1 (1 = perfect)
    age_days: int = 0  # sols since planting
    soil_moisture_pct: float = 60.0
    stress_indicators: list[StressIndicator] = field(default_factory=list)
    is_bolting: bool = False  # True once bolting triggered (permanent, lettuce only)
    # Internal water tracking
    _soil_water_L: float = field(default=0.0, repr=False)

    def __post_init__(self) -> None:
        # Set initial soil water proportional to area (capacity = area_m2 × 10 L)
        capacity = self.area_m2 * 10.0
        self._soil_water_L = capacity * self.soil_moisture_pct / 100.0

    # ------------------------------------------------------------------ helpers

    @property
    def growth_days(self) -> int:
        return CROP_CATALOG[self.crop_type]["growth_days"]

    @property
    def growth_pct(self) -> float:
        return round(min(100.0, self.age_days / self.growth_days * 100.0), 1)

    @property
    def is_ready(self) -> bool:
        return self.age_days >= self.growth_days

    def estimated_yield_kg(self) -> float:
        base = CROP_CATALOG[self.crop_type]["yield_kg_per_m2"] * self.area_m2
        return round(base * self.health * self.growth_pct / 100.0, 2)

    def estimated_calories_kcal(self) -> float:
        yield_kg = self.estimated_yield_kg()
        kcal_per_100g = CROP_CATALOG[self.crop_type]["kcal_per_100g"]
        return round(
            yield_kg * kcal_per_100g * 10.0, 0
        )  # kg → kcal: ×10 (since kcal/100g × 1000g/kg / 100)


@dataclass
class CropRates:
    age_increment: dict[str, int] = field(default_factory=dict)
    d_health: dict[str, float] = field(default_factory=dict)


class CropModel:
    """
    State variables  : CropBatch per id (health, age_days, soil_moisture_pct)
    Rate variables   : d_health, age_increment
    """

    def __init__(self) -> None:
        self.batches: dict[str, CropBatch] = {}
        self.rates = CropRates()
        self.seeds_remaining: dict[CropType, int] = dict(_DEFAULT_SEEDS)
        self._total_area_used: dict[str, float] = {}  # zone_id → m²

    # ------------------------------------------------------------------
    # PCSE lifecycle
    # ------------------------------------------------------------------

    def calc_rates(
        self,
        current_sol: int,
        climate: ClimateModel,
        water: WaterModel,
        nutrients: NutrientModel,
    ) -> None:
        """Phase 1 — compute growth increments and health deltas."""
        # Build per-zone total crop area for irrigation distribution
        zone_crop_area: dict[str, float] = {}
        for b in self.batches.values():
            zone_crop_area[b.zone_id] = zone_crop_area.get(b.zone_id, 0.0) + b.area_m2

        for batch_id, batch in self.batches.items():
            zone = climate.state.get(batch.zone_id)
            n_state = nutrients.state.get(batch.zone_id)
            catalog = CROP_CATALOG[batch.crop_type]
            d_health = 0.0
            stressors: list[StressIndicator] = []

            # ── Soil moisture update (rate calc) ──────────────────────
            capacity_L = batch.area_m2 * 10.0
            # Water consumed by crop this sol
            consumed_L = catalog["water_L_per_m2_per_sol"] * batch.area_m2
            # Irrigation share: zone setting distributed by crop area fraction
            total_zone_area = zone_crop_area.get(batch.zone_id, batch.area_m2)
            irrigation_zone_L = water.state.irrigation_settings.get(batch.zone_id, 0.0)
            irrigation_received = (
                irrigation_zone_L * batch.area_m2 / total_zone_area
                if total_zone_area > 0
                else 0.0
            )
            new_water_L = max(
                0.0,
                min(capacity_L, batch._soil_water_L + irrigation_received - consumed_L),
            )
            new_moisture_pct = new_water_L / capacity_L * 100.0

            # ── Stress checks ──────────────────────────────────────────
            # Drought
            if new_moisture_pct < 15.0:
                d_health -= 0.15
                stressors.append(StressIndicator("drought_stress", current_sol, 0.8))
            # Overwatering / root hypoxia
            elif new_moisture_pct > 90.0:
                d_health -= 0.10
                stressors.append(StressIndicator("root_hypoxia", current_sol, 0.5))

            # Temperature stress (zone actual temp)
            if zone:
                temp = zone.temp_c
                t_min, t_opt_low, t_opt_high, t_max = catalog["temp_response"]
                if temp < t_min or temp > t_max:
                    d_health -= 0.20
                    label = "cold_stress" if temp < t_min else "heat_stress"
                    stressors.append(StressIndicator(label, current_sol, 1.0))
                elif temp < t_opt_low:
                    d_health -= 0.05
                    stressors.append(StressIndicator("cold_stress", current_sol, 0.3))
                elif temp > t_opt_high:
                    d_health -= 0.08
                    label = "heat_stress"
                    if batch.crop_type == CropType.LETTUCE and temp > 25.0:
                        label = "bolting_risk"
                        batch.is_bolting = True  # permanent: bolted lettuce is inedible
                    stressors.append(StressIndicator(label, current_sol, 0.4))

                # CO₂ imbalance
                if zone.co2_ppm < 500.0:
                    stressors.append(StressIndicator("co2_imbalance", current_sol, 0.3))

                # High humidity → fungal risk
                if zone.humidity_pct > 85.0:
                    d_health -= 0.05
                    stressors.append(StressIndicator("fungal_risk", current_sol, 0.4))

                # PAR / light stress
                par = zone.par_umol_m2s
                if par < STRESS_PAR_CRITICAL_LOW:
                    d_health -= 0.10
                    stressors.append(
                        StressIndicator("light_deficiency", current_sol, 1.0)
                    )
                elif par < STRESS_PAR_LOW:
                    d_health -= 0.05
                    stressors.append(
                        StressIndicator("light_deficiency", current_sol, 0.5)
                    )
                elif par > STRESS_PAR_HIGH:
                    d_health -= 0.06
                    stressors.append(StressIndicator("light_excess", current_sol, 0.4))

            # N-deficiency
            if n_state and n_state.nitrogen_ppm < 50.0:
                d_health -= 0.10
                stressors.append(StressIndicator("n_deficiency", current_sol, 0.6))

            # K-deficiency
            if n_state and n_state.potassium_ppm < STRESS_K_DEFICIENCY_PPM:
                d_health -= 0.08
                stressors.append(StressIndicator("k_deficiency", current_sol, 0.5))

            # Salinity / EC stress
            if n_state:
                ec = n_state.solution_ec_ms_cm
                if ec > STRESS_EC_SEVERE:
                    d_health -= 0.15
                    stressors.append(
                        StressIndicator("salinity_stress", current_sol, 1.0)
                    )
                elif ec > STRESS_EC_MODERATE:
                    d_health -= 0.07
                    stressors.append(
                        StressIndicator("salinity_stress", current_sol, 0.5)
                    )

            # pH imbalance
            if n_state:
                ph = n_state.solution_ph
                if ph < STRESS_PH_CRITICAL_LOW or ph > STRESS_PH_CRITICAL_HIGH:
                    d_health -= 0.08
                    stressors.append(StressIndicator("ph_imbalance", current_sol, 0.6))
                elif ph < STRESS_PH_OPTIMAL_LOW or ph > STRESS_PH_OPTIMAL_HIGH:
                    d_health -= 0.03
                    stressors.append(StressIndicator("ph_imbalance", current_sol, 0.2))

            # Age increment: stalls on CO₂ < 500 ppm or near-darkness (PAR < critical)
            age_inc = 1
            if zone and (
                zone.co2_ppm < 500.0 or zone.par_umol_m2s < STRESS_PAR_CRITICAL_LOW
            ):
                age_inc = 0  # growth stalled

            self.rates.age_increment[batch_id] = age_inc
            self.rates.d_health[batch_id] = d_health
            # Store computed values for integrate phase
            batch._soil_water_L = new_water_L
            batch.soil_moisture_pct = round(new_moisture_pct, 1)
            batch.stress_indicators = stressors  # type: ignore[assignment]

    def integrate(self) -> list[str]:
        """Phase 2 — apply rates. Returns list of crop_ids that died this sol."""
        dead: list[str] = []
        for batch_id, batch in list(self.batches.items()):
            batch.age_days += self.rates.age_increment.get(batch_id, 1)
            new_health = batch.health + self.rates.d_health.get(batch_id, 0.0)
            batch.health = round(max(0.0, min(1.0, new_health)), 3)

            if batch.health <= 0.0:
                dead.append(batch_id)
                self._release_area(batch)
                del self.batches[batch_id]

        return dead

    # ------------------------------------------------------------------
    # Agent actions
    # ------------------------------------------------------------------

    def plant(
        self,
        current_sol: int,
        crop_type: CropType,
        zone_id: str,
        area_m2: float,
        batch_name: str | None = None,
    ) -> CropBatch:
        """Plant a new batch. Raises ValueError if insufficient seeds or area."""
        if self.seeds_remaining.get(crop_type, 0) <= 0:
            raise ValueError(f"No seeds remaining for {crop_type}")

        crop_id = batch_name or f"{crop_type.value}_{str(uuid.uuid4())[:6]}"
        batch = CropBatch(
            crop_id=crop_id,
            crop_type=crop_type,
            zone_id=zone_id,
            planted_sol=current_sol,
            area_m2=area_m2,
        )
        self.batches[crop_id] = batch
        self.seeds_remaining[crop_type] = max(0, self.seeds_remaining[crop_type] - 1)
        self._total_area_used[zone_id] = (
            self._total_area_used.get(zone_id, 0.0) + area_m2
        )
        return batch

    def harvest(self, crop_id: str) -> dict:
        """
        Harvest a batch. Returns yield dict with kcal, protein_g, quality etc.
        Does NOT require the crop to be fully grown — early harvest possible.
        """
        if crop_id not in self.batches:
            raise KeyError(f"Crop {crop_id!r} not found")

        batch = self.batches.pop(crop_id)
        catalog = CROP_CATALOG[batch.crop_type]
        self._release_area(batch)

        base_yield_kg = catalog["yield_kg_per_m2"] * batch.area_m2
        actual_yield_kg = round(
            base_yield_kg * batch.health * min(1.0, batch.growth_pct / 100.0), 3
        )

        # Bolting: lettuce enters reproductive phase — leaves become bitter/inedible
        if batch.is_bolting:
            actual_yield_kg = round(actual_yield_kg * 0.1, 3)

        kcal = round(actual_yield_kg * catalog["kcal_per_100g"] * 10.0, 0)
        protein_g = round(actual_yield_kg * catalog["protein_per_100g_g"] * 10.0, 0)
        vitamin_c_mg = round(actual_yield_kg * 20.0, 0)  # approximate
        potassium_mg = round(actual_yield_kg * 430.0, 0)  # approximate

        return {
            "crop_id": crop_id,
            "crop_type": batch.crop_type.value,
            "yield_kg": actual_yield_kg,
            "calories_kcal": kcal,
            "protein_g": protein_g,
            "vitamin_c_mg": vitamin_c_mg,
            "potassium_mg": potassium_mg,
            "quality": round(batch.health, 3),
            "area_freed_m2": batch.area_m2,
            "provides_micronutrients": catalog["provides_micronutrients"],
            "age_days": batch.age_days,
            "growth_pct": batch.growth_pct,
            "was_bolting": batch.is_bolting,
        }

    def remove(self, crop_id: str, reason: str = "") -> dict:
        """Remove a crop early (disease, strategic reallocation, etc.)."""
        if crop_id not in self.batches:
            raise KeyError(f"Crop {crop_id!r} not found")

        batch = self.batches.pop(crop_id)
        self._release_area(batch)
        catalog = CROP_CATALOG[batch.crop_type]
        waste_kg = round(
            catalog["yield_kg_per_m2"] * batch.area_m2 * batch.health * 0.3, 3
        )
        return {"area_freed_m2": batch.area_m2, "waste_kg": waste_kg, "reason": reason}

    # ------------------------------------------------------------------
    # Scenario injection
    # ------------------------------------------------------------------

    def inject_pathogen(
        self, crop_id: str, current_sol: int | None = None
    ) -> CropBatch:
        if crop_id not in self.batches:
            raise KeyError(f"Crop {crop_id!r} not found")
        batch = self.batches[crop_id]
        batch.health = 0.10
        since_sol = 0 if current_sol is None else current_sol
        batch.stress_indicators.append(  # type: ignore[attr-defined]
            StressIndicator("pathogen_outbreak", since_sol, 1.0)
        )
        return batch

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    def zone_used_area(self, zone_id: str) -> float:
        return sum(b.area_m2 for b in self.batches.values() if b.zone_id == zone_id)

    def total_planted_area(self) -> float:
        return sum(b.area_m2 for b in self.batches.values())

    def _release_area(self, batch: CropBatch) -> None:
        self._total_area_used[batch.zone_id] = max(
            0.0,
            self._total_area_used.get(batch.zone_id, 0.0) - batch.area_m2,
        )
