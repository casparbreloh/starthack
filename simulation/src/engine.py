"""
Simulation Engine — master orchestrator.

Follows the PCSE (WOFOST) pattern of:
  1. calc_rates()  — all sub-models compute their rate variables for this sol
  2. integrate()   — all sub-models apply rates to update state variables

Sub-model call order matters:
  Weather → Energy → Climate → Water → Nutrients → Crops → Crew → Events/Scoring

The engine is a plain Python object (no FastAPI dependency) so it can be
unit-tested in isolation.
"""

from __future__ import annotations

import math
import random
from collections import deque
from dataclasses import dataclass
from typing import Any

from src.constants import (
    BATTERY_CAPACITY_WH,
    CREW_DAILY_KCAL,
    DUST_STORM_OPACITY_TAU,
    MARS_DUST_EXTINCTION_COEFF,
    MISSION_DURATION_SOLS,
)
from src.enums import CrisisType, Difficulty, MissionPhase, Severity
from src.models.autonomous_events import AutonomousEventSystem
from src.models.climate import ClimateModel
from src.models.crew import CrewModel
from src.models.crops import CropModel
from src.models.energy import EnergyModel
from src.models.events import EventLog
from src.models.nutrients import NutrientModel
from src.models.scoring import ScoringModel
from src.models.water import WaterModel
from src.models.weather import MarsWeatherModel


@dataclass
class AgentDecision:
    sol: int
    decisions: list[dict[str, Any]]
    weather_forecast_used: dict[str, Any] | None = None
    risk_assessment: str = "nominal"
    reasoning: str = ""
    summary: str = ""


