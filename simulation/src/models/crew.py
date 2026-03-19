"""
Crew Sub-Model — Nutrition + Health.

Two interrelated state machines:

  CrewNutritionState  — food/calorie/protein tracking (pre-existing logic)
  CrewHealthState     — hydration, radiation, CO2, temperature, starvation

Health constants are sourced from:
  IOM 2004 / WHO StatPearls NBK555956  — hydration thresholds
  Hassler et al. 2014, Science 343     — Mars radiation (Curiosity RAD)
  NASA-STD-3001 Vol.1 Rev.B            — radiation career limits
  OSHA 1910.1000 / NIOSH NPG           — CO2 limits
  NASA-STD-3001 Vol.2 §6.2.1           — habitat temperature bounds
  WHO TRS 724 / Minnesota Study        — starvation timeline
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Optional

from src.constants import (
    CO2_CRITICAL_PPM,
    CO2_DANGER_PPM,
    CO2_IMPAIRMENT_PPM,
    CREW_DAILY_KCAL,
    CREW_DAILY_PROTEIN_G,
    CREW_DAILY_WATER_L,
    CREW_RADIATION_DOSE_PER_SOL,
    CREW_SIZE,
    CREW_TEMP_CRITICAL_HIGH_C,
    CREW_TEMP_CRITICAL_LOW_C,
    CREW_TEMP_HEATSTROKE_RISK_C,
    CREW_TEMP_HYPOTHERMIA_RISK_C,
    DEHYDRATION_RATE_PCT_PER_SOL,
    HYDRATION_CRITICAL_PCT,
    HYDRATION_MILD_PCT,
    HYDRATION_MODERATE_PCT,
    HYDRATION_RECOVERY_RATE_PCT_PER_SOL,
    HYDRATION_SEVERE_PCT,
    INITIAL_STORED_KCAL,
    INITIAL_STORED_PROTEIN_G,
    RADIATION_CRITICAL_MSV,
    RADIATION_FATAL_MSV,
    RADIATION_WARNING_MSV,
    STARVATION_CALORIC_THRESHOLD_PCT,
    STARVATION_CRITICAL_DEFICIT_SOLS,
    STARVATION_ONSET_DEFICIT_SOLS,
    STARVATION_SEVERE_DEFICIT_SOLS,
)
from src.enums import CrewCauseOfDeath, CrewStatus, DehydrationLevel, StarvationLevel


# ─────────────────────────────────────────────────────────────────────────────
# Individual crew member
# ─────────────────────────────────────────────────────────────────────────────

CREW_MEMBER_NAMES = ["Dr. Chen (Commander)", "Eng. Osei (Engineer)", "Dr. Volkov (Botanist)", "Dr. Patel (Medic)"]


@dataclass
class CrewMember:
    """Per-person health snapshot. All 4 share the same habitat conditions."""
    member_id: str
    name: str
    health_pct: float = 100.0
    hydration_pct: float = 100.0
    cumulative_radiation_msv: float = 0.0
    alive: bool = True
    status: CrewStatus = CrewStatus.NOMINAL


# ─────────────────────────────────────────────────────────────────────────────
# Nutrition state (original logic, unchanged)
# ─────────────────────────────────────────────────────────────────────────────

@dataclass
class CrewNutritionState:
    stored_kcal: float = INITIAL_STORED_KCAL
    stored_protein_g: float = INITIAL_STORED_PROTEIN_G
    fresh_buffer_kcal: float = 0.0
    fresh_buffer_protein_g: float = 0.0
    today_kcal_consumed: float = 0.0
    today_kcal_target: float = float(CREW_DAILY_KCAL)
    today_protein_consumed_g: float = 0.0
    today_protein_target_g: float = float(CREW_DAILY_PROTEIN_G)
    from_greenhouse_pct: float = 0.0
    from_stored_pct: float = 100.0
    cumulative_avg_kcal: float = float(CREW_DAILY_KCAL)
    cumulative_avg_protein_g: float = float(CREW_DAILY_PROTEIN_G)
    deficit_sols: int = 0
    surplus_sols: int = 0
    total_sols_tracked: int = 0
    crew_status: CrewStatus = CrewStatus.NOMINAL
    micronutrients_sufficient: bool = False


# ─────────────────────────────────────────────────────────────────────────────
# Health state
# ─────────────────────────────────────────────────────────────────────────────

@dataclass
class CrewHealthState:
    # ── Hydration ────────────────────────────────────────────────────────────
    hydration_pct: float = 100.0
    daily_water_received_l: float = 0.0
    daily_water_required_l: float = float(CREW_DAILY_WATER_L)
    water_fraction_met: float = 1.0
    dehydration_level: DehydrationLevel = DehydrationLevel.HYDRATED
    consecutive_water_deficit_sols: int = 0

    # ── Radiation ────────────────────────────────────────────────────────────
    cumulative_radiation_msv: float = 0.0
    daily_radiation_msv: float = float(CREW_RADIATION_DOSE_PER_SOL)
    radiation_warning_active: bool = False
    radiation_critical_active: bool = False

    # ── Temperature health ───────────────────────────────────────────────────
    ambient_temp_c: float = 21.0
    hypothermia_risk: bool = False
    hyperthermia_risk: bool = False
    temperature_health_penalty: float = 0.0

    # ── CO2 health ───────────────────────────────────────────────────────────
    ambient_co2_ppm: float = 1000.0
    co2_health_impaired: bool = False
    co2_health_penalty: float = 0.0

    # ── Starvation ───────────────────────────────────────────────────────────
    starvation_level: StarvationLevel = StarvationLevel.FED
    consecutive_caloric_deficit_sols: int = 0
    starvation_health_penalty: float = 0.0

    # ── Overall health ───────────────────────────────────────────────────────
    overall_health_pct: float = 100.0
    alive: bool = True
    cause_of_death: Optional[str] = None

    # ── Individual crew members ──────────────────────────────────────────────
    members: list = field(default_factory=lambda: [
        CrewMember(member_id=f"crew_{i + 1}", name=CREW_MEMBER_NAMES[i])
        for i in range(CREW_SIZE)
    ])


# ─────────────────────────────────────────────────────────────────────────────
# Rate variables
# ─────────────────────────────────────────────────────────────────────────────

@dataclass
class CrewRates:
    d_stored_kcal: float = 0.0
    d_stored_protein_g: float = 0.0
    d_hydration: float = 0.0


# ─────────────────────────────────────────────────────────────────────────────
# CrewModel
# ─────────────────────────────────────────────────────────────────────────────

class CrewModel:
    """
    State variables : stored food, fresh buffer, daily intake, hydration, radiation, health
    Rate variables  : daily food draw, daily hydration change
    """

    def __init__(self) -> None:
        self.state = CrewNutritionState()
        self.health = CrewHealthState()
        self.rates = CrewRates()
        self._total_kcal_consumed: float = 0.0
        self._total_protein_consumed: float = 0.0

    # ─────────────────────────────────────────────────────────────────────────
    # PCSE lifecycle
    # ─────────────────────────────────────────────────────────────────────────

    def calc_rates(
        self,
        water_reservoir_l: float,
        avg_temp_c: float,
        avg_co2_ppm: float,
    ) -> None:
        """Compute daily rates for food draw and hydration change."""
        # ── Nutrition rates ───────────────────────────────────────────────
        fresh_kcal = min(self.state.fresh_buffer_kcal, CREW_DAILY_KCAL)
        fresh_protein = min(self.state.fresh_buffer_protein_g, CREW_DAILY_PROTEIN_G)
        self.rates.d_stored_kcal = -max(0.0, CREW_DAILY_KCAL - fresh_kcal)
        self.rates.d_stored_protein_g = -max(0.0, CREW_DAILY_PROTEIN_G - fresh_protein)

        # ── Hydration rate ────────────────────────────────────────────────
        water_available = min(float(CREW_DAILY_WATER_L), water_reservoir_l)
        self.health.water_fraction_met = water_available / CREW_DAILY_WATER_L if CREW_DAILY_WATER_L > 0 else 1.0
        self.health.daily_water_received_l = round(water_available, 2)

        deficit_fraction = max(0.0, 1.0 - self.health.water_fraction_met)
        dehydration_loss = deficit_fraction * DEHYDRATION_RATE_PCT_PER_SOL
        hydration_gain = self.health.water_fraction_met * HYDRATION_RECOVERY_RATE_PCT_PER_SOL * (
            (100.0 - self.health.hydration_pct) / 100.0
        )
        self.rates.d_hydration = hydration_gain - dehydration_loss

        # ── Cache health inputs ───────────────────────────────────────────
        self.health.ambient_temp_c = avg_temp_c
        self.health.ambient_co2_ppm = avg_co2_ppm

    def integrate(self) -> None:
        """Apply rates and update all health sub-systems."""
        self._integrate_nutrition()
        self._integrate_hydration()
        self._integrate_starvation()
        self._integrate_radiation()
        self._integrate_temperature()
        self._integrate_co2()
        self._compute_overall_health()
        self._sync_crew_members()

    # ─────────────────────────────────────────────────────────────────────────
    # Harvest callback
    # ─────────────────────────────────────────────────────────────────────────

    def add_harvest(self, kcal: float, protein_g: float, has_micronutrients: bool) -> None:
        self.state.fresh_buffer_kcal += kcal
        self.state.fresh_buffer_protein_g += protein_g
        if has_micronutrients:
            self.state.micronutrients_sufficient = True

    # ─────────────────────────────────────────────────────────────────────────
    # Properties (convenience)
    # ─────────────────────────────────────────────────────────────────────────

    @property
    def total_kcal(self) -> float:
        return self.state.stored_kcal + self.state.fresh_buffer_kcal

    @property
    def total_protein_g(self) -> float:
        return self.state.stored_protein_g + self.state.fresh_buffer_protein_g

    @property
    def days_of_food(self) -> float:
        return round(self.total_kcal / CREW_DAILY_KCAL, 1)

    @property
    def days_of_protein(self) -> float:
        return round(self.total_protein_g / CREW_DAILY_PROTEIN_G, 1)

    @property
    def is_alive(self) -> bool:
        return self.health.alive

    @property
    def hydration_pct(self) -> float:
        return self.health.hydration_pct

    @property
    def overall_health_pct(self) -> float:
        return self.health.overall_health_pct

    # ─────────────────────────────────────────────────────────────────────────
    # Private integration helpers
    # ─────────────────────────────────────────────────────────────────────────

    def _integrate_nutrition(self) -> None:
        fresh_kcal_used = min(self.state.fresh_buffer_kcal, CREW_DAILY_KCAL)
        fresh_protein_used = min(self.state.fresh_buffer_protein_g, CREW_DAILY_PROTEIN_G)
        self.state.fresh_buffer_kcal = max(0.0, self.state.fresh_buffer_kcal - fresh_kcal_used)
        self.state.fresh_buffer_protein_g = max(0.0, self.state.fresh_buffer_protein_g - fresh_protein_used)

        self.state.stored_kcal = max(0.0, self.state.stored_kcal + self.rates.d_stored_kcal)
        self.state.stored_protein_g = max(0.0, self.state.stored_protein_g + self.rates.d_stored_protein_g)

        actual_kcal = fresh_kcal_used + min(self.state.stored_kcal, -self.rates.d_stored_kcal)
        actual_protein = fresh_protein_used + min(self.state.stored_protein_g, -self.rates.d_stored_protein_g)
        self.state.today_kcal_consumed = round(actual_kcal, 1)
        self.state.today_protein_consumed_g = round(actual_protein, 1)

        total_food = fresh_kcal_used + (-self.rates.d_stored_kcal)
        self.state.from_greenhouse_pct = round(
            fresh_kcal_used / total_food * 100.0 if total_food > 0 else 0.0, 1
        )
        self.state.from_stored_pct = round(100.0 - self.state.from_greenhouse_pct, 1)

        self._total_kcal_consumed += actual_kcal
        self._total_protein_consumed += actual_protein
        self.state.total_sols_tracked += 1
        self.state.cumulative_avg_kcal = round(
            self._total_kcal_consumed / self.state.total_sols_tracked, 1
        )
        self.state.cumulative_avg_protein_g = round(
            self._total_protein_consumed / self.state.total_sols_tracked, 1
        )

        if actual_kcal < CREW_DAILY_KCAL * 0.9:
            self.state.deficit_sols += 1
        else:
            self.state.surplus_sols += 1

        self._update_nutrition_status()

    def _integrate_hydration(self) -> None:
        new_hydration = self.health.hydration_pct + self.rates.d_hydration
        self.health.hydration_pct = round(max(0.0, min(100.0, new_hydration)), 2)

        if self.health.water_fraction_met < 0.99:
            self.health.consecutive_water_deficit_sols += 1
        else:
            self.health.consecutive_water_deficit_sols = max(
                0, self.health.consecutive_water_deficit_sols - 1
            )

        h = self.health.hydration_pct
        if h >= HYDRATION_MILD_PCT:
            self.health.dehydration_level = DehydrationLevel.HYDRATED
        elif h >= HYDRATION_MODERATE_PCT:
            self.health.dehydration_level = DehydrationLevel.MILD
        elif h >= HYDRATION_SEVERE_PCT:
            self.health.dehydration_level = DehydrationLevel.MODERATE
        elif h >= HYDRATION_CRITICAL_PCT:
            self.health.dehydration_level = DehydrationLevel.SEVERE
        else:
            self.health.dehydration_level = DehydrationLevel.CRITICAL

        if self.health.hydration_pct <= 0.0 and self.health.alive:
            self.health.alive = False
            self.health.cause_of_death = CrewCauseOfDeath.DEHYDRATION.value

    def _integrate_starvation(self) -> None:
        kcal_fraction = (
            self.state.today_kcal_consumed / CREW_DAILY_KCAL if CREW_DAILY_KCAL > 0 else 1.0
        )
        if kcal_fraction < STARVATION_CALORIC_THRESHOLD_PCT:
            self.health.consecutive_caloric_deficit_sols += 1
        else:
            self.health.consecutive_caloric_deficit_sols = max(
                0, self.health.consecutive_caloric_deficit_sols - 1
            )

        deficit_sols = self.health.consecutive_caloric_deficit_sols
        if deficit_sols < STARVATION_ONSET_DEFICIT_SOLS:
            self.health.starvation_level = StarvationLevel.FED
            self.health.starvation_health_penalty = 0.0
        elif deficit_sols < STARVATION_SEVERE_DEFICIT_SOLS:
            self.health.starvation_level = StarvationLevel.UNDERFED
            self.health.starvation_health_penalty = round(
                (deficit_sols - STARVATION_ONSET_DEFICIT_SOLS) * 0.5, 2
            )
        elif deficit_sols < STARVATION_CRITICAL_DEFICIT_SOLS:
            self.health.starvation_level = StarvationLevel.MALNOURISHED
            self.health.starvation_health_penalty = round(
                (STARVATION_SEVERE_DEFICIT_SOLS - STARVATION_ONSET_DEFICIT_SOLS) * 0.5
                + (deficit_sols - STARVATION_SEVERE_DEFICIT_SOLS) * 2.0,
                2,
            )
        else:
            self.health.starvation_level = StarvationLevel.STARVING
            self.health.starvation_health_penalty = round(
                (STARVATION_SEVERE_DEFICIT_SOLS - STARVATION_ONSET_DEFICIT_SOLS) * 0.5
                + (STARVATION_CRITICAL_DEFICIT_SOLS - STARVATION_SEVERE_DEFICIT_SOLS) * 2.0
                + (deficit_sols - STARVATION_CRITICAL_DEFICIT_SOLS) * 4.0,
                2,
            )

    def _integrate_radiation(self) -> None:
        self.health.cumulative_radiation_msv = round(
            self.health.cumulative_radiation_msv + CREW_RADIATION_DOSE_PER_SOL, 3
        )
        self.health.radiation_warning_active = self.health.cumulative_radiation_msv >= RADIATION_WARNING_MSV
        self.health.radiation_critical_active = self.health.cumulative_radiation_msv >= RADIATION_CRITICAL_MSV

        if self.health.cumulative_radiation_msv >= RADIATION_FATAL_MSV and self.health.alive:
            self.health.alive = False
            self.health.cause_of_death = CrewCauseOfDeath.RADIATION.value

    def _integrate_temperature(self) -> None:
        t = self.health.ambient_temp_c

        if t < CREW_TEMP_HYPOTHERMIA_RISK_C:
            self.health.hypothermia_risk = True
            if t <= CREW_TEMP_CRITICAL_LOW_C:
                # Rapid hypothermia: up to 10% penalty per sol below 0°C
                self.health.temperature_health_penalty = round(abs(t) * 2.0, 2)
            else:
                # Gradual hypothermia risk
                self.health.temperature_health_penalty = round(
                    (CREW_TEMP_HYPOTHERMIA_RISK_C - t) * 0.5, 2
                )
        elif t > CREW_TEMP_HEATSTROKE_RISK_C:
            self.health.hyperthermia_risk = True
            if t >= CREW_TEMP_CRITICAL_HIGH_C:
                self.health.temperature_health_penalty = round((t - CREW_TEMP_CRITICAL_HIGH_C) * 3.0, 2)
            else:
                self.health.temperature_health_penalty = round(
                    (t - CREW_TEMP_HEATSTROKE_RISK_C) * 1.0, 2
                )
        else:
            self.health.hypothermia_risk = False
            self.health.hyperthermia_risk = False
            self.health.temperature_health_penalty = 0.0

    def _integrate_co2(self) -> None:
        co2 = self.health.ambient_co2_ppm
        if co2 >= CO2_DANGER_PPM:
            self.health.co2_health_impaired = True
            self.health.co2_health_penalty = round((co2 - CO2_DANGER_PPM) / 1000.0 * 10.0 + 15.0, 2)
        elif co2 >= CO2_CRITICAL_PPM:
            self.health.co2_health_impaired = True
            self.health.co2_health_penalty = round((co2 - CO2_CRITICAL_PPM) / 1000.0 * 5.0 + 5.0, 2)
        elif co2 >= CO2_IMPAIRMENT_PPM:
            self.health.co2_health_impaired = True
            self.health.co2_health_penalty = round((co2 - CO2_IMPAIRMENT_PPM) / 1000.0 * 2.0, 2)
        else:
            self.health.co2_health_impaired = False
            self.health.co2_health_penalty = 0.0

    def _compute_overall_health(self) -> None:
        if not self.health.alive:
            self.health.overall_health_pct = 0.0
            for m in self.health.members:
                m.alive = False
                m.health_pct = 0.0
                m.status = CrewStatus.DEAD
            return

        # Dehydration penalty: starts at moderate level (80%)
        h = self.health.hydration_pct
        if h >= HYDRATION_MODERATE_PCT:
            dehydration_penalty = 0.0
        elif h >= HYDRATION_SEVERE_PCT:
            dehydration_penalty = (HYDRATION_MODERATE_PCT - h) * 1.0
        elif h >= HYDRATION_CRITICAL_PCT:
            dehydration_penalty = (
                (HYDRATION_MODERATE_PCT - HYDRATION_SEVERE_PCT) * 1.0
                + (HYDRATION_SEVERE_PCT - h) * 2.0
            )
        else:
            dehydration_penalty = (
                (HYDRATION_MODERATE_PCT - HYDRATION_SEVERE_PCT) * 1.0
                + (HYDRATION_SEVERE_PCT - HYDRATION_CRITICAL_PCT) * 2.0
                + (HYDRATION_CRITICAL_PCT - h) * 4.0
            )

        # Radiation penalty: only above critical (500 mSv)
        r = self.health.cumulative_radiation_msv
        radiation_penalty = max(0.0, (r - RADIATION_CRITICAL_MSV) / 50.0)

        total_penalty = (
            dehydration_penalty
            + self.health.starvation_health_penalty
            + self.health.temperature_health_penalty
            + self.health.co2_health_penalty
            + radiation_penalty
        )
        score = round(max(0.0, 100.0 - total_penalty), 2)
        self.health.overall_health_pct = score

        # Kill crew if health reaches 0 from any cause
        if score <= 0.0 and self.health.alive:
            self.health.alive = False
            if self.health.dehydration_level == DehydrationLevel.CRITICAL:
                self.health.cause_of_death = CrewCauseOfDeath.DEHYDRATION.value
            elif self.health.starvation_level == StarvationLevel.STARVING:
                self.health.cause_of_death = CrewCauseOfDeath.STARVATION.value
            elif self.health.hypothermia_risk:
                self.health.cause_of_death = CrewCauseOfDeath.HYPOTHERMIA.value
            elif self.health.hyperthermia_risk:
                self.health.cause_of_death = CrewCauseOfDeath.HYPERTHERMIA.value
            elif self.health.co2_health_impaired:
                self.health.cause_of_death = CrewCauseOfDeath.CO2_TOXICITY.value
            else:
                self.health.cause_of_death = "unknown"

    def _sync_crew_members(self) -> None:
        """Propagate shared health state to individual crew member records."""
        for m in self.health.members:
            m.alive = self.health.alive
            m.health_pct = round(self.health.overall_health_pct, 1)
            m.hydration_pct = round(self.health.hydration_pct, 1)
            m.cumulative_radiation_msv = round(self.health.cumulative_radiation_msv, 2)
            if not m.alive:
                m.status = CrewStatus.DEAD
            elif m.health_pct < 40:
                m.status = CrewStatus.CRITICAL
            elif m.health_pct < 75:
                m.status = CrewStatus.WARNING
            else:
                m.status = CrewStatus.NOMINAL

    def _update_nutrition_status(self) -> None:
        total = self.state.stored_kcal + self.state.fresh_buffer_kcal
        days_food = total / CREW_DAILY_KCAL if CREW_DAILY_KCAL > 0 else 999
        if days_food < 2:
            self.state.crew_status = CrewStatus.CRITICAL
        elif days_food < 10:
            self.state.crew_status = CrewStatus.WARNING
        else:
            self.state.crew_status = CrewStatus.NOMINAL
