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
    PH_ACIDIFICATION_PER_SOL,
    SALT_ACCUMULATION_PPM_PER_SOL,
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
    # Accumulated mineral salts (rises passively each sol; flushing resets it)
    base_salt_ppm: float = 20.0
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

    nutrient_stock_remaining_pct
        Physical reserve of nutrient salts (fertiliser concentrate) stored in
        the greenhouse. Cannot be replenished on Mars — it is a finite,
        one-way expendable.

        Depletion mechanisms:
          • Passive degradation / precipitation losses: -0.08 %/sol (runs out
            after ~1 250 sols at baseline, well beyond the 450-sol mission).
          • Agent boost action (nitrogen_boost or potassium_boost): -10 % of
            total stock per call. Budget is therefore ~10 boosts before
            depletion; use sparingly.

        The per-zone N/P/K concentrations are separate from this stock —
        they drop as crops take up nutrients and are only refilled when the
        agent explicitly calls adjust() with a boost flag.
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
        # Tracks which zones have active crop N demand this sol (set in calc_rates,
        # consumed in integrate for pH drift logic)
        self._zone_has_demand: dict[str, bool] = {z: False for z in ZONE_AREAS_M2}

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
        # Record which zones have active crops (drives pH acidification in integrate)
        self._zone_has_demand = {z: zone_demand_n.get(z, 0.0) > 0 for z in self.state}

    def integrate(self) -> None:
        """Apply nutrient uptake; deplete global stock."""
        for z_id, z in self.state.items():
            # Reset per-sol boost flags before applying this tick
            z.nitrogen_boost = False
            z.potassium_boost = False
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
            # Salt accumulation: mineral residue from water that doesn't fully recycle
            z.base_salt_ppm = round(
                min(500.0, z.base_salt_ppm + SALT_ACCUMULATION_PPM_PER_SOL), 2
            )
            # EC = total dissolved solids (nutrients + accumulated mineral salts)
            z.solution_ec_ms_cm = round(
                max(0.1, (z.nitrogen_ppm + z.potassium_ppm + z.base_salt_ppm) / 200.0),
                2,
            )
            # pH drift: crop nutrient uptake acidifies solution (cation > anion uptake);
            # zones without crops drift alkaline (Mars water tendency)
            if self._zone_has_demand.get(z_id, False):
                z.solution_ph = round(
                    max(4.0, z.solution_ph - PH_ACIDIFICATION_PER_SOL), 2
                )
            else:
                z.solution_ph = round(min(8.0, z.solution_ph + 0.01), 2)

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
        flush_solution: bool = False,
    ) -> dict:
        z = self.state[zone_id]
        result: dict = {}
        if target_ph is not None:
            z.target_ph = target_ph
            z.solution_ph = round(z.solution_ph + (target_ph - z.solution_ph) * 0.5, 2)
        if target_ec_ms_cm is not None:
            z.target_ec_ms_cm = target_ec_ms_cm
        if nitrogen_boost:
            restock = min(NUTRIENT_RESTOCK_AMOUNT_PCT, self.stock_remaining_pct)
            self.stock_remaining_pct -= restock
            z.nitrogen_ppm = round(min(TARGET_N_PPM * 1.5, z.nitrogen_ppm + 30.0), 2)
            z.nitrogen_boost = True
        if potassium_boost:
            restock = min(NUTRIENT_RESTOCK_AMOUNT_PCT, self.stock_remaining_pct)
            self.stock_remaining_pct -= restock
            z.potassium_ppm = round(min(TARGET_K_PPM * 1.5, z.potassium_ppm + 30.0), 2)
            z.potassium_boost = True
        if flush_solution:
            # Dilute solution: flush removes ~70% of accumulated mineral salts.
            # Costs 10 L of water (caller must deduct from reservoir).
            old_salt = z.base_salt_ppm
            z.base_salt_ppm = round(max(20.0, z.base_salt_ppm * 0.3), 2)
            result["flush"] = {
                "salt_ppm_before": old_salt,
                "salt_ppm_after": z.base_salt_ppm,
                "water_cost_l": 10.0,
            }
        return result
