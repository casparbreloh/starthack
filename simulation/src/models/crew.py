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

import random
from dataclasses import dataclass, field

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
    ILLNESS_KCAL_MULTIPLIER,
    ILLNESS_MAX_DURATION_SOLS,
    ILLNESS_MIN_DURATION_SOLS,
    ILLNESS_PROBABILITY_PER_SOL,
    ILLNESS_PROTEIN_MULTIPLIER,
    INITIAL_FOOD_KG,
    INITIAL_STORED_KCAL,
    INITIAL_STORED_PROTEIN_G,
    MICRONUTRIENT_ONSET_DEFICIT_SOLS,
    MICRONUTRIENT_PENALTY_DEFICIENT_PER_SOL,
    MICRONUTRIENT_PENALTY_DEPLETED_PER_SOL,
    MICRONUTRIENT_SEVERE_DEFICIT_SOLS,
    RADIATION_CRITICAL_MSV,
    RADIATION_FATAL_MSV,
    RADIATION_WARNING_MSV,
    STARVATION_CRITICAL_DEFICIT_SOLS,
    STARVATION_DEFICIT_THRESHOLD_PCT,
    STARVATION_FULL_RECOVERY_THRESHOLD_PCT,
    STARVATION_ONSET_DEFICIT_SOLS,
    STARVATION_PENALTY_MALNOURISHED_PER_SOL,
    STARVATION_PENALTY_STARVING_PER_SOL,
    STARVATION_PENALTY_UNDERFED_PER_SOL,
    STARVATION_SEVERE_DEFICIT_SOLS,
)
from src.enums import (
    CrewCauseOfDeath,
    CrewStatus,
    DehydrationLevel,
    MicronutrientLevel,
    StarvationLevel,
)

# ─────────────────────────────────────────────────────────────────────────────
# Individual crew member
# ─────────────────────────────────────────────────────────────────────────────

CREW_MEMBER_NAMES = [
    "Dr. Chen (Commander)",
    "Eng. Osei (Engineer)",
    "Dr. Volkov (Botanist)",
    "Dr. Patel (Medic)",
]


@dataclass
class CrewMember:
    """Per-person health snapshot.

    Individual crew differentiation is not yet implemented — all crew members
    share identical health values from the shared habitat model.
    """

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
    # Per-food-type pantry (kg). Drawn down proportionally as stored_kcal depletes.
    stored_food_kg: dict = field(default_factory=lambda: dict(INITIAL_FOOD_KG))
    fresh_buffer_kcal: float = 0.0
    fresh_buffer_protein_g: float = 0.0
    today_kcal_consumed: float = 0.0
    today_kcal_target: float = CREW_DAILY_KCAL
    today_protein_consumed_g: float = 0.0
    today_protein_target_g: float = CREW_DAILY_PROTEIN_G
    from_greenhouse_pct: float = 0.0
    from_stored_pct: float = 100.0
    cumulative_avg_kcal: float = CREW_DAILY_KCAL
    cumulative_avg_protein_g: float = CREW_DAILY_PROTEIN_G
    deficit_sols: int = 0
    surplus_sols: int = 0
    total_sols_tracked: int = 0
    crew_status: CrewStatus = CrewStatus.NOMINAL
    micronutrients_sufficient: bool = False


# ─────────────────────────────────────────────────────────────────────────────
# Health state
# ─────────────────────────────────────────────────────────────────────────────


