"""
Event log and crisis tracker.

Follows PCSE's dispatcher/signal pattern but simplified: instead of PyDispatcher
we use a plain list with automatic crisis detection each tick.
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass
from typing import TYPE_CHECKING

from src.enums import CrisisType, Severity

if TYPE_CHECKING:
    pass  # avoid circular; engine passes primitive snapshots


@dataclass
class Event:
    sol: int
    type: str  # "alert" | "harvest" | "crisis" | "action" | "info"
    category: str  # "temperature" | "water" | "energy" | "crop" | …
    message: str
    severity: Severity = Severity.INFO
    zone: str | None = None
    data: dict | None = None


@dataclass
class Crisis:
    id: str
    type: CrisisType
    started_sol: int
    severity: Severity
    message: str
    current_value: float
    threshold: float
    resolved: bool = False
    resolved_sol: int | None = None


class EventLog:
    MAX_EVENTS = 200

    def __init__(self) -> None:
        self._events: list[Event] = []
        self._crises: dict[str, Crisis] = {}  # id → Crisis

    # ------------------------------------------------------------------
    # Logging
    # ------------------------------------------------------------------

    def log(
        self,
        sol: int,
        type_: str,
        category: str,
        message: str,
        severity: Severity = Severity.INFO,
        zone: str | None = None,
        data: dict | None = None,
    ) -> Event:
        ev = Event(
            sol=sol,
            type=type_,
            category=category,
            message=message,
            severity=severity,
            zone=zone,
            data=data,
        )
        self._events.append(ev)
        if len(self._events) > self.MAX_EVENTS:
            self._events.pop(0)
        return ev

    # ------------------------------------------------------------------
    # Crisis management
    # ------------------------------------------------------------------

    def open_crisis(
        self,
        sol: int,
        crisis_type: CrisisType,
        severity: Severity,
        message: str,
        current_value: float,
        threshold: float,
    ) -> Crisis:
        # Avoid duplicate open crises of the same type
        for c in self._crises.values():
            if c.type == crisis_type and not c.resolved:
                c.current_value = current_value
                return c

        crisis = Crisis(
            id=f"crisis_{str(uuid.uuid4())[:8]}",
            type=crisis_type,
            started_sol=sol,
            severity=severity,
            message=message,
            current_value=current_value,
            threshold=threshold,
        )
        self._crises[crisis.id] = crisis
        self.log(
            sol,
            "crisis",
            crisis_type.value,
            message,
            severity,
            data={"crisis_id": crisis.id},
        )
        return crisis

    def resolve_crisis(self, crisis_type: CrisisType, sol: int) -> None:
        for c in self._crises.values():
            if c.type == crisis_type and not c.resolved:
                c.resolved = True
                c.resolved_sol = sol
                self.log(
                    sol,
                    "info",
                    crisis_type.value,
                    f"Crisis '{crisis_type.value}' resolved.",
                    Severity.INFO,
                )

    def resolve_by_id(self, crisis_id: str, sol: int) -> bool:
        if crisis_id in self._crises:
            c = self._crises[crisis_id]
            c.resolved = True
            c.resolved_sol = sol
            return True
        return False

    def active_crises(self) -> list[Crisis]:
        return [c for c in self._crises.values() if not c.resolved]

    # ------------------------------------------------------------------
    # Queries
    # ------------------------------------------------------------------

    def since(self, since_sol: int) -> list[Event]:
        return [e for e in self._events if e.sol >= since_sol]

    def recent(self, n: int = 20) -> list[Event]:
        return list(reversed(self._events[-n:]))

    def all_crises(self) -> list[Crisis]:
        return list(self._crises.values())

    # ------------------------------------------------------------------
    # Automatic crisis detection (called each tick by engine)
    # ------------------------------------------------------------------

    def detect_and_update(
        self,
        sol: int,
        water_reservoir_L: float,
        water_recycling_pct: float,
        battery_wh: float,
        battery_capacity_wh: float,
        avg_temp_c: float,
        co2_ppm: float,
        nutrient_stock_pct: float,
        crew_kcal: float,
        crew_daily_kcal: float,
    ) -> None:
        from src.constants import (
            CRISIS_WATER_RESERVOIR_L,
            WARNING_KCAL_DAYS,
        )

        # Water recycling decline
        if water_recycling_pct < 85.0:
            sev = Severity.CRITICAL if water_recycling_pct < 70.0 else Severity.WARNING
            self.open_crisis(
                sol,
                CrisisType.WATER_RECYCLING_DECLINE,
                sev,
                f"Recycling efficiency dropped to {water_recycling_pct:.1f}%",
                water_recycling_pct,
                85.0,
            )
        else:
            self.resolve_crisis(CrisisType.WATER_RECYCLING_DECLINE, sol)

        # Water shortage
        if water_reservoir_L < CRISIS_WATER_RESERVOIR_L:
            self.open_crisis(
                sol,
                CrisisType.WATER_SHORTAGE,
                Severity.CRITICAL,
                f"Water reservoir critically low: {water_reservoir_L:.0f}L",
                water_reservoir_L,
                CRISIS_WATER_RESERVOIR_L,
            )
        else:
            self.resolve_crisis(CrisisType.WATER_SHORTAGE, sol)

        # Energy disruption
        battery_pct = battery_wh / battery_capacity_wh * 100.0
        if battery_pct < 10.0:
            self.open_crisis(
                sol,
                CrisisType.ENERGY_DISRUPTION,
                Severity.CRITICAL,
                f"Battery critically low: {battery_pct:.1f}%",
                battery_pct,
                10.0,
            )
        elif battery_pct < 20.0:
            self.open_crisis(
                sol,
                CrisisType.ENERGY_DISRUPTION,
                Severity.WARNING,
                f"Battery low: {battery_pct:.1f}%",
                battery_pct,
                20.0,
            )
        else:
            self.resolve_crisis(CrisisType.ENERGY_DISRUPTION, sol)

        # Temperature failure
        if avg_temp_c < 15.0 or avg_temp_c > 28.0:
            sev = (
                Severity.CRITICAL
                if (avg_temp_c < 5.0 or avg_temp_c > 35.0)
                else Severity.WARNING
            )
            self.open_crisis(
                sol,
                CrisisType.TEMPERATURE_FAILURE,
                sev,
                f"Temperature out of safe range: {avg_temp_c:.1f}°C",
                avg_temp_c,
                15.0,
            )
        else:
            self.resolve_crisis(CrisisType.TEMPERATURE_FAILURE, sol)

        # CO2 imbalance
        if co2_ppm < 500.0 or co2_ppm > 2000.0:
            self.open_crisis(
                sol,
                CrisisType.CO2_IMBALANCE,
                Severity.WARNING,
                f"CO2 outside safe range: {co2_ppm:.0f} ppm",
                co2_ppm,
                800.0,
            )
        else:
            self.resolve_crisis(CrisisType.CO2_IMBALANCE, sol)

        # Nutrient depletion
        if nutrient_stock_pct < 15.0:
            sev = Severity.CRITICAL if nutrient_stock_pct < 5.0 else Severity.WARNING
            self.open_crisis(
                sol,
                CrisisType.NUTRIENT_DEPLETION,
                sev,
                f"Nutrient stock critically low: {nutrient_stock_pct:.1f}%",
                nutrient_stock_pct,
                15.0,
            )
        else:
            self.resolve_crisis(CrisisType.NUTRIENT_DEPLETION, sol)

        # Food shortage
        days_of_food = crew_kcal / crew_daily_kcal if crew_daily_kcal > 0 else 999
        if days_of_food < WARNING_KCAL_DAYS:
            sev = Severity.CRITICAL if days_of_food < 2.0 else Severity.WARNING
            self.open_crisis(
                sol,
                CrisisType.FOOD_SHORTAGE,
                sev,
                f"Food reserves low: {days_of_food:.1f} sols remaining",
                days_of_food,
                float(WARNING_KCAL_DAYS),
            )
        else:
            self.resolve_crisis(CrisisType.FOOD_SHORTAGE, sol)
