"""
Autonomous Event System — probabilistic events that fire during the mission.

Implements the 5 operational scenarios from:
  docs/mcp-data/06_GREENHOUSE_OPERATIONAL_SCENARIOS.MD

  6.3  Water Recycling Efficiency Decline
       biofouling, mechanical malfunction, sensor reporting error
  6.4  Energy Budget Reduction
       dust storm (solar reduction), unexpected consumption spike
  6.5  Crop Disease / Pathogen Risk
       fungal growth (humidity-triggered), bacterial contamination
  6.6  Temperature Control Failure
       HVAC partial failure, sensor error
  6.7  CO₂ Imbalance
       system leakage, consumption imbalance, sensor error

Each sol the engine calls .tick(sol, engine). The method may:
  - Fire new events (probabilistic, with guards against duplicates)
  - Apply ongoing per-sol effects of active events to engine state
  - Expire events when their duration ends and clean up any side-effects

Sensor noise is stored in the `sensor_noise` dict; engine.sensor_readings()
consults it to report realistic-but-wrong values to the agent.
"""

from __future__ import annotations

import random
from dataclasses import dataclass, field
from typing import Any


@dataclass
class ActiveEvent:
    """A currently active autonomous event with ongoing effects."""

    id: str
    event_type: str
    started_sol: int
    # -1 means permanent (effect stays until agent action resolves it)
    duration_sols: int
    description: str
    # "info" | "warning" | "critical"
    severity: str
    effects: dict[str, Any] = field(default_factory=dict)

    def is_permanent(self) -> bool:
        return self.duration_sols < 0

    def has_expired(self, current_sol: int) -> bool:
        return (
            not self.is_permanent()
            and current_sol >= self.started_sol + self.duration_sols
        )