@dataclass
class IllnessState:
    """Tracks a single active crew illness event."""

    active: bool = False
    sick_member_id: str | None = None
    sick_member_name: str | None = None
    duration_remaining_sols: int = 0
    kcal_multiplier: float = 1.0
    protein_multiplier: float = 1.0


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

    # ── Micronutrients ───────────────────────────────────────────────────────
    micronutrient_level: MicronutrientLevel = MicronutrientLevel.ADEQUATE
    consecutive_micronutrient_deficit_sols: int = 0
    micronutrient_health_penalty: float = 0.0

    # ── Illness ──────────────────────────────────────────────────────────────
    illness: IllnessState = field(default_factory=IllnessState)

    # ── Overall health ───────────────────────────────────────────────────────
    overall_health_pct: float = 100.0
    alive: bool = True
    cause_of_death: str | None = None

    # ── Individual crew members ──────────────────────────────────────────────
    members: list[CrewMember] = field(
        default_factory=lambda: [
            CrewMember(member_id=f"crew_{i + 1}", name=CREW_MEMBER_NAMES[i])
            for i in range(CREW_SIZE)
        ]
    )


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
        # Starvation level-change events produced this tick; drained by the engine.
        # Each entry: (category, message, severity_str)
        self.pending_events: list[tuple[str, str, str]] = []

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
        water_available = min(CREW_DAILY_WATER_L, water_reservoir_l)
        self.health.water_fraction_met = (
            water_available / CREW_DAILY_WATER_L if CREW_DAILY_WATER_L > 0 else 1.0
        )
        self.health.daily_water_received_l = round(water_available, 2)

        deficit_fraction = max(0.0, 1.0 - self.health.water_fraction_met)
        dehydration_loss = deficit_fraction * DEHYDRATION_RATE_PCT_PER_SOL
        hydration_gain = (
            self.health.water_fraction_met
            * HYDRATION_RECOVERY_RATE_PCT_PER_SOL
            * ((100.0 - self.health.hydration_pct) / 100.0)
        )
        self.rates.d_hydration = hydration_gain - dehydration_loss

        # ── Cache health inputs ───────────────────────────────────────────
        self.health.ambient_temp_c = avg_temp_c
        self.health.ambient_co2_ppm = avg_co2_ppm

    def integrate(self, current_sol: int = 0) -> None:
        """Apply rates and update all health sub-systems."""
        self.pending_events.clear()
        self._integrate_nutrition()
        self._integrate_illness(current_sol)
        self._integrate_hydration()
        self._integrate_starvation()
        self._integrate_micronutrients()
        self._integrate_radiation()
        self._integrate_temperature()
        self._integrate_co2()
        self._compute_overall_health()
        self._sync_crew_members()

    # ─────────────────────────────────────────────────────────────────────────
    # Harvest callback
    # ─────────────────────────────────────────────────────────────────────────

    def add_harvest(
        self, kcal: float, protein_g: float, has_micronutrients: bool
    ) -> None:
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
        fresh_protein_used = min(
            self.state.fresh_buffer_protein_g, CREW_DAILY_PROTEIN_G
        )
        self.state.fresh_buffer_kcal = max(
            0.0, self.state.fresh_buffer_kcal - fresh_kcal_used
        )
        self.state.fresh_buffer_protein_g = max(
            0.0, self.state.fresh_buffer_protein_g - fresh_protein_used
        )

        stored_kcal_before = self.state.stored_kcal
        stored_protein_before = self.state.stored_protein_g
        self.state.stored_kcal = max(
            0.0, self.state.stored_kcal + self.rates.d_stored_kcal
        )
        self.state.stored_protein_g = max(
            0.0, self.state.stored_protein_g + self.rates.d_stored_protein_g
        )

        actual_kcal = fresh_kcal_used + (stored_kcal_before - self.state.stored_kcal)
        actual_protein = fresh_protein_used + (
            stored_protein_before - self.state.stored_protein_g
        )

        # Proportionally draw down per-food-type pantry as stored_kcal depletes
        consumed_from_stored = stored_kcal_before - self.state.stored_kcal
        if stored_kcal_before > 0 and consumed_from_stored > 0:
            fraction = consumed_from_stored / stored_kcal_before
            for food_type in self.state.stored_food_kg:
                self.state.stored_food_kg[food_type] = max(
                    0.0, self.state.stored_food_kg[food_type] * (1.0 - fraction)
                )

        self.state.today_kcal_consumed = round(actual_kcal, 1)
        self.state.today_protein_consumed_g = round(actual_protein, 1)

        self.state.from_greenhouse_pct = round(
            fresh_kcal_used / actual_kcal * 100.0 if actual_kcal > 0 else 0.0, 1
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

    def _integrate_illness(self, current_sol: int) -> None:
        """
        Random crew illness events (~2 per 450-sol mission).

        While ill, the daily caloric and protein targets are elevated so the
        existing starvation counter rises faster if the agent fails to provide
        sufficient food.  A random alive crew member is named in the event log.
        """
        illness = self.health.illness

        if illness.active:
            illness.duration_remaining_sols -= 1
            if illness.duration_remaining_sols <= 0:
                # Recovery
                illness.active = False
                illness.kcal_multiplier = 1.0
                illness.protein_multiplier = 1.0
                self.state.today_kcal_target = float(CREW_DAILY_KCAL)
                self.state.today_protein_target_g = float(CREW_DAILY_PROTEIN_G)
                msg = (
                    f"SUCCESS: {illness.sick_member_name} has recovered from illness. "
                    f"Nutritional requirements return to normal."
                )
                self.pending_events.append(("crew_illness", msg, "info"))
                illness.sick_member_id = None
                illness.sick_member_name = None
            else:
                # Keep elevated targets for today
                self.state.today_kcal_target = round(
                    CREW_DAILY_KCAL * illness.kcal_multiplier, 1
                )
                self.state.today_protein_target_g = round(
                    CREW_DAILY_PROTEIN_G * illness.protein_multiplier, 1
                )
        else:
            # Reset targets to baseline (guards against stale values)
            self.state.today_kcal_target = float(CREW_DAILY_KCAL)
            self.state.today_protein_target_g = float(CREW_DAILY_PROTEIN_G)

            # Only trigger new illness after sol 10 and when at least one alive
            alive_members = [m for m in self.health.members if m.alive]
            if (
                current_sol >= 10
                and alive_members
                and random.random() < ILLNESS_PROBABILITY_PER_SOL
            ):
                sick = random.choice(alive_members)
                duration = random.randint(
                    ILLNESS_MIN_DURATION_SOLS, ILLNESS_MAX_DURATION_SOLS
                )
                illness.active = True
                illness.sick_member_id = sick.member_id
                illness.sick_member_name = sick.name
                illness.duration_remaining_sols = duration
                illness.kcal_multiplier = ILLNESS_KCAL_MULTIPLIER
                illness.protein_multiplier = ILLNESS_PROTEIN_MULTIPLIER
                self.state.today_kcal_target = round(
                    CREW_DAILY_KCAL * ILLNESS_KCAL_MULTIPLIER, 1
                )
                self.state.today_protein_target_g = round(
                    CREW_DAILY_PROTEIN_G * ILLNESS_PROTEIN_MULTIPLIER, 1
                )
                kcal_extra = round((ILLNESS_KCAL_MULTIPLIER - 1) * 100)
                protein_extra = round((ILLNESS_PROTEIN_MULTIPLIER - 1) * 100)
                msg = (
                    f"WARNING: {sick.name} has fallen ill (sol {current_sol}). "
                    f"Crew requires +{kcal_extra}% calories and +{protein_extra}% protein "
                    f"for recovery over the next {duration} sols."
                )
                self.pending_events.append(("crew_illness", msg, "warning"))

    def _integrate_starvation(self) -> None:
        previous_level = self.health.starvation_level

        kcal_fraction = (
            self.state.today_kcal_consumed / self.state.today_kcal_target
            if self.state.today_kcal_target > 0
            else 1.0
        )

        # ── 1. Asymmetric recovery ────────────────────────────────────
        # Fully fed (≥100 %): fast recovery —3 sols/tick.
        # Mildly fed (80–100 %): slow recovery −1 sol/tick.
        # Deficit (<80 %): deterioration +1 sol/tick.
        if kcal_fraction >= STARVATION_FULL_RECOVERY_THRESHOLD_PCT:
            self.health.consecutive_caloric_deficit_sols = max(
                0, self.health.consecutive_caloric_deficit_sols - 3
            )
        elif kcal_fraction >= STARVATION_DEFICIT_THRESHOLD_PCT:
            self.health.consecutive_caloric_deficit_sols = max(
                0, self.health.consecutive_caloric_deficit_sols - 1
            )
        else:
            self.health.consecutive_caloric_deficit_sols += 1

        # ── 2. Hardcore thresholds & cumulative penalty ───────────────
        # Tiers: 0–2 FED, 3–6 UNDERFED (+2/sol), 7–10 MALNOURISHED (+5/sol),
        #        11+ STARVING (+10/sol) → death ~18 consecutive deficit sols.
        deficit_sols = self.health.consecutive_caloric_deficit_sols

        _underfed_span = (
            STARVATION_SEVERE_DEFICIT_SOLS - STARVATION_ONSET_DEFICIT_SOLS
        )  # 4
        _malnourished_span = (
            STARVATION_CRITICAL_DEFICIT_SOLS - STARVATION_SEVERE_DEFICIT_SOLS
        )  # 4
        _max_underfed_penalty = (
            _underfed_span * STARVATION_PENALTY_UNDERFED_PER_SOL
        )  # 8
        _max_malnourished_penalty = (
            _malnourished_span * STARVATION_PENALTY_MALNOURISHED_PER_SOL
        )  # 20

        if deficit_sols < STARVATION_ONSET_DEFICIT_SOLS:
            self.health.starvation_level = StarvationLevel.FED
            self.health.starvation_health_penalty = 0.0
        elif deficit_sols < STARVATION_SEVERE_DEFICIT_SOLS:
            self.health.starvation_level = StarvationLevel.UNDERFED
            self.health.starvation_health_penalty = round(
                (deficit_sols - STARVATION_ONSET_DEFICIT_SOLS + 1)
                * STARVATION_PENALTY_UNDERFED_PER_SOL,
                2,
            )
        elif deficit_sols < STARVATION_CRITICAL_DEFICIT_SOLS:
            self.health.starvation_level = StarvationLevel.MALNOURISHED
            self.health.starvation_health_penalty = round(
                _max_underfed_penalty
                + (deficit_sols - STARVATION_SEVERE_DEFICIT_SOLS + 1)
                * STARVATION_PENALTY_MALNOURISHED_PER_SOL,
                2,
            )
        else:
            self.health.starvation_level = StarvationLevel.STARVING
            self.health.starvation_health_penalty = round(
                _max_underfed_penalty
                + _max_malnourished_penalty
                + (deficit_sols - STARVATION_CRITICAL_DEFICIT_SOLS + 1)
                * STARVATION_PENALTY_STARVING_PER_SOL,
                2,
            )

        # ── 3. Early-warning events on level transition ───────────────
        current_level = self.health.starvation_level
        if current_level != previous_level:
            self._emit_starvation_transition(
                previous_level, current_level, kcal_fraction
            )

    def _emit_starvation_transition(
        self,
        previous: StarvationLevel,
        current: StarvationLevel,
        kcal_fraction: float,
    ) -> None:
        """Append a starvation-level-change event to pending_events for the engine to log."""
        kcal_pct = round(kcal_fraction * 100, 1)
        transition = f"{previous.value} → {current.value}"
        if current == StarvationLevel.FED:
            msg = (
                f"SUCCESS: Crew has recovered and is now FED [{transition}] "
                f"(caloric intake {kcal_pct}% of target)."
            )
            sev = "info"
        elif current == StarvationLevel.UNDERFED:
            msg = (
                f"WARNING: Crew is now UNDERFED [{transition}]. "
                f"Caloric deficit detected ({kcal_pct}% of target). "
                f"Increase food production or harvest reserves."
            )
            sev = "warning"
        elif current == StarvationLevel.MALNOURISHED:
            msg = (
                f"CRITICAL: Crew is MALNOURISHED [{transition}]. "
                f"Health degrading at {STARVATION_PENALTY_MALNOURISHED_PER_SOL:.0f}%/sol. "
                f"Immediate harvest required ({kcal_pct}% kcal met)."
            )
            sev = "critical"
        else:  # STARVING
            msg = (
                f"CRITICAL: Crew is STARVING [{transition}]. "
                f"Health degrading at {STARVATION_PENALTY_STARVING_PER_SOL:.0f}%/sol — "
                f"death imminent without food ({kcal_pct}% kcal met)."
            )
            sev = "critical"
        self.pending_events.append(("crew_starvation", msg, sev))

    def _integrate_micronutrients(self) -> None:
        """
        Track crew micronutrient status based on fresh crop intake each sol.

        micronutrients_sufficient is set to True by add_harvest() whenever a
        crop with provides_micronutrients=True is harvested this sol.  We read
        and reset the flag here so each sol starts with a clean slate.

        Levels (consecutive sols without fresh micronutrients):
          0–6  ADEQUATE  — no penalty
          7–20 DEFICIENT — subclinical: fatigue, immune decline (+1 %/sol)
          21+  DEPLETED  — clinical: scurvy, bone loss, organ stress (+3 %/sol)
        """
        previous_level = self.health.micronutrient_level

        # Consume the per-sol flag set by add_harvest(); reset for next sol.
        received = self.state.micronutrients_sufficient
        self.state.micronutrients_sufficient = False

        if received:
            # Recovery: −2 per sol when micronutrients supplied
            self.health.consecutive_micronutrient_deficit_sols = max(
                0, self.health.consecutive_micronutrient_deficit_sols - 2
            )
        else:
            self.health.consecutive_micronutrient_deficit_sols += 1

        deficit_sols = self.health.consecutive_micronutrient_deficit_sols
        _deficient_span = (
            MICRONUTRIENT_SEVERE_DEFICIT_SOLS - MICRONUTRIENT_ONSET_DEFICIT_SOLS
        )  # 14
        _max_deficient_penalty = (
            _deficient_span * MICRONUTRIENT_PENALTY_DEFICIENT_PER_SOL
        )  # 14.0

        if deficit_sols < MICRONUTRIENT_ONSET_DEFICIT_SOLS:
            self.health.micronutrient_level = MicronutrientLevel.ADEQUATE
            self.health.micronutrient_health_penalty = 0.0
        elif deficit_sols < MICRONUTRIENT_SEVERE_DEFICIT_SOLS:
            self.health.micronutrient_level = MicronutrientLevel.DEFICIENT
            self.health.micronutrient_health_penalty = round(
                (deficit_sols - MICRONUTRIENT_ONSET_DEFICIT_SOLS + 1)
                * MICRONUTRIENT_PENALTY_DEFICIENT_PER_SOL,
                2,
            )
        else:
            self.health.micronutrient_level = MicronutrientLevel.DEPLETED
            self.health.micronutrient_health_penalty = round(
                _max_deficient_penalty
                + (deficit_sols - MICRONUTRIENT_SEVERE_DEFICIT_SOLS + 1)
                * MICRONUTRIENT_PENALTY_DEPLETED_PER_SOL,
                2,
            )

        # Emit a warning event on level transition
        current_level = self.health.micronutrient_level
        if current_level != previous_level:
            self._emit_micronutrient_transition(previous_level, current_level)

    def _emit_micronutrient_transition(
        self,
        previous: MicronutrientLevel,
        current: MicronutrientLevel,
    ) -> None:
        transition = f"{previous.value} → {current.value}"
        if current == MicronutrientLevel.ADEQUATE:
            msg = (
                f"SUCCESS: Crew micronutrient levels restored [{transition}]. "
                f"Fresh crop supply re-established."
            )
            sev = "info"
        elif current == MicronutrientLevel.DEFICIENT:
            msg = (
                f"WARNING: Crew micronutrient DEFICIENT [{transition}]. "
                f"No fresh vitamin/mineral source for {self.health.consecutive_micronutrient_deficit_sols} sols. "
                f"Harvest lettuce or other micronutrient crops immediately."
            )
            sev = "warning"
        else:  # DEPLETED
            msg = (
                f"CRITICAL: Crew micronutrients DEPLETED [{transition}]. "
                f"Clinical deficiency after {self.health.consecutive_micronutrient_deficit_sols} sols — "
                f"health degrading at {MICRONUTRIENT_PENALTY_DEPLETED_PER_SOL:.0f}%/sol. "
                f"Urgent: plant and harvest lettuce."
            )
            sev = "critical"
        self.pending_events.append(("crew_micronutrient", msg, sev))

    def _integrate_radiation(self) -> None:
        self.health.cumulative_radiation_msv = round(
            self.health.cumulative_radiation_msv + CREW_RADIATION_DOSE_PER_SOL, 3
        )
        self.health.radiation_warning_active = (
            self.health.cumulative_radiation_msv >= RADIATION_WARNING_MSV
        )
        self.health.radiation_critical_active = (
            self.health.cumulative_radiation_msv >= RADIATION_CRITICAL_MSV
        )

        if (
            self.health.cumulative_radiation_msv >= RADIATION_FATAL_MSV
            and self.health.alive
        ):
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
                self.health.temperature_health_penalty = round(
                    (t - CREW_TEMP_CRITICAL_HIGH_C) * 3.0, 2
                )
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
            self.health.co2_health_penalty = round(
                (co2 - CO2_DANGER_PPM) / 1000.0 * 10.0 + 15.0, 2
            )
        elif co2 >= CO2_CRITICAL_PPM:
            self.health.co2_health_impaired = True
            self.health.co2_health_penalty = round(
                (co2 - CO2_CRITICAL_PPM) / 1000.0 * 5.0 + 5.0, 2
            )
        elif co2 >= CO2_IMPAIRMENT_PPM:
            self.health.co2_health_impaired = True
            self.health.co2_health_penalty = round(
                (co2 - CO2_IMPAIRMENT_PPM) / 1000.0 * 2.0, 2
            )
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
                HYDRATION_MODERATE_PCT - HYDRATION_SEVERE_PCT
            ) * 1.0 + (HYDRATION_SEVERE_PCT - h) * 2.0
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
            + self.health.micronutrient_health_penalty
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
        """Propagate shared health state to individual crew member records.

        Individual crew differentiation is not yet implemented — all crew
        members receive identical values from the shared habitat model.
        """
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