class SimulationEngine:
    """
    Central state machine for the Mars greenhouse simulation.

    All state lives here; routers only read/write through this object.yeah
    """

    def __init__(self) -> None:
        self._init_state()
        # Compute initial weather for sol 0
        self.weather.advance(0)

    def _init_state(self) -> None:
        """Shared initialisation for __init__ and reset."""
        self.current_sol: int = 0
        self.mission_phase: MissionPhase = MissionPhase.ACTIVE
        self.paused: bool = False
        self.mission_duration_sols: int = MISSION_DURATION_SOLS

        # Sub-models
        self.weather = MarsWeatherModel()
        self.energy = EnergyModel()
        self.climate = ClimateModel()
        self.water = WaterModel()
        self.nutrients = NutrientModel()
        self.crops = CropModel()
        self.crew = CrewModel()
        self.events = EventLog()
        self.scoring = ScoringModel()
        self.autonomous_events = AutonomousEventSystem(random.Random(42))

        # Agent decision log
        self.agent_decisions: deque[AgentDecision] = deque(maxlen=500)

        # Autonomous events toggle (demo mode disables these)
        self.autonomous_events_enabled: bool = True

        # Dust storm scenario state
        self._dust_storm_remaining_sols: int = 0
        self._dust_storm_opacity: float = 0.0

    # ------------------------------------------------------------------
    # Core tick
    # ------------------------------------------------------------------

    def advance(self, sols: int = 1) -> list[dict[str, Any]]:
        """
        Advance the simulation by `sols` days.
        Returns list of events that occurred during the advance.
        """
        new_events: list[dict[str, Any]] = []

        for _ in range(sols):
            if self.mission_phase != MissionPhase.ACTIVE:
                break

            self.current_sol += 1
            tick_events = self._tick()
            new_events.extend(tick_events)

        return new_events

    def _tick(self) -> list[dict[str, Any]]:
        """Single-sol simulation step. Returns serialisable event list."""
        sol = self.current_sol

        # ── Phase 1: calc_rates ──────────────────────────────────────
        weather = self.weather.advance(sol)

        # Override dust opacity during active dust storm scenario
        if self._dust_storm_remaining_sols > 0:
            # Reverse original Beer-Lambert to recover top-of-atmosphere irradiance
            original_opacity = weather.dust_opacity
            irradiance_top = weather.solar_irradiance_wm2 / math.exp(
                -MARS_DUST_EXTINCTION_COEFF * original_opacity
            )
            # Apply storm opacity
            weather.dust_opacity = self._dust_storm_opacity
            weather.solar_irradiance_wm2 = round(
                irradiance_top
                * math.exp(-MARS_DUST_EXTINCTION_COEFF * self._dust_storm_opacity),
                1,
            )
            # Update the cached weather state
            self.weather._store[sol] = weather
            self._dust_storm_remaining_sols -= 1
            if self._dust_storm_remaining_sols == 0:
                self.events.resolve_crisis(CrisisType.DUST_STORM, sol)
                self.events.log(
                    sol,
                    "info",
                    "energy",
                    "Dust storm has cleared — solar irradiance returning to normal",
                    Severity.INFO,
                )

        # Apply autonomous dust storm solar reduction (if any) so that
        # the energy model sees correct generation and surplus_wh is accurate.
        # This stacks multiplicatively with the scenario dust storm above,
        # which is intentional — they are independent systems.
        auto_solar_factor = self.autonomous_events.active_solar_factor(sol)
        if auto_solar_factor < 1.0:
            weather.solar_irradiance_wm2 = round(
                weather.solar_irradiance_wm2 * auto_solar_factor, 1
            )

        self.energy.calc_rates(weather, self.climate)
        self.climate.calc_rates(weather, self.energy)
        self.water.calc_rates(
            self.crops,
            water_pumps_delivery_ratio=self.energy.rates.water_pumps_delivery_ratio,
        )
        self.nutrients.calc_rates(self.crops)
        self.crops.calc_rates(sol, self.climate, self.water, self.nutrients)
        self.crew.calc_rates(
            water_reservoir_l=self.water.state.reservoir_liters,
            avg_temp_c=self.climate.avg_temp(),
            avg_co2_ppm=self.climate.avg_co2(),
        )

        # ── Phase 2: integrate ───────────────────────────────────────
        self.energy.integrate()
        self.climate.integrate()
        self.water.integrate()
        self.nutrients.integrate()
        dead_crops = self.crops.integrate()
        self.crew.integrate(current_sol=sol)

        # ── Autonomous events (post-integration effects this sol) ─────
        tick_events: list[dict[str, Any]] = []
        if self.autonomous_events_enabled:
            for ae in self.autonomous_events.tick(sol, self):
                sev = Severity(ae["severity"])
                ev = self.events.log(
                    sol, ae["type"], ae["category"], ae["message"], sev
                )
                tick_events.append(ev.to_dict())

        # ── Event generation ─────────────────────────────────────────

        # Starvation level-change events (emitted by CrewModel)
        for category, message, sev_str in self.crew.pending_events:
            ev = self.events.log(sol, "alert", category, message, Severity(sev_str))
            tick_events.append(ev.to_dict())

        # Dead crops
        for crop_id in dead_crops:
            ev = self.events.log(
                sol,
                "alert",
                "crop",
                f"Crop '{crop_id}' died (health reached 0)",
                Severity.CRITICAL,
            )
            tick_events.append(ev.to_dict())

        # Crew death check → mission failure
        if not self.crew.is_alive and self.mission_phase == MissionPhase.ACTIVE:
            cause = self.crew.health.cause_of_death or "unknown"
            self.mission_phase = MissionPhase.FAILED
            ev = self.events.log(
                sol,
                "crisis",
                "crew",
                f"MISSION FAILED: Crew perished — cause: {cause}",
                Severity.CRITICAL,
            )
            tick_events.append(ev.to_dict())

        # Automatic crisis detection
        avg_temp = self.climate.avg_temp()
        avg_co2 = self.climate.avg_co2()
        self.events.detect_and_update(
            sol=sol,
            water_reservoir_L=self.water.state.reservoir_liters,
            water_recycling_pct=self.water.state.recycling_efficiency_pct,
            battery_wh=self.energy.state.battery_level_wh,
            battery_capacity_wh=BATTERY_CAPACITY_WH,
            avg_temp_c=avg_temp,
            co2_ppm=avg_co2,
            nutrient_stock_pct=self.nutrients.stock_remaining_pct,
            crew_kcal=self.crew.total_kcal,
            crew_daily_kcal=CREW_DAILY_KCAL,
            crew_hydration_pct=self.crew.hydration_pct,
            crew_dehydration_level=self.crew.health.dehydration_level,
            crew_starvation_level=self.crew.health.starvation_level,
            cumulative_radiation_msv=self.crew.health.cumulative_radiation_msv,
        )

        # Scoring update
        self.scoring.update(
            sol=sol,
            crew_kcal=self.crew.state.today_kcal_consumed,
            crew_protein_g=self.crew.state.today_protein_consumed_g,
            crew_alive=self.crew.is_alive,
            micronutrients=self.crew.state.micronutrients_sufficient,
            all_crises=self.events.all_crises(),
            active_crises=self.events.active_crises(),
            battery_pct=self.energy.battery_pct,
            reservoir_L=self.water.state.reservoir_liters,
            reservoir_capacity_L=self.water.state.reservoir_capacity_liters,
        )

        # Mission completion check
        if (
            sol >= self.mission_duration_sols
            and self.mission_phase == MissionPhase.ACTIVE
        ):
            self.mission_phase = MissionPhase.COMPLETE
            self.events.log(
                sol,
                "info",
                "mission",
                f"Mission complete after {self.mission_duration_sols} sols.",
                Severity.INFO,
            )

        return tick_events

    # ------------------------------------------------------------------
    # Reset
    # ------------------------------------------------------------------

    def reset(
        self,
        difficulty: Difficulty = Difficulty.NORMAL,
        starting_reserves: dict[str, float] | None = None,
        mission_duration_sols: int = MISSION_DURATION_SOLS,
    ) -> None:
        """Reset simulation to sol 0 with optional config overrides."""
        self._init_state()
        self.mission_duration_sols = mission_duration_sols

        # Apply difficulty modifiers
        _apply_difficulty(self, difficulty)

        # Apply override reserves
        if starting_reserves:
            if "water_liters" in starting_reserves:
                self.water.state.reservoir_liters = float(
                    starting_reserves["water_liters"]
                )
            if "food_buffer_kcal" in starting_reserves:
                self.crew.state.fresh_buffer_kcal = float(
                    starting_reserves["food_buffer_kcal"]
                )
            if "battery_wh" in starting_reserves:
                self.energy.state.battery_level_wh = float(
                    starting_reserves["battery_wh"]
                )
            if "drill_health_pct" in starting_reserves:
                self.water.state.drill_health_pct = max(
                    0.0, min(100.0, float(starting_reserves["drill_health_pct"]))
                )

        self.weather.advance(0)

    # ------------------------------------------------------------------
    # Scenario injections (admin/hackathon triggers)
    # ------------------------------------------------------------------

    def scenario_water_leak(self) -> None:
        """Drop recycling efficiency to 70% (filter damage)."""
        self.water.state.filter_health_pct = 30.0
        self.water.state.recycling_efficiency_pct = 70.0
        self.events.log(
            self.current_sol,
            "crisis",
            "water",
            "SCENARIO: Water leak — recycling efficiency dropped to 70%",
            Severity.CRITICAL,
        )
        self.events.open_crisis(
            self.current_sol,
            CrisisType.WATER_RECYCLING_DECLINE,
            Severity.CRITICAL,
            "Water leak scenario injected",
            70.0,
            85.0,
        )

    def scenario_hvac_failure(self) -> None:
        """Drop all zone temperatures to -10°C instantly."""
        for zone in self.climate.state.values():
            zone.temp_c = -10.0
            zone.target_temp_c = -10.0
        self.events.log(
            self.current_sol,
            "crisis",
            "temperature",
            "SCENARIO: HVAC failure — all zones dropped to -10°C",
            Severity.CRITICAL,
        )
        self.events.open_crisis(
            self.current_sol,
            CrisisType.TEMPERATURE_FAILURE,
            Severity.CRITICAL,
            "HVAC failure scenario injected",
            -10.0,
            15.0,
        )

    def scenario_pathogen(self, crop_id: str) -> None:
        """Drop a specific crop's health to 10%."""
        self.crops.inject_pathogen(crop_id)
        self.events.log(
            self.current_sol,
            "crisis",
            "crop",
            f"SCENARIO: Pathogen outbreak in crop '{crop_id}' — health → 10%",
            Severity.CRITICAL,
            data={"crop_id": crop_id},
        )
        self.events.open_crisis(
            self.current_sol,
            CrisisType.PATHOGEN_OUTBREAK,
            Severity.CRITICAL,
            f"Pathogen outbreak in {crop_id}",
            0.10,
            0.50,
        )

    def scenario_dust_storm(self, duration_sols: int = 10) -> None:
        """Simulates a dust storm by raising dust opacity for N sols."""
        self._dust_storm_remaining_sols = duration_sols
        self._dust_storm_opacity = DUST_STORM_OPACITY_TAU

        self.events.log(
            self.current_sol,
            "crisis",
            "energy",
            f"SCENARIO: Dust storm beginning — reduced solar for ~{duration_sols} sols",
            Severity.CRITICAL,
        )
        self.events.open_crisis(
            self.current_sol,
            CrisisType.DUST_STORM,
            Severity.CRITICAL,
            f"Dust storm active for {duration_sols} sols — opacity {self._dust_storm_opacity} tau",
            self._dust_storm_opacity,
            0.5,
        )

    def scenario_energy_disruption(self) -> None:
        """Drop battery to 10% of capacity."""
        self.energy.state.battery_level_wh = BATTERY_CAPACITY_WH * 0.10
        self.events.log(
            self.current_sol,
            "crisis",
            "energy",
            "SCENARIO: Energy disruption — battery dropped to 10%",
            Severity.CRITICAL,
        )
        self.events.open_crisis(
            self.current_sol,
            CrisisType.ENERGY_DISRUPTION,
            Severity.CRITICAL,
            "Energy disruption scenario injected",
            self.energy.battery_pct,
            10.0,
        )

    # ------------------------------------------------------------------
    # Agent decision log
    # ------------------------------------------------------------------

    def log_agent_decision(self, decision: AgentDecision) -> None:
        self.agent_decisions.append(decision)

    # ------------------------------------------------------------------
    # Derived telemetry helpers
    # ------------------------------------------------------------------

    def sensor_readings(self) -> list[dict[str, Any]]:
        """Generate sensor readings from current state, with active sensor noise injected."""
        noise = self.autonomous_events.sensor_noise
        readings: list[dict[str, Any]] = []
        for zone_id, zone in self.climate.state.items():
            temp_key = f"temp_{zone_id}"
            co2_key = f"co2_{zone_id}"
            readings += [
                {
                    "sensor_id": f"temp_{zone_id}_1",
                    "zone": zone_id,
                    "type": "temperature",
                    "value": noise.get(temp_key, zone.temp_c),
                    "unit": "celsius",
                    "status": "fault" if temp_key in noise else "ok",
                },
                {
                    "sensor_id": f"hum_{zone_id}_1",
                    "zone": zone_id,
                    "type": "humidity",
                    "value": zone.humidity_pct,
                    "unit": "percent",
                    "status": "ok",
                },
                {
                    "sensor_id": f"co2_{zone_id}_1",
                    "zone": zone_id,
                    "type": "co2",
                    "value": noise.get(co2_key, round(zone.co2_ppm, 1)),
                    "unit": "ppm",
                    "status": "fault" if co2_key in noise else "ok",
                },
                {
                    "sensor_id": f"par_{zone_id}_1",
                    "zone": zone_id,
                    "type": "par",
                    "value": zone.par_umol_m2s,
                    "unit": "umol/m2/s",
                    "status": "ok",
                },
            ]
            nutr = self.nutrients.state.get(zone_id)
            if nutr:
                readings += [
                    {
                        "sensor_id": f"ph_{zone_id}_1",
                        "zone": zone_id,
                        "type": "ph",
                        "value": nutr.solution_ph,
                        "unit": "ph",
                        "status": "ok",
                    },
                    {
                        "sensor_id": f"ec_{zone_id}_1",
                        "zone": zone_id,
                        "type": "ec",
                        "value": nutr.solution_ec_ms_cm,
                        "unit": "mS/cm",
                        "status": "ok",
                    },
                    {
                        "sensor_id": f"do_{zone_id}_1",
                        "zone": zone_id,
                        "type": "dissolved_oxygen",
                        "value": nutr.dissolved_o2_ppm,
                        "unit": "ppm",
                        "status": "ok",
                    },
                ]
        # External temperature
        w = self.weather.current()
        if w:
            readings.append(
                {
                    "sensor_id": "temp_external",
                    "zone": "external",
                    "type": "temperature",
                    "value": w.avg_temp_c,
                    "unit": "celsius",
                    "status": "ok",
                }
            )
        return readings


# ------------------------------------------------------------------
# Private helpers
# ------------------------------------------------------------------


def _apply_difficulty(engine: SimulationEngine, difficulty: Difficulty) -> None:
    if difficulty == Difficulty.EASY:
        engine.water.state.reservoir_liters = 600.0
        engine.crew.state.stored_kcal = 4_500_000.0  # ~375-sol buffer
        engine.crew.state.stored_protein_g = 180_000.0
        engine.energy.state.battery_level_wh = 25_000.0 * 0.6
    elif difficulty == Difficulty.HARD:
        engine.water.state.reservoir_liters = 350.0
        engine.crew.state.stored_kcal = 2_400_000.0  # ~200-sol buffer
        engine.crew.state.stored_protein_g = 90_000.0
        engine.energy.state.battery_level_wh = 15_000.0 * 0.6
    # NORMAL = defaults (already set by dataclasses)