class AutonomousEventSystem:
    """
    Manages probabilistic events that fire autonomously during the simulation.

    Design principles (matching doc 6.9):
      - Effects are proportional — not instantly catastrophic
      - Events are detectable via existing telemetry (signal-first)
      - Recovery is possible via agent actions
      - Each scenario type can only have ONE active instance at a time
    """

    def __init__(self, rng: random.Random) -> None:
        self.rng = rng
        self.active_events: list[ActiveEvent] = []
        self._counter = 0
        # Sensor noise: key → override value shown in sensor_readings()
        # Keys: "temp_{zone_id}", "co2_{zone_id}"
        self.sensor_noise: dict[str, float] = {}

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def tick(self, sol: int, engine: Any) -> list[dict[str, Any]]:
        """
        Run one sol. Returns list of log-entry dicts (type/category/message/severity).
        Call this AFTER all sub-model integrate() calls so effects apply this sol.
        """
        emitted: list[dict[str, Any]] = []

        # 1. Expire finished events
        expired = [e for e in self.active_events if e.has_expired(sol)]
        self.active_events = [e for e in self.active_events if not e.has_expired(sol)]
        for e in expired:
            self._on_expire(e, engine)
            emitted.append(
                _entry("info", "system", f"Event resolved: {e.description}", "info")
            )

        # 2. Apply ongoing per-sol effects
        for e in self.active_events:
            self._apply(e, engine)

        # 3. Roll for new events
        emitted.extend(self._check_new(sol, engine))

        return emitted

    def active_solar_factor(self, sol: int) -> float:
        """Combined solar reduction factor from all active energy_dust_storm events.

        Returns 1.0 when no storm is active.  Called by the engine BEFORE
        calc_rates so that the energy model sees correct solar generation
        and surplus_wh reflects reality.

        Events that have expired for ``sol`` are skipped even if they
        haven't been pruned from ``active_events`` yet (expiry happens
        later in ``tick()``).
        """
        factor = 1.0
        for e in self.active_events:
            if e.has_expired(sol):
                continue
            if e.event_type == "energy_dust_storm":
                factor *= e.effects.get("solar_factor", 1.0)
        return factor

    def reset(self, rng: random.Random) -> None:
        """Clear all state; called when engine resets."""
        self.rng = rng
        self.active_events.clear()
        self.sensor_noise.clear()
        self._counter = 0

    # ------------------------------------------------------------------
    # New event detection
    # ------------------------------------------------------------------

    def _check_new(self, sol: int, engine: Any) -> list[dict[str, Any]]:
        active_types = {e.event_type for e in self.active_events}
        emitted: list[dict[str, Any]] = []
        r = self.rng.random

        # ── 6.3  Water Recycling Efficiency Decline ──────────────────────────

        # Biofouling: sudden filter damage.  Permanent until agent cleans filters.
        # Probability: ~2 %/sol  → expected ~1 occurrence per 450-sol mission (permanent guard)
        if "water_biofouling" not in active_types and r() < 0.02:
            dmg = self.rng.uniform(12.0, 30.0)
            self._new(
                "water_biofouling",
                sol,
                duration=-1,
                desc="Biofouling in water recycling filters",
                severity="warning",
                effects={"filter_damage_pct": dmg},
            )
            engine.water.state.filter_health_pct = max(
                0.0, engine.water.state.filter_health_pct - dmg
            )
            # Immediately recompute recycling efficiency
            engine.water._update_recycling_efficiency()
            emitted.append(
                _entry(
                    "alert",
                    "water",
                    f"Water filter biofouling detected — filter health reduced by {dmg:.0f}% "
                    f"(now {engine.water.state.filter_health_pct:.0f}%). "
                    "Run filter maintenance to restore.",
                    "warning",
                )
            )

        # Mechanical malfunction: sudden efficiency drop, self-resolves over time
        # Probability: ~1.5 %/sol → expected ~1-2 occurrences per mission
        if "water_mechanical" not in active_types and r() < 0.015:
            drop = self.rng.uniform(10.0, 25.0)
            duration = self.rng.randint(8, 20)
            self._new(
                "water_mechanical",
                sol,
                duration=duration,
                desc="Water recycling mechanical malfunction",
                severity="critical",
                effects={"recycling_drop_pct": drop},
            )
            engine.water.state.recycling_efficiency_pct = max(
                30.0, engine.water.state.recycling_efficiency_pct - drop
            )
            emitted.append(
                _entry(
                    "crisis",
                    "water",
                    f"Water recycling mechanical malfunction — efficiency dropped by {drop:.0f}% "
                    f"(now {engine.water.state.recycling_efficiency_pct:.1f}%). "
                    f"Expected self-repair in ~{duration} sols.",
                    "critical",
                )
            )

        # Sensor error: water recycling sensor reports a fake low value for a few sols.
        # The actual state is unaffected; telemetry returns the noisy reading.
        # Probability: ~3 %/sol
        if "water_sensor_error" not in active_types and r() < 0.03:
            duration = self.rng.randint(3, 8)
            # Report a falsely low value so the agent has to reason about it
            fake_val = self.rng.uniform(50.0, 72.0)
            self._new(
                "water_sensor_error",
                sol,
                duration=duration,
                desc="Water recycling sensor reporting erroneous values",
                severity="info",
                effects={"sensor_fake_recycling_pct": fake_val},
            )
            self.sensor_noise["water_recycling_pct"] = fake_val
            emitted.append(
                _entry(
                    "alert",
                    "water",
                    "Water recycling efficiency sensor anomaly — displayed reading may be unreliable. "
                    "Cross-check reservoir trend before acting.",
                    "info",
                )
            )

        # ── 6.4  Energy Budget Reduction ─────────────────────────────────────

        # Dust storm: reduces solar generation for several sols.
        # The multiplier is applied post-integration by _apply().
        # Probability: ~2 %/sol → expected ~1-2 per mission
        if "energy_dust_storm" not in active_types and r() < 0.02:
            duration = self.rng.randint(6, 18)
            factor = self.rng.uniform(0.25, 0.60)
            self._new(
                "energy_dust_storm",
                sol,
                duration=duration,
                desc=f"Dust storm (solar reduced to {factor * 100:.0f}%)",
                severity="warning",
                effects={"solar_factor": factor},
            )
            emitted.append(
                _entry(
                    "alert",
                    "energy",
                    f"Dust storm detected — solar generation reduced to ~{factor * 100:.0f}% "
                    f"for approximately {duration} sols. "
                    "Reduce energy consumption or rely on battery reserves.",
                    "warning",
                )
            )

        # Unexpected consumption spike: e.g., malfunctioning pump or heater.
        # Probability: ~5 %/sol → expected ~3-5 per mission
        if "energy_consumption_spike" not in active_types and r() < 0.05:
            extra_wh = self.rng.uniform(800.0, 3000.0)
            duration = self.rng.randint(2, 6)
            self._new(
                "energy_consumption_spike",
                sol,
                duration=duration,
                desc="Unexpected energy consumption spike",
                severity="warning",
                effects={"extra_wh_per_sol": extra_wh},
            )
            emitted.append(
                _entry(
                    "alert",
                    "energy",
                    f"Unexpected energy demand: +{extra_wh:.0f} Wh/sol extra draw "
                    f"(subsystem malfunction) for {duration} sols.",
                    "warning",
                )
            )

        # ── 6.5  Crop Disease / Pathogen Risk ────────────────────────────────

        batches = list(engine.crops.batches.values())

        # Fungal growth: triggered by sustained high humidity (>72 %)
        # Probability: ~0.4 %/sol conditional on humidity
        avg_humidity = sum(z.humidity_pct for z in engine.climate.state.values()) / len(
            engine.climate.state
        )
        if (
            "crop_fungal" not in active_types
            and avg_humidity > 72.0
            and batches
            and r() < 0.04
        ):
            target = self.rng.choice(batches)
            duration = self.rng.randint(5, 14)
            penalty = self.rng.uniform(0.018, 0.055)
            self._new(
                "crop_fungal",
                sol,
                duration=duration,
                desc=f"Fungal infection in {target.crop_id}",
                severity="warning",
                effects={"crop_id": target.crop_id, "health_penalty_per_sol": penalty},
            )
            emitted.append(
                _entry(
                    "alert",
                    "crop",
                    f"Fungal growth detected in crop '{target.crop_id}' "
                    f"(zone {target.zone_id}) — likely caused by high humidity ({avg_humidity:.0f}%). "
                    "Reduce humidity or remove affected batch to prevent spread.",
                    "warning",
                )
            )

        # Bacterial contamination: random, zone-agnostic, harder to detect
        # Probability: ~2 %/sol → expected ~1-2 per mission (only when crops planted)
        if "crop_bacterial" not in active_types and batches and r() < 0.02:
            target = self.rng.choice(batches)
            duration = self.rng.randint(8, 20)
            penalty = self.rng.uniform(0.025, 0.07)
            self._new(
                "crop_bacterial",
                sol,
                duration=duration,
                desc=f"Bacterial contamination in {target.crop_id}",
                severity="critical",
                effects={"crop_id": target.crop_id, "health_penalty_per_sol": penalty},
            )
            emitted.append(
                _entry(
                    "crisis",
                    "crop",
                    f"Bacterial contamination detected in crop '{target.crop_id}' "
                    f"(zone {target.zone_id}). "
                    "Isolate affected zone, increase monitoring, consider removing batch.",
                    "critical",
                )
            )

        # ── 6.6  Temperature Control Failure ─────────────────────────────────

        zone_ids = list(engine.climate.state.keys())

        # HVAC partial failure: one zone's target drifts; reverts after duration.
        # Probability: ~2 %/sol → expected ~1-2 per mission
        if "temp_hvac_failure" not in active_types and r() < 0.02:
            zone_id = self.rng.choice(zone_ids)
            drift = self.rng.uniform(5.0, 14.0) * self.rng.choice([-1, 1])
            duration = self.rng.randint(4, 12)
            self._new(
                "temp_hvac_failure",
                sol,
                duration=duration,
                desc=f"HVAC partial failure zone {zone_id}",
                severity="warning",
                effects={"zone_id": zone_id, "temp_offset": drift},
            )
            # Shift target; climate model drifts toward the shifted target naturally
            engine.climate.state[zone_id].target_temp_c = round(
                engine.climate.state[zone_id].target_temp_c + drift, 1
            )
            direction = "heat" if drift > 0 else "cold"
            emitted.append(
                _entry(
                    "alert",
                    "temperature",
                    f"HVAC partial failure in zone {zone_id} — "
                    f"{direction} drift of {abs(drift):.1f}°C applied to setpoint "
                    f"(auto-restores in ~{duration} sols). "
                    "Adjust zone temperature setpoints to compensate.",
                    "warning",
                )
            )

        # Temperature sensor error: one zone reports wrong temperature.
        # Probability: ~3 %/sol → expected ~2-3 per mission
        if "temp_sensor_error" not in active_types and r() < 0.03:
            zone_id = self.rng.choice(zone_ids)
            actual = engine.climate.state[zone_id].temp_c
            fake_offset = self.rng.uniform(-9.0, 9.0)
            duration = self.rng.randint(2, 6)
            fake_val = round(actual + fake_offset, 1)
            self._new(
                "temp_sensor_error",
                sol,
                duration=duration,
                desc=f"Temperature sensor error zone {zone_id}",
                severity="info",
                effects={"zone_id": zone_id, "fake_offset": fake_offset},
            )
            self.sensor_noise[f"temp_{zone_id}"] = fake_val
            emitted.append(
                _entry(
                    "alert",
                    "temperature",
                    f"Temperature sensor anomaly in zone {zone_id} — "
                    f"displayed reading may be off by ≈{fake_offset:+.1f}°C. "
                    "Cross-check with adjacent zone sensors.",
                    "info",
                )
            )

        # ── 6.7  CO₂ Imbalance ───────────────────────────────────────────────

        # System leakage: CO₂ slowly escapes (per-sol drain applied in _apply)
        # Probability: ~1.5 %/sol → expected ~1-2 per mission
        if "co2_leakage" not in active_types and r() < 0.015:
            drain = self.rng.uniform(25.0, 80.0)
            duration = self.rng.randint(8, 22)
            self._new(
                "co2_leakage",
                sol,
                duration=duration,
                desc=f"CO₂ system leakage (~{drain:.0f} ppm/sol)",
                severity="warning",
                effects={"co2_drain_ppm_per_sol": drain},
            )
            emitted.append(
                _entry(
                    "alert",
                    "co2",
                    f"CO₂ system leakage detected — levels dropping ~{drain:.0f} ppm/sol "
                    f"for ~{duration} sols. "
                    "Increase CO₂ enrichment to compensate.",
                    "warning",
                )
            )

        # Consumption imbalance: CO₂ spikes or drops rapidly
        # Probability: ~2 %/sol → expected ~1-2 per mission
        if "co2_imbalance" not in active_types and r() < 0.02:
            direction = self.rng.choice(["high", "low"])
            magnitude = self.rng.uniform(150.0, 450.0)
            duration = self.rng.randint(3, 10)
            delta = magnitude if direction == "high" else -magnitude
            self._new(
                "co2_imbalance",
                sol,
                duration=duration,
                desc=f"CO₂ {'enrichment over-supply' if direction == 'high' else 'consumption imbalance'}",
                severity="warning",
                effects={"co2_delta_ppm_per_sol": delta},
            )
            if direction == "high":
                msg = (
                    f"CO₂ enrichment over-supply — levels rising ~{magnitude:.0f} ppm/sol "
                    f"for ~{duration} sols. Ventilate if above 5000 ppm."
                )
            else:
                msg = (
                    f"CO₂ consumption imbalance — levels falling ~{magnitude:.0f} ppm/sol "
                    f"for ~{duration} sols. Check crop density vs. enrichment rate."
                )
            emitted.append(_entry("alert", "co2", msg, "warning"))

        # CO₂ sensor error: one zone reports wrong CO₂
        # Probability: ~3 %/sol → expected ~2-3 per mission
        if "co2_sensor_error" not in active_types and r() < 0.03:
            zone_id = self.rng.choice(zone_ids)
            actual = engine.climate.state[zone_id].co2_ppm
            fake_offset = self.rng.uniform(-350.0, 600.0)
            duration = self.rng.randint(2, 5)
            fake_val = max(0.0, round(actual + fake_offset, 0))
            self._new(
                "co2_sensor_error",
                sol,
                duration=duration,
                desc=f"CO₂ sensor error zone {zone_id}",
                severity="info",
                effects={"zone_id": zone_id, "fake_offset": fake_offset},
            )
            self.sensor_noise[f"co2_{zone_id}"] = fake_val
            emitted.append(
                _entry(
                    "alert",
                    "co2",
                    f"CO₂ sensor anomaly in zone {zone_id} — "
                    f"readings may be off by ≈{fake_offset:+.0f} ppm. "
                    "Validate with cross-zone comparison.",
                    "info",
                )
            )

        return emitted

    # ------------------------------------------------------------------
    # Ongoing per-sol effect application
    # ------------------------------------------------------------------

    def _apply(self, event: ActiveEvent, engine: Any) -> None:
        eff = event.effects

        if event.event_type == "energy_dust_storm":
            # Solar reduction is now applied pre-calc_rates via
            # active_solar_factor(), so no post-hoc battery drain needed.
            pass

        elif event.event_type == "energy_consumption_spike":
            extra = eff.get("extra_wh_per_sol", 0.0)
            engine.energy.state.battery_level_wh = max(
                0.0, engine.energy.state.battery_level_wh - extra
            )
            engine.energy.state.total_consumption_wh = round(
                engine.energy.state.total_consumption_wh + extra, 1
            )

        elif event.event_type in ("crop_fungal", "crop_bacterial"):
            crop_id = eff.get("crop_id")
            penalty = eff.get("health_penalty_per_sol", 0.0)
            if crop_id and crop_id in engine.crops.batches:
                engine.crops.batches[crop_id].health = round(
                    max(0.0, engine.crops.batches[crop_id].health - penalty), 4
                )

        elif event.event_type == "co2_leakage":
            drain = eff.get("co2_drain_ppm_per_sol", 0.0)
            for zone in engine.climate.state.values():
                zone.co2_ppm = round(max(100.0, zone.co2_ppm - drain), 1)

        elif event.event_type == "co2_imbalance":
            delta = eff.get("co2_delta_ppm_per_sol", 0.0)
            for zone in engine.climate.state.values():
                zone.co2_ppm = round(max(100.0, min(15000.0, zone.co2_ppm + delta)), 1)

        # water_biofouling:   one-shot state mutation already applied at fire time
        # water_mechanical:   one-shot state mutation already applied at fire time
        # water_sensor_error: sensor_noise dict, no state change needed
        # temp_hvac_failure:  setpoint adjusted at fire time; climate model drifts naturally
        # temp_sensor_error:  sensor_noise dict, no state change needed
        # co2_sensor_error:   sensor_noise dict, no state change needed

    # ------------------------------------------------------------------
    # Event expiry cleanup
    # ------------------------------------------------------------------

    def _on_expire(self, event: ActiveEvent, engine: Any) -> None:
        eff = event.effects

        if event.event_type == "water_sensor_error":
            self.sensor_noise.pop("water_recycling_pct", None)

        elif event.event_type == "water_mechanical":
            # Self-healed mechanical issue — restore recycling efficiency from filter health
            engine.water._update_recycling_efficiency()

        elif event.event_type == "temp_hvac_failure":
            zone_id = eff.get("zone_id", "")
            drift = eff.get("temp_offset", 0.0)
            if zone_id in engine.climate.state:
                engine.climate.state[zone_id].target_temp_c = round(
                    engine.climate.state[zone_id].target_temp_c - drift, 1
                )

        elif event.event_type == "temp_sensor_error":
            zone_id = eff.get("zone_id", "")
            self.sensor_noise.pop(f"temp_{zone_id}", None)

        elif event.event_type == "co2_sensor_error":
            zone_id = eff.get("zone_id", "")
            self.sensor_noise.pop(f"co2_{zone_id}", None)

        # energy_dust_storm, energy_consumption_spike: no cleanup needed
        #   (battery drain already happened; solar_generation_wh recalculated each tick)
        # water_biofouling: permanent — only agent maintenance fixes it
        # crop_fungal, crop_bacterial: damage done; agent can remove/harvest crop

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _new(
        self,
        event_type: str,
        sol: int,
        *,
        duration: int,
        desc: str,
        severity: str,
        effects: dict[str, Any] | None = None,
    ) -> ActiveEvent:
        self._counter += 1
        ae = ActiveEvent(
            id=f"ae_{self._counter}",
            event_type=event_type,
            started_sol=sol,
            duration_sols=duration,
            description=desc,
            severity=severity,
            effects=effects or {},
        )
        self.active_events.append(ae)
        return ae


# ------------------------------------------------------------------
# Module-level helpers
# ------------------------------------------------------------------


def _entry(type_: str, category: str, message: str, severity: str) -> dict[str, Any]:
    return {
        "type": type_,
        "category": category,
        "message": message,
        "severity": severity,
    }
