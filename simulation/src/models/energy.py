"""
Energy System Sub-Model.

PCSE pattern: calc_rates() computes how much energy will be generated/consumed
this sol; integrate() updates battery state. Agent calls allocate() to set
priority percentages.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import TYPE_CHECKING

from src.constants import (
    BATTERY_CAPACITY_WH,
    EFFECTIVE_SOLAR_HOURS_PER_SOL,
    HEATING_BASE_WH,
    HEATING_PER_DEGREE_WH,
    INITIAL_BATTERY_WH,
    LIGHTING_WH_PER_ZONE_PER_16H,
    NUTRIENT_PUMPS_WH,
    RECYCLING_WH,
    SENSORS_CONTROL_WH,
    SOLAR_PANEL_AREA_M2,
    SOLAR_PANEL_EFFICIENCY,
)

if TYPE_CHECKING:
    from src.models.climate import ClimateModel
    from src.models.weather import WeatherState


@dataclass
class EnergyState:
    battery_level_wh: float = INITIAL_BATTERY_WH
    battery_capacity_wh: float = BATTERY_CAPACITY_WH
    solar_generation_wh: float = 0.0
    total_consumption_wh: float = 0.0
    surplus_wh: float = 0.0
    deficit: bool = False
    breakdown: dict[str, float] = field(
        default_factory=lambda: {
            "heating_wh": 0.0,
            "lighting_wh": 0.0,
            "water_recycling_wh": RECYCLING_WH,
            "nutrient_pumps_wh": NUTRIENT_PUMPS_WH,
            "sensors_control_wh": SENSORS_CONTROL_WH,
        }
    )
    # Agent-set allocation percentages (must sum to ~100)
    allocation: dict[str, int | float] = field(
        default_factory=lambda: {
            "heating_pct": 47,
            "lighting_pct": 30,
            "water_recycling_pct": 12,
            "nutrient_pumps_pct": 5,
            "reserve_pct": 6,
        }
    )


@dataclass
class EnergyRates:
    d_battery_wh: float = 0.0  # net change this sol
    # Delivery ratios: actual/requested (1.0 = fully supplied, <1.0 = capped)
    lighting_delivery_ratio: float = 1.0
    heating_delivery_ratio: float = 1.0
    water_pumps_delivery_ratio: float = 1.0


class EnergyModel:
    """
    Solar generation → battery → subsystem allocation.

    State variables : battery_level_wh, solar_generation_wh, total_consumption_wh
    Rate variables  : d_battery_wh
    """

    def __init__(self) -> None:
        self.state = EnergyState()
        self.rates = EnergyRates()

    # ------------------------------------------------------------------
    # PCSE lifecycle
    # ------------------------------------------------------------------

    def calc_rates(self, weather: WeatherState, climate: ClimateModel) -> None:
        """Phase 1: compute generation and consumption for this sol."""
        # Solar generation (dust attenuates — already in irradiance_wm2)
        solar = (
            weather.solar_irradiance_wm2
            * SOLAR_PANEL_AREA_M2
            * SOLAR_PANEL_EFFICIENCY
            * EFFECTIVE_SOLAR_HOURS_PER_SOL
        )
        self.state.solar_generation_wh = round(solar, 1)

        # ── Requested consumption (what subsystems need) ──────────────
        outside_avg = weather.avg_temp_c
        requested_heating = HEATING_BASE_WH + HEATING_PER_DEGREE_WH * max(
            0.0, -outside_avg
        )
        requested_lighting = sum(
            z.photoperiod_hours / 16.0 * LIGHTING_WH_PER_ZONE_PER_16H
            for z in climate.state.values()
            if z.light_on
        )
        requested_recycling = RECYCLING_WH
        requested_pumps = NUTRIENT_PUMPS_WH
        sensors = SENSORS_CONTROL_WH

        # ── Allocation caps ───────────────────────────────────────────
        # Total available = this sol's solar + current battery reserve
        total_available = solar + self.state.battery_level_wh

        alloc = self.state.allocation
        heating_cap = total_available * alloc.get("heating_pct", 47) / 100.0
        lighting_cap = total_available * alloc.get("lighting_pct", 30) / 100.0
        recycling_cap = total_available * alloc.get("water_recycling_pct", 12) / 100.0
        pumps_cap = total_available * alloc.get("nutrient_pumps_pct", 5) / 100.0
        # Sensors/control always get full power (critical infrastructure)

        # Actual consumption = min(requested, cap)
        heating = min(requested_heating, heating_cap)
        lighting = min(requested_lighting, lighting_cap)
        recycling = min(requested_recycling, recycling_cap)
        pumps = min(requested_pumps, pumps_cap)

        # ── Delivery ratios (actual / requested) ─────────────────────
        self.rates.heating_delivery_ratio = (
            heating / requested_heating if requested_heating > 0 else 1.0
        )
        self.rates.lighting_delivery_ratio = (
            lighting / requested_lighting if requested_lighting > 0 else 1.0
        )
        self.rates.water_pumps_delivery_ratio = (
            recycling / requested_recycling if requested_recycling > 0 else 1.0
        )

        total = heating + lighting + recycling + pumps + sensors
        self.state.breakdown = {
            "heating_wh": round(heating, 1),
            "lighting_wh": round(lighting, 1),
            "water_recycling_wh": round(recycling, 1),
            "nutrient_pumps_wh": round(pumps, 1),
            "sensors_control_wh": round(sensors, 1),
        }
        self.state.total_consumption_wh = round(total, 1)
        self.rates.d_battery_wh = solar - total

    def integrate(self) -> None:
        """Phase 2: apply rates to battery state."""
        new_level = self.state.battery_level_wh + self.rates.d_battery_wh
        self.state.battery_level_wh = round(
            max(0.0, min(BATTERY_CAPACITY_WH, new_level)), 1
        )
        surplus = self.rates.d_battery_wh
        self.state.surplus_wh = round(surplus, 1)
        self.state.deficit = self.state.battery_level_wh <= 0.0

    # ------------------------------------------------------------------
    # Agent action
    # ------------------------------------------------------------------

    def allocate(self, allocation: dict[str, int | float]) -> None:
        """Agent updates energy allocation priorities."""
        self.state.allocation.update(allocation)
        # Normalize if active allocations exceed 100%
        active_keys = (
            "heating_pct",
            "lighting_pct",
            "water_recycling_pct",
            "nutrient_pumps_pct",
        )
        total = sum(self.state.allocation.get(k, 0) for k in active_keys)
        if total > 100:
            scale = 100.0 / total
            for k in active_keys:
                if k in self.state.allocation:
                    self.state.allocation[k] = round(
                        self.state.allocation[k] * scale, 1
                    )

    # ------------------------------------------------------------------
    # Derived helpers
    # ------------------------------------------------------------------

    @property
    def battery_pct(self) -> float:
        return round(self.state.battery_level_wh / BATTERY_CAPACITY_WH * 100.0, 1)

    @property
    def energy_factor(self) -> float:
        """0.0–1.0 indicating how much of nominal energy is available."""
        return min(1.0, self.state.battery_level_wh / (BATTERY_CAPACITY_WH * 0.3))
