"""
Mars Weather Model — generates deterministic synthetic weather for each sol.

Uses a simplified Ls-based seasonal model derived from real Mars climatology
(InSight/Curiosity data patterns). Deterministic: same sol always gives same
weather unless a scenario has been injected.
"""

from __future__ import annotations

import math
from dataclasses import dataclass

from src.constants import (
    MARS_ECCENTRICITY,
    MARS_SEMIMAJOR_AXIS_AU,
    MARS_SOLAR_CONSTANT_WM2,
    MARS_SOLS_PER_YEAR,
)


@dataclass
class WeatherState:
    sol: int
    min_temp_c: float
    max_temp_c: float
    avg_temp_c: float
    pressure_pa: float
    solar_irradiance_wm2: float  # top-of-atmosphere
    dust_opacity: float  # optical depth τ (0.1 = clear, 3.0 = severe storm)
    season: str
    ls: float  # solar longitude 0–360°
    sol_in_year: int


class MarsWeatherModel:
    """
    Generates and stores Mars weather.

    Follows PCSE's WeatherDataProvider pattern: each sol the engine calls
    `advance(sol)` which computes and caches the weather for that sol.
    Historical data can be retrieved via `history(n)` and future via `forecast(horizon)`.
    """

    def __init__(self) -> None:
        self._store: dict[int, WeatherState] = {}  # sol → WeatherState

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def advance(self, sol: int) -> WeatherState:
        """Compute and cache weather for `sol`. Call once per tick."""
        w = self._compute(sol)
        self._store[sol] = w
        return w

    def current(self) -> WeatherState | None:
        if not self._store:
            return None
        return self._store[max(self._store)]

    def history(self, last_n_sols: int = 30) -> list[WeatherState]:
        if not self._store:
            return []
        max_sol = max(self._store)
        min_sol = min(self._store)
        start_sol = max(min_sol, max_sol - last_n_sols + 1)
        return [
            self._store[s] for s in range(start_sol, max_sol + 1) if s in self._store
        ]

    def forecast(self, current_sol: int, horizon: int = 7) -> list[WeatherState]:
        """Pre-compute future sols (deterministic model = perfect forecast)."""
        return [self._compute(current_sol + i) for i in range(1, horizon + 1)]

    # ------------------------------------------------------------------
    # Core computation (PCSE-style: pure function of time)
    # ------------------------------------------------------------------

    def _compute(self, sol: int) -> WeatherState:
        sol_in_year = sol % MARS_SOLS_PER_YEAR
        ls = (sol_in_year / MARS_SOLS_PER_YEAR) * 360.0
        ls_rad = math.radians(ls)

        # Mars–Sun distance (AU): perihelion at Ls ≈ 250° (southern summer)
        r = (
            MARS_SEMIMAJOR_AXIS_AU
            * (1 - MARS_ECCENTRICITY**2)
            / (1 + MARS_ECCENTRICITY * math.cos(ls_rad - math.radians(250.0)))
        )

        # Top-of-atmosphere solar irradiance
        irradiance_top = MARS_SOLAR_CONSTANT_WM2 / r**2

        # Dust opacity: seasonal baseline + deterministic pseudo-variation
        # Dust storms peak during southern summer (Ls 180–360)
        dust_seasonal = 0.3 + 0.25 * max(0.0, math.sin(ls_rad - math.radians(90.0)))
        dust_noise = 0.08 * math.sin(sol * 7.3) * math.cos(sol * 3.1)
        dust_opacity = max(0.1, min(2.5, dust_seasonal + dust_noise))

        # Surface irradiance: Beer-Lambert attenuation by dust
        irradiance_surface = irradiance_top * math.exp(-0.9 * dust_opacity)

        # Temperature: equatorial location seasonal model
        # Northern spring (Ls ≈ 0°) is coldest due to aphelion proximity
        # Perihelion (Ls ≈ 250°) is the warmest period
        seasonal_mean = -50.0 + 35.0 * math.sin(ls_rad - math.radians(60.0))
        # Diurnal variation ~45 °C
        diurnal = 45.0
        min_temp = seasonal_mean - diurnal / 2.0
        max_temp = seasonal_mean + diurnal / 2.0
        avg_temp = seasonal_mean

        # Atmospheric pressure: CO₂ frost cycle (high in summer, low in winter)
        pressure_pa = 700.0 + 100.0 * math.sin(ls_rad)

        # Season label
        if ls < 90:
            season = "Northern Spring"
        elif ls < 180:
            season = "Northern Summer"
        elif ls < 270:
            season = "Northern Autumn"
        else:
            season = "Northern Winter"

        return WeatherState(
            sol=sol,
            min_temp_c=round(min_temp, 1),
            max_temp_c=round(max_temp, 1),
            avg_temp_c=round(avg_temp, 1),
            pressure_pa=round(pressure_pa, 1),
            solar_irradiance_wm2=round(irradiance_surface, 1),
            dust_opacity=round(dust_opacity, 3),
            season=season,
            ls=round(ls, 2),
            sol_in_year=sol_in_year,
        )
