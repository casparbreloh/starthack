"""
Water System Sub-Model.

Tracks the facility water reservoir, recycling efficiency, filter health,
and per-zone irrigation settings.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import TYPE_CHECKING

from src.constants import (
    CREW_DAILY_WATER_L,
    FILTER_DEGRADATION_RATE_PCT_PER_SOL,
    FILTER_HEALTH_MAINTENANCE_RESTORE,
    FILTER_HEALTH_MIN_EFFICIENCY_FACTOR,
    ICE_MINING_BASE_YIELD_L,
    ICE_MINING_DRILL_DEGRADATION_PCT,
    ICE_MINING_DRILL_INITIAL_HEALTH_PCT,
    ICE_MINING_DRILL_MAINTENANCE_RESTORE_PCT,
    ICE_MINING_DRILL_MIN_HEALTH_PCT,
    ICE_MINING_ENERGY_COST_WH,
    ICE_MINING_MIN_YIELD_L,
    INITIAL_WATER_RESERVOIR_L,
    PLANT_TRANSPIRATION_RECOVERY_PCT,
    WATER_RECYCLING_NOMINAL_PCT,
    WATER_RESERVOIR_CAPACITY_L,
    ZONE_AREAS_M2,
)

if TYPE_CHECKING:
    from src.models.crops import CropModel


@dataclass
class WaterState:
    reservoir_liters: float = INITIAL_WATER_RESERVOIR_L
    reservoir_capacity_liters: float = WATER_RESERVOIR_CAPACITY_L
    recycling_efficiency_pct: float = WATER_RECYCLING_NOMINAL_PCT
    filter_health_pct: float = 100.0
    daily_crew_consumption_liters: float = CREW_DAILY_WATER_L
    daily_crop_consumption_liters: float = 0.0
    daily_recycled_liters: float = 0.0
    daily_net_change_liters: float = 0.0
    days_until_critical: float = 999.0
    # Per-zone irrigation (L/sol)
    irrigation_settings: dict[str, float] = field(
        default_factory=lambda: {z: 5.0 for z in ZONE_AREAS_M2}
    )
    # Ice mining state
    drill_health_pct: float = ICE_MINING_DRILL_INITIAL_HEALTH_PCT
    last_mining_sol: int = -1
    daily_mined_liters: float = 0.0
    total_mined_liters: float = 0.0


@dataclass
class WaterRates:
    d_reservoir: float = 0.0


class WaterModel:
    """
    State variables  : reservoir_liters, recycling_efficiency_pct, filter_health_pct
    Rate variables   : d_reservoir (net L/sol)
    """

    def __init__(self) -> None:
        self.state = WaterState()
        self.rates = WaterRates()

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _health_factor(self) -> float:
        """Clamped filter health as an efficiency multiplier in [FILTER_HEALTH_MIN_EFFICIENCY_FACTOR, 1.0]."""
        return (
            FILTER_HEALTH_MIN_EFFICIENCY_FACTOR
            + (1.0 - FILTER_HEALTH_MIN_EFFICIENCY_FACTOR)
            * self.state.filter_health_pct
            / 100.0
        )

    def _update_recycling_efficiency(self) -> None:
        """Recompute recycling_efficiency_pct from current filter health."""
        self.state.recycling_efficiency_pct = round(
            WATER_RECYCLING_NOMINAL_PCT * self._health_factor(), 2
        )

    # ------------------------------------------------------------------
    # PCSE lifecycle
    # ------------------------------------------------------------------

    def calc_rates(
        self,
        crop_model: CropModel,
        water_pumps_delivery_ratio: float = 1.0,
    ) -> None:
        """Compute net water change this sol.

        Two recycling loops (NASA ECLSS):
          1. Crew metabolic water (urine, sweat, respiration): WATER_RECYCLING_NOMINAL_PCT
          2. Plant transpiration captured by condensing heat exchanger: PLANT_TRANSPIRATION_RECOVERY_PCT

        ``water_pumps_delivery_ratio`` (0.0–1.0) scales recycling efficiency
        when the water pumps receive less energy than they need.
        """
        # Crop water demand: sum of zone irrigation settings (L/sol)
        total_irrigation = sum(self.state.irrigation_settings.values())
        self.state.daily_crop_consumption_liters = round(total_irrigation, 2)

        # Loop 1 — Crew metabolic water recovery (scaled by pump power)
        recycled_from_crew = (
            CREW_DAILY_WATER_L
            * self.state.recycling_efficiency_pct
            / 100.0
            * water_pumps_delivery_ratio
        )

        # Loop 2 — Plant transpiration recovery (filter health degrades this too)
        effective_transpiration_pct = (
            PLANT_TRANSPIRATION_RECOVERY_PCT * self._health_factor()
        )
        recycled_from_plants = (
            total_irrigation
            * effective_transpiration_pct
            / 100.0
            * water_pumps_delivery_ratio
        )

        total_recycled = recycled_from_crew + recycled_from_plants
        self.state.daily_recycled_liters = round(total_recycled, 2)

        # Net change = outflows - inflows
        net = -(CREW_DAILY_WATER_L + total_irrigation - total_recycled)
        self.rates.d_reservoir = net
        self.state.daily_net_change_liters = round(net, 2)

    def integrate(self) -> None:
        """Apply rates and degrade filter."""
        self.state.reservoir_liters = round(
            max(
                0.0,
                min(
                    WATER_RESERVOIR_CAPACITY_L,
                    self.state.reservoir_liters + self.rates.d_reservoir,
                ),
            ),
            2,
        )

        # Filter degradation (passive)
        self.state.filter_health_pct = round(
            max(
                0.0, self.state.filter_health_pct - FILTER_DEGRADATION_RATE_PCT_PER_SOL
            ),
            2,
        )

        # Recycling efficiency scales with filter health
        self._update_recycling_efficiency()

        # Estimate days until critical (50 L)
        net_loss = abs(self.rates.d_reservoir)
        if self.rates.d_reservoir < 0 and net_loss >= 0.01:
            self.state.days_until_critical = round(
                max(0.0, (self.state.reservoir_liters - 50.0) / net_loss), 1
            )
        else:
            self.state.days_until_critical = 999.0

    # ------------------------------------------------------------------
    # Agent actions
    # ------------------------------------------------------------------

    def set_irrigation(self, zone_id: str, liters_per_sol: float) -> None:
        self.state.irrigation_settings[zone_id] = max(0.0, liters_per_sol)

    def mine_ice(self, current_sol: int, battery_wh: float) -> dict:
        """Extract water from Martian ice deposits using a drill.

        Degrades drill health; limited to once per sol.
        Reset daily_mined_liters at the top of every call.
        """
        # Always reset daily counter at the start of every mine_ice call
        self.state.daily_mined_liters = 0.0

        # Guard 1: Can only mine once per sol
        if current_sol == self.state.last_mining_sol:
            return {"result": "failed", "reason": "already_mined_this_sol"}

        # Guard 2: Require sufficient energy
        if battery_wh < ICE_MINING_ENERGY_COST_WH:
            return {"result": "failed", "reason": "insufficient_energy"}

        # Guard 3: Drill must be above minimum health threshold
        if self.state.drill_health_pct < ICE_MINING_DRILL_MIN_HEALTH_PCT:
            return {"result": "failed", "reason": "drill_too_damaged"}

        # Calculate yield based on drill health (linear interpolation)
        liters = (
            ICE_MINING_MIN_YIELD_L
            + (ICE_MINING_BASE_YIELD_L - ICE_MINING_MIN_YIELD_L)
            * self.state.drill_health_pct
            / 100.0
        )

        # Clamp to reservoir capacity
        liters = min(liters, WATER_RESERVOIR_CAPACITY_L - self.state.reservoir_liters)

        # Update state
        self.state.reservoir_liters = round(
            min(WATER_RESERVOIR_CAPACITY_L, self.state.reservoir_liters + liters), 2
        )
        self.state.drill_health_pct = round(
            max(0.0, self.state.drill_health_pct - ICE_MINING_DRILL_DEGRADATION_PCT), 2
        )
        self.state.last_mining_sol = current_sol
        self.state.daily_mined_liters = round(liters, 2)
        self.state.total_mined_liters = round(self.state.total_mined_liters + liters, 2)

        return {
            "result": "success",
            "liters_extracted": round(liters, 2),
            "energy_cost_wh": ICE_MINING_ENERGY_COST_WH,
            "new_drill_health_pct": round(self.state.drill_health_pct, 2),
            "new_reservoir_liters": round(self.state.reservoir_liters, 2),
        }

    def maintenance(self, action: str) -> dict:
        if action == "clean_filters":
            restored = min(
                100.0 - self.state.filter_health_pct,
                FILTER_HEALTH_MAINTENANCE_RESTORE,
            )
            self.state.filter_health_pct = round(
                min(100.0, self.state.filter_health_pct + restored), 2
            )
            # Immediately recalculate recycling efficiency
            self._update_recycling_efficiency()
            return {
                "result": "success",
                "new_efficiency_pct": self.state.recycling_efficiency_pct,
                "new_filter_health_pct": self.state.filter_health_pct,
                "downtime_hours": 4,
            }
        elif action == "maintain_drill":
            restored = min(
                100.0 - self.state.drill_health_pct,
                ICE_MINING_DRILL_MAINTENANCE_RESTORE_PCT,
            )
            self.state.drill_health_pct = round(
                min(100.0, self.state.drill_health_pct + restored), 2
            )
            return {
                "result": "success",
                "new_drill_health_pct": self.state.drill_health_pct,
                "downtime_hours": 6,
            }
        return {"result": "unknown_action"}
