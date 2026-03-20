"""
Policy engine — deterministic per-sol decision maker.

Evaluates engine state every sol and returns a list of action dicts.
No LLM calls — pure parameterized heuristics based on StrategyConfig.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from src.config import PlantingEntry, StrategyConfig

if TYPE_CHECKING:
    pass  # no simulation imports at module level -- all lazy via engine_bridge

# Zone areas (m2) — used for tracking available area
ZONE_AREAS: dict[str, float] = {"A": 12.0, "B": 18.0, "C": 20.0}


class PolicyEngine:
    """
    Stateful per-sol decision maker.

    Tracks planted area per zone to know when area is available for new crops.
    All decisions are based solely on engine state + StrategyConfig.
    """

    def __init__(self, config: StrategyConfig) -> None:
        self.config = config
        # Track planted area per zone (zone_id -> m2 currently occupied)
        self._planted_area: dict[str, float] = {"A": 0.0, "B": 0.0, "C": 0.0}
        # Track active crop_ids -> (zone_id, area_m2, crop_type)
        self._active_crops: dict[str, tuple[str, float, str]] = {}
        # Track environment setup
        self._env_set: bool = False
        # Track key decisions for RunResult
        self.key_decisions: list[dict[str, Any]] = []

    def decide(self, engine: Any, sol: int) -> list[dict[str, Any]]:
        """
        Main method called every sol. Returns list of {endpoint, body} action dicts.
        """
        actions: list[dict[str, Any]] = []

        # Sync internal crop tracking with engine state (handles deaths, manual changes)
        self._sync_crop_tracking(engine)

        # Environment setup (sol 0 or if reset)
        if not self._env_set:
            actions.extend(self._check_environment(engine, sol))
            self._env_set = True

        # Core decisions every sol
        actions.extend(self._check_energy(engine, sol))
        actions.extend(self._check_ice_mining(engine, sol))
        actions.extend(self._check_drill_maintenance(engine, sol))
        actions.extend(self._check_irrigation(engine, sol))
        actions.extend(self._check_filter_maintenance(engine, sol))
        actions.extend(self._check_nutrients(engine, sol))
        actions.extend(self._check_crop_removal(engine, sol))
        actions.extend(self._check_micronutrient_emergency(engine, sol))
        actions.extend(self._check_harvest(engine, sol))
        actions.extend(self._check_planting(engine, sol))
        actions.extend(self._check_crisis_response(engine, sol))
        actions.extend(self._check_food_emergency(engine, sol))

        return actions

    # ------------------------------------------------------------------
    # Internal tracking
    # ------------------------------------------------------------------

    def _sync_crop_tracking(self, engine: Any) -> None:
        """
        Sync internal planted area tracking against actual engine state.

        Handles crop deaths (removed from engine.crops.batches) or external changes.
        """
        dead_ids = [cid for cid in self._active_crops if cid not in engine.crops.batches]
        for cid in dead_ids:
            zone_id, area_m2, _ = self._active_crops.pop(cid)
            self._planted_area[zone_id] = max(0.0, self._planted_area[zone_id] - area_m2)

    def _register_crop(self, crop_id: str, zone_id: str, area_m2: float, crop_type: str) -> None:
        self._active_crops[crop_id] = (zone_id, area_m2, crop_type)
        self._planted_area[zone_id] = self._planted_area.get(zone_id, 0.0) + area_m2

    def _free_crop(self, crop_id: str) -> None:
        if crop_id in self._active_crops:
            zone_id, area_m2, _ = self._active_crops.pop(crop_id)
            self._planted_area[zone_id] = max(0.0, self._planted_area[zone_id] - area_m2)

    def _available_area(self, zone_id: str) -> float:
        """Available area in a zone (total - planted)."""
        return max(0.0, ZONE_AREAS.get(zone_id, 0.0) - self._planted_area.get(zone_id, 0.0))

    # ------------------------------------------------------------------
    # Decision methods
    # ------------------------------------------------------------------

    def _check_planting(self, engine: Any, sol: int) -> list[dict[str, Any]]:
        """Check planting schedule; plant if area and seeds are available."""
        actions: list[dict[str, Any]] = []

        # Get scheduled entries for this sol
        due: list[PlantingEntry] = [e for e in self.config.planting_schedule if e.sol == sol]

        for entry in due:
            crop_type = entry.crop_type
            zone_id = entry.zone_id
            area_m2 = entry.area_m2

            # Check seed availability
            seeds = getattr(engine.crops.seeds_remaining, "__getitem__", None)
            if seeds is not None:
                seeds_left = engine.crops.seeds_remaining.get(crop_type, 0)
            else:
                seeds_left = engine.crops.seeds_remaining.get(crop_type, 0)

            if seeds_left <= 0:
                self.key_decisions.append(
                    {
                        "sol": sol,
                        "action": f"skip_plant {crop_type} zone {zone_id}",
                        "reason": "seed_shortage",
                    }
                )
                continue

            # Check available area
            avail = self._available_area(zone_id)
            plant_area = min(area_m2, avail)
            if plant_area < 0.5:
                # Not enough room
                continue

            actions.append(
                {
                    "endpoint": "crops/plant",
                    "body": {
                        "type": crop_type,
                        "zone_id": zone_id,
                        "area_m2": plant_area,
                    },
                }
            )

        return actions

    def post_action_plant(self, crop_id: str, zone_id: str, area_m2: float, crop_type: str) -> None:
        """Called by runner after a successful plant action to track the crop."""
        self._register_crop(crop_id, zone_id, area_m2, crop_type)

    def _check_harvest(self, engine: Any, sol: int) -> list[dict[str, Any]]:
        """Check all active crops for harvest readiness."""
        actions: list[dict[str, Any]] = []
        hp = self.config.harvest_policy

        for crop_id, batch in list(engine.crops.batches.items()):
            # Get crop growth info
            growth_pct = _get_growth_pct(engine, batch)

            # Normal harvest: fully grown
            if growth_pct >= hp.min_growth_pct:
                actions.append(
                    {
                        "endpoint": "crops/harvest",
                        "body": {"crop_id": crop_id},
                    }
                )
                self._free_crop(crop_id)
                self.key_decisions.append(
                    {
                        "sol": sol,
                        "action": f"harvest {batch.crop_type} (growth {growth_pct:.0f}%)",
                        "reason": "mature",
                    }
                )
                continue

            # Salvage harvest: health dropping below threshold but partially grown
            if batch.health < hp.salvage_health_threshold and growth_pct >= hp.salvage_growth_pct:
                actions.append(
                    {
                        "endpoint": "crops/harvest",
                        "body": {"crop_id": crop_id},
                    }
                )
                self._free_crop(crop_id)
                self.key_decisions.append(
                    {
                        "sol": sol,
                        "action": (
                            f"salvage_harvest {batch.crop_type} "
                            f"(health {batch.health:.2f}, growth {growth_pct:.0f}%)"
                        ),
                        "reason": "salvage",
                    }
                )

        return actions

    def _check_energy(self, engine: Any, sol: int) -> list[dict[str, Any]]:
        """Set energy allocation based on battery level and active crises."""
        active_types = {c.type for c in engine.events.active_crises()}

        # Check for energy crisis
        is_energy_crisis = "energy_disruption" in [str(t) for t in active_types] or (
            engine.energy.battery_pct < 30.0
        )

        alloc_key = "crisis" if is_energy_crisis else "default"
        alloc = self.config.energy_allocation.get(
            alloc_key, self.config.energy_allocation.get("default", {})
        )

        if not alloc:
            return []

        return [
            {
                "endpoint": "energy/allocate",
                "body": {k: v for k, v in alloc.items()},
            }
        ]

    def _check_ice_mining(self, engine: Any, sol: int) -> list[dict[str, Any]]:
        """Mine ice when conditions allow: battery sufficient, reservoir not full, drill healthy."""
        if not self.config.ice_mining.enabled:
            return []
        if engine.energy.state.battery_level_wh < self.config.ice_mining.energy_reserve_wh:
            return []  # protect battery
        if engine.water.state.reservoir_liters >= self.config.ice_mining.water_ceiling_L:
            return []  # reservoir near full, save drill health
        if engine.water.state.drill_health_pct < 10.0:
            return []  # drill too damaged, needs maintenance first
        return [{"endpoint": "water/mine_ice", "body": {}}]

    def _check_irrigation(self, engine: Any, sol: int) -> list[dict[str, Any]]:
        """Set irrigation with crop-value-priority water allocation.

        Caloric crops (potato, beans) get priority irrigation. Other zones
        are cut first when water is scarce. Crew hydration is protected by
        stopping all irrigation when reservoir drops below 50L.
        """
        actions: list[dict[str, Any]] = []
        active_types = {str(c.type) for c in engine.events.active_crises()}
        reservoir_L = engine.water.state.reservoir_liters
        water_crisis = (
            "water_shortage" in active_types
            or "water_recycling_decline" in active_types
        )

        # Classify zones by crop value (kcal/L of water)
        # potato > beans > radish > lettuce > herbs
        high_value_zones: set[str] = set()
        for _cid, batch in engine.crops.batches.items():
            ct = str(batch.crop_type)
            if ct in ("potato", "beans"):
                high_value_zones.add(batch.zone_id)

        for zone_id, base_liters in self.config.irrigation.items():
            is_high_value = zone_id in high_value_zones

            # Priority irrigation: high-value zones get full water until 100L
            # Low-value zones are cut aggressively to preserve water for caloric crops
            if water_crisis or reservoir_L < 50.0:
                scale = 0.0  # emergency: save all water for crew
            elif is_high_value:
                # Protect caloric crops: full irrigation until 100L, then ramp down
                if reservoir_L < 100.0:
                    scale = reservoir_L / 100.0
                elif reservoir_L < 300.0:
                    scale = 0.8 + 0.2 * (reservoir_L - 100.0) / 200.0
                else:
                    scale = 1.0
            else:
                # Low-value zones: cut early to save water for caloric crops
                if reservoir_L < 200.0:
                    scale = 0.0
                elif reservoir_L < 400.0:
                    scale = (reservoir_L - 200.0) / 200.0
                else:
                    scale = 1.0

            liters = base_liters * scale
            actions.append(
                {
                    "endpoint": "water/set_irrigation",
                    "body": {
                        "zone_id": zone_id,
                        "irrigation_liters_per_sol": round(liters, 1),
                    },
                }
            )
        return actions

    def _check_environment(self, engine: Any, sol: int) -> list[dict[str, Any]]:
        """Set zone environment targets from config."""
        actions: list[dict[str, Any]] = []
        for zone_id, target in self.config.environment_targets.items():
            actions.append(
                {
                    "endpoint": "greenhouse/set_environment",
                    "body": {
                        "zone_id": zone_id,
                        "target_temp_c": target.temp_c,
                        "target_humidity_pct": target.humidity_pct,
                        "target_co2_ppm": target.co2_ppm,
                        "par_umol_m2s": target.par_umol_m2s,
                        "photoperiod_hours": target.photoperiod_hours,
                    },
                }
            )
        return actions

    def _check_drill_maintenance(self, engine: Any, sol: int) -> list[dict[str, Any]]:
        """Maintain drill on schedule and emergency if health drops too low."""
        if not self.config.ice_mining.enabled:
            return []
        # Emergency maintenance if drill health too low
        if engine.water.state.drill_health_pct < self.config.ice_mining.drill_health_maintenance_threshold_pct:
            return [{"endpoint": "water/maintenance", "body": {"action": "maintain_drill"}}]
        # Scheduled maintenance
        interval = self.config.ice_mining.drill_maintenance_interval_sols
        if interval > 0 and sol > 0 and sol % interval == 0:
            return [{"endpoint": "water/maintenance", "body": {"action": "maintain_drill"}}]
        return []

    def _check_filter_maintenance(self, engine: Any, sol: int) -> list[dict[str, Any]]:
        """Clean filters when health drops below threshold or on schedule."""
        health = engine.water.state.filter_health_pct
        interval = self.config.filter_maintenance_interval_sols
        threshold = self.config.filter_health_threshold_pct

        should_clean = health < threshold or (interval > 0 and sol > 0 and sol % interval == 0)

        if should_clean:
            return [
                {
                    "endpoint": "water/maintenance",
                    "body": {"action": "clean_filters"},
                }
            ]
        return []

    def _check_nutrients(self, engine: Any, sol: int) -> list[dict[str, Any]]:
        """Correct pH and boost nutrients when below thresholds."""
        actions: list[dict[str, Any]] = []
        nc = self.config.nutrient_correction
        active_types = {str(c.type) for c in engine.events.active_crises()}
        water_crisis = "water_shortage" in active_types or "water_recycling_decline" in active_types
        optimal_ph = 6.0

        for zone_id, zone_state in engine.nutrients.state.items():
            body: dict[str, Any] = {"zone_id": zone_id}

            # pH correction
            ph_drift = abs(zone_state.solution_ph - optimal_ph)
            if ph_drift > nc.ph_tolerance:
                body["target_ph"] = optimal_ph

            # Nitrogen boost
            if zone_state.nitrogen_ppm < nc.nitrogen_threshold_ppm:
                body["nitrogen_boost"] = True

            # Potassium boost
            if zone_state.potassium_ppm < nc.potassium_threshold_ppm:
                body["potassium_boost"] = True

            # Flush solution (suppress during water crisis)
            if zone_state.base_salt_ppm > 300.0 and not water_crisis:
                body["flush_solution"] = True

            # Only emit action if we have something to do
            if len(body) > 1:
                actions.append({"endpoint": "nutrients/adjust", "body": body})

        return actions

    def _check_crisis_response(self, engine: Any, sol: int) -> list[dict[str, Any]]:
        """Apply crisis-specific rule overrides from config."""
        # Crisis responses are handled inline in _check_energy, _check_irrigation, etc.
        # This method handles crisis-specific logging and environment changes.
        actions: list[dict[str, Any]] = []
        active_types = {str(c.type) for c in engine.events.active_crises()}

        # Temperature failure: boost heating
        if "temperature_failure" in active_types:
            response = self.config.crisis_response.get("temperature_failure", {})
            increase_heating = response.get("increase_heating_pct", 10.0)
            current_alloc = self.config.energy_allocation.get("default", {})
            if current_alloc:
                new_heating = min(80.0, current_alloc.get("heating_pct", 47.0) + increase_heating)
                actions.append(
                    {
                        "endpoint": "energy/allocate",
                        "body": {
                            "heating_pct": new_heating,
                        },
                    }
                )

        return actions

    def _check_crop_removal(self, engine: Any, sol: int) -> list[dict[str, Any]]:
        """Remove dead or dying crops (health < 0.1)."""
        actions: list[dict[str, Any]] = []
        DEATH_THRESHOLD = 0.1

        for crop_id, batch in list(engine.crops.batches.items()):
            if batch.health < DEATH_THRESHOLD:
                actions.append(
                    {
                        "endpoint": "crops/remove",
                        "body": {
                            "crop_id": crop_id,
                            "reason": f"health_critical_{batch.health:.2f}",
                        },
                    }
                )
                self._free_crop(crop_id)
                self.key_decisions.append(
                    {
                        "sol": sol,
                        "action": f"remove {batch.crop_type} (health {batch.health:.2f})",
                        "reason": "crop_death",
                    }
                )

        return actions

    def _check_micronutrient_emergency(self, engine: Any, sol: int) -> list[dict[str, Any]]:
        """
        Force-harvest lettuce early when crew micronutrient deficit is approaching danger.

        The provides_micronutrients flag is boolean — ANY lettuce harvest (even tiny)
        resets the deficit counter by 2 sols. We harvest the oldest lettuce batch
        when deficit_sols > 4 (before DEFICIENT threshold at 7).
        """
        deficit_sols = engine.crew.health.consecutive_micronutrient_deficit_sols
        if deficit_sols <= 4:
            return []

        # Find the oldest lettuce batch to emergency-harvest (prefer most mature)
        oldest_lettuce_id: str | None = None
        oldest_age = -1
        for crop_id, batch in engine.crops.batches.items():
            if str(batch.crop_type) == "lettuce" and batch.age_days > oldest_age:
                oldest_age = batch.age_days
                oldest_lettuce_id = crop_id

        # No minimum growth for emergency micronutrient harvest — the micronutrient
        # flag is boolean, so even a tiny harvest resets the deficit counter

        if oldest_lettuce_id is None:
            # No lettuce at all — plant emergency lettuce in any available zone
            for zone_id in ["A", "B", "C"]:
                avail = self._available_area(zone_id)
                seeds_left = engine.crops.seeds_remaining.get("lettuce", 0)
                if avail >= 2.0 and seeds_left > 0:
                    self.key_decisions.append({
                        "sol": sol,
                        "action": f"emergency_plant lettuce zone {zone_id}",
                        "reason": f"micronutrient_deficit_{deficit_sols}sols",
                    })
                    return [{
                        "endpoint": "crops/plant",
                        "body": {"type": "lettuce", "zone_id": zone_id, "area_m2": min(avail, 3.0)},
                    }]
            return []

        growth_pct = _get_growth_pct(engine, engine.crops.batches[oldest_lettuce_id])
        self._free_crop(oldest_lettuce_id)
        self.key_decisions.append({
            "sol": sol,
            "action": f"emergency_harvest lettuce (growth {growth_pct:.0f}%, age {oldest_age}d)",
            "reason": f"micronutrient_deficit_{deficit_sols}sols",
        })
        return [{
            "endpoint": "crops/harvest",
            "body": {"crop_id": oldest_lettuce_id},
        }]

    def _check_food_emergency(self, engine: Any, sol: int) -> list[dict[str, Any]]:
        """Plant emergency crops when food buffer is critically low."""
        if not self.config.food_shortage_response:
            return []

        fsr = self.config.food_shortage_response
        days_food = engine.crew.days_of_food

        if days_food > fsr.min_days_food:
            return []

        # Find a zone with available area
        emergency_crop = fsr.emergency_crop
        seeds_left = engine.crops.seeds_remaining.get(emergency_crop, 0)
        if seeds_left <= 0:
            return []

        for zone_id in ["A", "B", "C"]:
            avail = self._available_area(zone_id)
            if avail >= 2.0:
                self.key_decisions.append(
                    {
                        "sol": sol,
                        "action": f"emergency_plant {emergency_crop} zone {zone_id}",
                        "reason": f"food_low_{days_food:.1f}d",
                    }
                )
                return [
                    {
                        "endpoint": "crops/plant",
                        "body": {
                            "type": emergency_crop,
                            "zone_id": zone_id,
                            "area_m2": min(avail, 4.0),
                        },
                    }
                ]

        return []


# ------------------------------------------------------------------
# Helpers
# ------------------------------------------------------------------

# Growth days per crop type (mirrors src/catalog.py CROP_CATALOG)
_GROWTH_DAYS: dict[str, int] = {
    "lettuce": 35,
    "potato": 90,
    "radish": 25,
    "beans": 60,
    "herbs": 15,
}


def _get_growth_pct(engine: Any, batch: Any) -> float:
    """
    Compute growth percentage for a crop batch.

    growth_pct = (age_days / growth_days) * 100, capped at 100.
    """
    growth_days = _GROWTH_DAYS.get(str(batch.crop_type), 90)
    return min(100.0, (batch.age_days / growth_days) * 100.0)
