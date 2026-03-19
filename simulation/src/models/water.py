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
        if self.rates.d_reservoir < 0:
            self.state.days_until_critical = round(
                max(
                    0.0,
                    (self.state.reservoir_liters - 50.0) / abs(self.rates.d_reservoir),
                ),
                1,
            )
        else:
            self.state.days_until_critical = 999.0

    # ------------------------------------------------------------------
    # Agent actions
    # ------------------------------------------------------------------

    def set_irrigation(self, zone_id: str, liters_per_sol: float) -> None:
        self.state.irrigation_settings[zone_id] = max(0.0, liters_per_sol)

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
        return {"result": "unknown_action"}
