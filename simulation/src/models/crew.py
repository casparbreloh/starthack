"""
Crew Nutrition Sub-Model.

Tracks what the 4-astronaut crew eats each sol, the balance between stored
food (pre-mission supplies) and fresh greenhouse harvests, and cumulative
nutrition performance.
"""

from __future__ import annotations

from dataclasses import dataclass

from src.constants import (
    CREW_DAILY_KCAL,
    CREW_DAILY_PROTEIN_G,
    INITIAL_STORED_KCAL,
    INITIAL_STORED_PROTEIN_G,
)
from src.enums import CrewStatus


@dataclass
class CrewState:
    # Stored food (pre-mission supplies, finite)
    stored_kcal: float = INITIAL_STORED_KCAL
    stored_protein_g: float = INITIAL_STORED_PROTEIN_G
    # Fresh harvest buffer (added at each harvest)
    fresh_buffer_kcal: float = 0.0
    fresh_buffer_protein_g: float = 0.0
    # Today's intake (reset each sol)
    today_kcal_consumed: float = 0.0
    today_kcal_target: float = float(CREW_DAILY_KCAL)
    today_protein_consumed_g: float = 0.0
    today_protein_target_g: float = float(CREW_DAILY_PROTEIN_G)
    from_greenhouse_pct: float = 0.0
    from_stored_pct: float = 100.0
    # Cumulative metrics
    cumulative_avg_kcal: float = float(CREW_DAILY_KCAL)
    cumulative_avg_protein_g: float = float(CREW_DAILY_PROTEIN_G)
    deficit_sols: int = 0
    surplus_sols: int = 0
    total_sols_tracked: int = 0
    crew_status: CrewStatus = CrewStatus.NOMINAL
    micronutrients_sufficient: bool = False


@dataclass
class CrewRates:
    d_stored_kcal: float = 0.0
    d_stored_protein_g: float = 0.0


class CrewModel:
    """
    State variables  : stored food, fresh buffer, daily intake, cumulative metrics
    Rate variables   : daily draw on stored food
    """

    def __init__(self) -> None:
        self.state = CrewState()
        self.rates = CrewRates()
        self._total_kcal_consumed: float = 0.0
        self._total_protein_consumed: float = 0.0

    # ------------------------------------------------------------------
    # PCSE lifecycle
    # ------------------------------------------------------------------

    def calc_rates(self) -> None:
        """Determine how much stored food must cover daily need."""
        # Fresh buffer covers as much as possible first
        fresh_kcal = min(self.state.fresh_buffer_kcal, CREW_DAILY_KCAL)
        fresh_protein = min(self.state.fresh_buffer_protein_g, CREW_DAILY_PROTEIN_G)

        stored_kcal_needed = max(0.0, CREW_DAILY_KCAL - fresh_kcal)
        stored_protein_needed = max(0.0, CREW_DAILY_PROTEIN_G - fresh_protein)

        self.rates.d_stored_kcal = -stored_kcal_needed
        self.rates.d_stored_protein_g = -stored_protein_needed

    def integrate(self) -> None:
        """Apply consumption, update cumulative metrics."""
        # Consume from fresh buffer
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

        # Draw remainder from stored supplies
        self.state.stored_kcal = max(
            0.0, self.state.stored_kcal + self.rates.d_stored_kcal
        )
        self.state.stored_protein_g = max(
            0.0, self.state.stored_protein_g + self.rates.d_stored_protein_g
        )

        # Today's intake
        actual_kcal = fresh_kcal_used + min(
            self.state.stored_kcal, -self.rates.d_stored_kcal
        )
        actual_protein = fresh_protein_used + min(
            self.state.stored_protein_g, -self.rates.d_stored_protein_g
        )
        self.state.today_kcal_consumed = round(actual_kcal, 1)
        self.state.today_protein_consumed_g = round(actual_protein, 1)

        total_food = fresh_kcal_used + (-self.rates.d_stored_kcal)
        self.state.from_greenhouse_pct = round(
            fresh_kcal_used / total_food * 100.0 if total_food > 0 else 0.0, 1
        )
        self.state.from_stored_pct = round(100.0 - self.state.from_greenhouse_pct, 1)

        # Cumulative metrics
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

        self._update_status()

    # ------------------------------------------------------------------
    # Harvest callback
    # ------------------------------------------------------------------

    def add_harvest(
        self, kcal: float, protein_g: float, has_micronutrients: bool
    ) -> None:
        """Called by engine after a successful harvest."""
        self.state.fresh_buffer_kcal += kcal
        self.state.fresh_buffer_protein_g += protein_g
        if has_micronutrients:
            self.state.micronutrients_sufficient = True

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    def _update_status(self) -> None:
        total = self.state.stored_kcal + self.state.fresh_buffer_kcal
        days_food = total / CREW_DAILY_KCAL if CREW_DAILY_KCAL > 0 else 999
        if days_food < 2:
            self.state.crew_status = CrewStatus.CRITICAL
        elif days_food < 10:
            self.state.crew_status = CrewStatus.WARNING
        else:
            self.state.crew_status = CrewStatus.NOMINAL

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
