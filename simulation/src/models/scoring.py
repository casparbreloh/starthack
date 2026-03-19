"""
Mission Scoring Sub-Model.

Four dimensions evaluated each sol:
  1. Survival      — crew alive, consecutive days without critical deficit
  2. Nutrition     — kcal / protein achievement vs targets
  3. Efficiency    — water, energy, crop waste
  4. Crisis mgmt   — crises encountered / resolved / prevented
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import TYPE_CHECKING

from src.constants import CREW_DAILY_KCAL, CREW_DAILY_PROTEIN_G

if TYPE_CHECKING:
    pass


@dataclass
class ScoreSnapshot:
    current_sol: int = 0
    survival: dict = field(
        default_factory=lambda: {
            "crew_alive": True,
            "days_without_critical_deficit": 0,
            "score": 100,
        }
    )
    nutrition: dict = field(
        default_factory=lambda: {
            "avg_daily_kcal": 0.0,
            "target_kcal": CREW_DAILY_KCAL,
            "kcal_achievement_pct": 100.0,
            "avg_daily_protein_g": 0.0,
            "protein_achievement_pct": 100.0,
            "micronutrient_diversity_score": 0.0,
            "score": 100,
        }
    )
    resource_efficiency: dict = field(
        default_factory=lambda: {
            "water_efficiency_pct": 100.0,
            "energy_efficiency_pct": 100.0,
            "crop_waste_pct": 0.0,
            "score": 100,
        }
    )
    crisis_management: dict = field(
        default_factory=lambda: {
            "crises_encountered": 0,
            "crises_resolved": 0,
            "avg_resolution_sols": 0.0,
            "preventive_actions_taken": 0,
            "score": 100,
        }
    )
    overall_score: int = 100


class ScoringModel:
    """
    Updated each sol by the engine. Read-only from routers.
    """

    def __init__(self) -> None:
        self.snapshot = ScoreSnapshot()
        self._consecutive_ok_sols: int = 0
        self._total_kcal_score: float = 0.0
        self._total_protein_score: float = 0.0
        self._water_waste_total_L: float = 0.0
        self._crises_encountered: list = []
        self._crises_resolved: list = []
        self._preventive_actions: int = 0
        self._crop_waste_kg: float = 0.0
        self._total_harvest_kg: float = 0.0

    def update(
        self,
        sol: int,
        crew_kcal: float,
        crew_protein_g: float,
        crew_alive: bool,
        micronutrients: bool,
        all_crises: list,
        active_crises: list,
        battery_pct: float,
        reservoir_L: float,
        reservoir_capacity_L: float,
    ) -> None:
        self.snapshot.current_sol = sol

        # Survival
        if not crew_alive or crew_kcal <= 0:
            self.snapshot.survival["crew_alive"] = False
            self._consecutive_ok_sols = 0
        else:
            self._consecutive_ok_sols += 1
        self.snapshot.survival["days_without_critical_deficit"] = (
            self._consecutive_ok_sols
        )
        self.snapshot.survival["score"] = 100 if crew_alive else 0

        # Nutrition
        kcal_ach = (
            min(100.0, crew_kcal / CREW_DAILY_KCAL * 100.0)
            if CREW_DAILY_KCAL > 0
            else 100.0
        )
        prot_ach = (
            min(100.0, crew_protein_g / CREW_DAILY_PROTEIN_G * 100.0)
            if CREW_DAILY_PROTEIN_G > 0
            else 100.0
        )
        self._total_kcal_score += kcal_ach
        self._total_protein_score += prot_ach
        avg_kcal_ach = self._total_kcal_score / sol if sol > 0 else 100.0
        avg_prot_ach = self._total_protein_score / sol if sol > 0 else 100.0
        micro_score = 1.0 if micronutrients else 0.5
        nutrition_score = int(
            avg_kcal_ach * 0.5 + avg_prot_ach * 0.4 + micro_score * 10.0
        )
        self.snapshot.nutrition.update(
            {
                "avg_daily_kcal": round(crew_kcal, 1),
                "kcal_achievement_pct": round(kcal_ach, 1),
                "avg_daily_protein_g": round(crew_protein_g, 1),
                "protein_achievement_pct": round(prot_ach, 1),
                "micronutrient_diversity_score": micro_score,
                "score": min(100, max(0, nutrition_score)),
            }
        )

        # Resource efficiency
        energy_eff = min(100.0, battery_pct * 2.0)  # 50% battery = 100% efficiency
        water_eff = min(100.0, reservoir_L / reservoir_capacity_L * 100.0 + 20.0)
        resource_score = int((energy_eff + water_eff) / 2.0)
        self.snapshot.resource_efficiency.update(
            {
                "water_efficiency_pct": round(water_eff, 1),
                "energy_efficiency_pct": round(energy_eff, 1),
                "score": min(100, max(0, resource_score)),
            }
        )

        # Crisis management
        n_crises = len(all_crises)
        n_resolved = sum(1 for c in all_crises if c.resolved)
        resolution_rate = n_resolved / n_crises if n_crises > 0 else 1.0
        crisis_score = int(100 * resolution_rate - len(active_crises) * 5)
        self.snapshot.crisis_management.update(
            {
                "crises_encountered": n_crises,
                "crises_resolved": n_resolved,
                "score": min(100, max(0, crisis_score)),
            }
        )

        # Overall
        overall = int(
            self.snapshot.survival["score"] * 0.35
            + self.snapshot.nutrition["score"] * 0.30
            + self.snapshot.resource_efficiency["score"] * 0.20
            + self.snapshot.crisis_management["score"] * 0.15
        )
        self.snapshot.overall_score = min(100, max(0, overall))

    def record_preventive_action(self) -> None:
        self._preventive_actions += 1
        self.snapshot.crisis_management["preventive_actions_taken"] = (
            self._preventive_actions
        )

    def record_crop_removed(self, waste_kg: float) -> None:
        self._crop_waste_kg += waste_kg

    def record_harvest(self, yield_kg: float) -> None:
        self._total_harvest_kg += yield_kg
        if self._total_harvest_kg > 0:
            self.snapshot.resource_efficiency["crop_waste_pct"] = round(
                self._crop_waste_kg
                / (self._total_harvest_kg + self._crop_waste_kg)
                * 100.0,
                1,
            )
