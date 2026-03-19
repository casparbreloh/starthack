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
            "other_wh": 0.0,
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

        # Heating: proportional to temperature delta (outside avg)
        outside_avg = weather.avg_temp_c
        heating = HEATING_BASE_WH + HEATING_PER_DEGREE_WH * max(0.0, -outside_avg)

        # Lighting: depends on zone photoperiod settings
        lighting = sum(
            z.photoperiod_hours / 16.0 * LIGHTING_WH_PER_ZONE_PER_16H
            for z in climate.state.values()
            if z.light_on
        )

        recycling = RECYCLING_WH
        pumps = NUTRIENT_PUMPS_WH
        sensors = SENSORS_CONTROL_WH

        total = heating + lighting + recycling + pumps + sensors
        self.state.breakdown = {
            "heating_wh": round(heating, 1),
            "lighting_wh": round(lighting, 1),
            "water_recycling_wh": round(recycling, 1),
            "nutrient_pumps_wh": round(pumps, 1),
            "sensors_control_wh": round(sensors, 1),
            "other_wh": 0.0,
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
