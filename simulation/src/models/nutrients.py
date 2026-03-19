"""
Nutrient System Sub-Model.

Tracks per-zone hydroponic nutrient solution: pH, EC, dissolved O₂,
and macro-nutrients (N, P, K, Ca). Nutrients are consumed by crops
and replenished by agent actions.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import TYPE_CHECKING

from src.constants import (
    INITIAL_NUTRIENT_STOCK_PCT,
    NUTRIENT_RESTOCK_AMOUNT_PCT,
    NUTRIENT_STOCK_DEGRADATION_PCT_PER_SOL,
    TARGET_CA_PPM,
    TARGET_DO_PPM,
    TARGET_EC,
    TARGET_K_PPM,
    TARGET_N_PPM,
    TARGET_P_PPM,
    TARGET_PH,
    ZONE_AREAS_M2,
)

if TYPE_CHECKING:
    from src.models.crops import CropModel


@dataclass
class ZoneNutrients:
    zone_id: str
    solution_ph: float = TARGET_PH
    solution_ec_ms_cm: float = TARGET_EC
    solution_temp_c: float = 19.5
    dissolved_o2_ppm: float = TARGET_DO_PPM
    nitrogen_ppm: float = TARGET_N_PPM
    phosphorus_ppm: float = TARGET_P_PPM
    potassium_ppm: float = TARGET_K_PPM
    calcium_ppm: float = TARGET_CA_PPM
    magnesium_ppm: float = 35.0
    # Setpoints
    target_ph: float = TARGET_PH
    target_ec_ms_cm: float = TARGET_EC
    nitrogen_boost: bool = False
    potassium_boost: bool = False


@dataclass
class NutrientRates:
    d_nitrogen: dict[str, float] = field(default_factory=dict)
    d_phosphorus: dict[str, float] = field(default_factory=dict)
    d_potassium: dict[str, float] = field(default_factory=dict)


class NutrientModel:
    """
    State variables  : ZoneNutrients per zone + nutrient_stock_remaining_pct
    Rate variables   : d_N, d_P, d_K per zone per sol
    """

    def __init__(self) -> None:
        self.state: dict[str, ZoneNutrients] = {
            z: ZoneNutrients(zone_id=z) for z in ZONE_AREAS_M2
        }
        self.rates = NutrientRates()
        self.stock_remaining_pct: float = INITIAL_NUTRIENT_STOCK_PCT
        self.days_of_stock_remaining: float = (
            INITIAL_NUTRIENT_STOCK_PCT / NUTRIENT_STOCK_DEGRADATION_PCT_PER_SOL
        )

    # ------------------------------------------------------------------
    # PCSE lifecycle
    # ------------------------------------------------------------------

    def calc_rates(self, crop_model: CropModel) -> None:
        """Compute per-zone nutrient uptake by crops each sol."""
        from src.catalog import CROP_CATALOG

        zone_demand_n: dict[str, float] = {z: 0.0 for z in self.state}
        zone_demand_p: dict[str, float] = {z: 0.0 for z in self.state}
        zone_demand_k: dict[str, float] = {z: 0.0 for z in self.state}

        for batch in crop_model.batches.values():
            catalog = CROP_CATALOG[batch.crop_type]
            # N demand: proportional to area and growth rate
            base_n = catalog["n_demand_ppm"] * 0.005 * batch.area_m2  # ppm/sol
            zone_demand_n[batch.zone_id] = (
                zone_demand_n.get(batch.zone_id, 0.0) + base_n
            )
            zone_demand_p[batch.zone_id] = (
                zone_demand_p.get(batch.zone_id, 0.0) + base_n * 0.25
            )
            zone_demand_k[batch.zone_id] = (
                zone_demand_k.get(batch.zone_id, 0.0) + base_n * 1.1
            )

        self.rates.d_nitrogen = {z: -zone_demand_n.get(z, 0.0) for z in self.state}
        self.rates.d_phosphorus = {z: -zone_demand_p.get(z, 0.0) for z in self.state}
        self.rates.d_potassium = {z: -zone_demand_k.get(z, 0.0) for z in self.state}

    def integrate(self) -> None:
        """Apply nutrient uptake; deplete global stock."""
        for z_id, z in self.state.items():
            # Nutrient concentrations drop with crop uptake
            z.nitrogen_ppm = round(
                max(0.0, z.nitrogen_ppm + self.rates.d_nitrogen.get(z_id, 0.0)), 2
            )
            z.phosphorus_ppm = round(
                max(0.0, z.phosphorus_ppm + self.rates.d_phosphorus.get(z_id, 0.0)), 2
            )
            z.potassium_ppm = round(
                max(0.0, z.potassium_ppm + self.rates.d_potassium.get(z_id, 0.0)), 2
            )
            # EC tracks N+K roughly
            z.solution_ec_ms_cm = round(
                max(0.1, (z.nitrogen_ppm + z.potassium_ppm) / 200.0), 2
            )

        # Global stock depletion
        self.stock_remaining_pct = round(
            max(0.0, self.stock_remaining_pct - NUTRIENT_STOCK_DEGRADATION_PCT_PER_SOL),
            2,
        )
        self.days_of_stock_remaining = round(
            self.stock_remaining_pct / NUTRIENT_STOCK_DEGRADATION_PCT_PER_SOL
            if NUTRIENT_STOCK_DEGRADATION_PCT_PER_SOL > 0
            else 999.0,
            1,
        )

    # ------------------------------------------------------------------
    # Agent action
    # ------------------------------------------------------------------

    def adjust(
        self,
        zone_id: str,
        target_ph: float | None = None,
        target_ec_ms_cm: float | None = None,
        nitrogen_boost: bool = False,
        potassium_boost: bool = False,
    ) -> None:
        z = self.state[zone_id]
        if target_ph is not None:
            z.target_ph = target_ph
            z.solution_ph = round(z.solution_ph + (target_ph - z.solution_ph) * 0.5, 2)
        if target_ec_ms_cm is not None:
            z.target_ec_ms_cm = target_ec_ms_cm
        if nitrogen_boost:
            restock = min(NUTRIENT_RESTOCK_AMOUNT_PCT, self.stock_remaining_pct)
            self.stock_remaining_pct -= restock
            z.nitrogen_ppm = round(min(TARGET_N_PPM * 1.5, z.nitrogen_ppm + 30.0), 2)
        if potassium_boost:
            restock = min(NUTRIENT_RESTOCK_AMOUNT_PCT, self.stock_remaining_pct)
            self.stock_remaining_pct -= restock
            z.potassium_ppm = round(min(TARGET_K_PPM * 1.5, z.potassium_ppm + 30.0), 2)
