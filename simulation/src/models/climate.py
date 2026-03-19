"""
Greenhouse Climate Sub-Model.

Maintains per-zone environment. Each zone has temperature, humidity, CO₂, PAR,
and photoperiod setpoints. When energy is sufficient the actual values track the
setpoints; when energy is constrained values degrade toward external conditions.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import TYPE_CHECKING

from src.constants import (
    TARGET_CO2_PPM,
    TARGET_HUMIDITY_PCT,
    TARGET_PAR,
    TARGET_PHOTOPERIOD_H,
    TARGET_TEMP_C,
    TOTAL_GREENHOUSE_AREA_M2,
    ZONE_AREAS_M2,
)

if TYPE_CHECKING:
    from src.models.energy import EnergyModel
    from src.models.weather import WeatherState


@dataclass
class ZoneClimate:
    zone_id: str
    area_m2: float
    # Actual (measured) conditions
    temp_c: float = TARGET_TEMP_C
    humidity_pct: float = TARGET_HUMIDITY_PCT
    co2_ppm: float = TARGET_CO2_PPM
    par_umol_m2s: float = TARGET_PAR
    light_on: bool = True
    photoperiod_hours: float = TARGET_PHOTOPERIOD_H
    # Setpoints (what the agent wants)
    target_temp_c: float = TARGET_TEMP_C
    target_humidity_pct: float = TARGET_HUMIDITY_PCT
    target_co2_ppm: float = TARGET_CO2_PPM
    target_par: float = TARGET_PAR
    target_photoperiod_hours: float = TARGET_PHOTOPERIOD_H


@dataclass
class ClimateRates:
    d_temp: dict[str, float] = field(default_factory=dict)
    d_co2: dict[str, float] = field(default_factory=dict)
    d_humidity: dict[str, float] = field(default_factory=dict)


class ClimateModel:
    """
    Per-zone greenhouse climate.

    State variables  : ZoneClimate per zone (temp, humidity, co2, par, photoperiod)
    Rate variables   : delta per zone per sol (approach-to-setpoint dynamics)
    """

    def __init__(self) -> None:
        self.state: dict[str, ZoneClimate] = {
            zone_id: ZoneClimate(zone_id=zone_id, area_m2=area)
            for zone_id, area in ZONE_AREAS_M2.items()
        }
        self.rates = ClimateRates()
        self._lighting_ratio: float = 1.0  # set by calc_rates from energy model

    # ------------------------------------------------------------------
    # PCSE lifecycle
    # ------------------------------------------------------------------

    def calc_rates(self, weather: WeatherState, energy: EnergyModel) -> None:
        """
        Compute how far each zone moves toward its setpoints.

        Uses per-subsystem delivery ratios from the energy model so that
        allocation caps have physical consequences:
          - heating_delivery_ratio  → temperature control effectiveness
          - lighting_delivery_ratio → PAR output scaling
          - energy_factor           → CO₂ scrubbing / humidity (general power)
        """
        ef = energy.energy_factor  # 0 = no energy, 1 = full energy
        heating_ratio = energy.rates.heating_delivery_ratio
        self._lighting_ratio = energy.rates.lighting_delivery_ratio
        outside_temp = weather.avg_temp_c

        for z in self.state.values():
            # Temperature: heating delivery ratio controls HVAC effectiveness
            temp_drift = (outside_temp - z.temp_c) * (1.0 - heating_ratio)
            temp_control = (z.target_temp_c - z.temp_c) * heating_ratio * 0.8
            self.rates.d_temp[z.zone_id] = temp_drift + temp_control

            # CO₂: maintained at setpoint when energy > 50%, else drifts down slowly
            if ef > 0.5:
                self.rates.d_co2[z.zone_id] = (z.target_co2_ppm - z.co2_ppm) * 0.6
            else:
                # CO₂ slowly bleeds out (ventilation/leakage)
                self.rates.d_co2[z.zone_id] = (400.0 - z.co2_ppm) * 0.1 * (1 - ef)

            # Humidity: maintained within wide band; minor drift only
            self.rates.d_humidity[z.zone_id] = (
                (z.target_humidity_pct - z.humidity_pct) * 0.4 * ef
            )

    def integrate(self) -> None:
        """Phase 2: apply climate rates."""
        for z in self.state.values():
            z.temp_c = round(z.temp_c + self.rates.d_temp.get(z.zone_id, 0.0), 2)
            z.co2_ppm = round(
                max(350.0, z.co2_ppm + self.rates.d_co2.get(z.zone_id, 0.0)), 1
            )
            z.humidity_pct = round(
                max(
                    10.0,
                    min(
                        95.0, z.humidity_pct + self.rates.d_humidity.get(z.zone_id, 0.0)
                    ),
                ),
                1,
            )
            # PAR scales with lighting delivery ratio; photoperiod is a schedule
            z.par_umol_m2s = round(z.target_par * self._lighting_ratio, 1)
            z.photoperiod_hours = z.target_photoperiod_hours

    # ------------------------------------------------------------------
    # Agent action
    # ------------------------------------------------------------------

    def set_zone(
        self,
        zone_id: str,
        target_temp_c: float | None = None,
        target_humidity_pct: float | None = None,
        target_co2_ppm: float | None = None,
        par_umol_m2s: float | None = None,
        photoperiod_hours: float | None = None,
    ) -> ZoneClimate:
        z = self.state[zone_id]
        if target_temp_c is not None:
            z.target_temp_c = target_temp_c
        if target_humidity_pct is not None:
            z.target_humidity_pct = target_humidity_pct
        if target_co2_ppm is not None:
            z.target_co2_ppm = target_co2_ppm
        if par_umol_m2s is not None:
            z.target_par = par_umol_m2s
        if photoperiod_hours is not None:
            z.target_photoperiod_hours = photoperiod_hours
            z.light_on = photoperiod_hours > 0
        return z

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    def avg_temp(self) -> float:
        """Area-weighted average temperature across all zones."""
        if TOTAL_GREENHOUSE_AREA_M2 == 0:
            return TARGET_TEMP_C
        return (
            sum(z.temp_c * z.area_m2 for z in self.state.values())
            / TOTAL_GREENHOUSE_AREA_M2
        )

    def avg_co2(self) -> float:
        if TOTAL_GREENHOUSE_AREA_M2 == 0:
            return TARGET_CO2_PPM
        return (
            sum(z.co2_ppm * z.area_m2 for z in self.state.values())
            / TOTAL_GREENHOUSE_AREA_M2
        )
