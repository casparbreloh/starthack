"""Action @tool functions for the Mars greenhouse agent.

Each function returns a queued confirmation dict. The actual execution
happens server-side when the simulation receives the agent_actions
WebSocket message and calls _dispatch_action() in tick_loop.py.
"""

from __future__ import annotations

import json
from contextlib import contextmanager
from contextvars import ContextVar

from strands import tool

_ACTION_ACCUMULATOR: ContextVar[list[dict] | None] = ContextVar(
    "action_accumulator",
    default=None,
)


@contextmanager
def bind_action_accumulator(action_accumulator: list[dict]):
    """Temporarily bind an action accumulator for nested specialist tool calls."""
    token = _ACTION_ACCUMULATOR.set(action_accumulator)
    try:
        yield
    finally:
        _ACTION_ACCUMULATOR.reset(token)


def create_action_tools(
    action_accumulator: list[dict] | None = None,
) -> dict:
    """Create action tool functions that return intent dicts.

    If action_accumulator is provided, each tool call also appends its
    action dict (endpoint + body) to the list. This allows the caller
    to collect all actions after the agent finishes.

    Returns a dict with keys matching the tool function names.
    """
    inherited_acc = _ACTION_ACCUMULATOR.get()
    _acc = (
        action_accumulator
        if action_accumulator is not None
        else inherited_acc
        if inherited_acc is not None
        else []
    )

    def _queue(endpoint: str, body: dict) -> str:
        """Append to accumulator and return JSON confirmation."""
        _acc.append({"endpoint": endpoint, "body": body})
        return json.dumps({"status": "queued", "endpoint": endpoint, "body": body})

    @tool
    def allocate_energy(
        heating_pct: float,
        lighting_pct: float,
        water_recycling_pct: float,
        nutrient_pumps_pct: float,
        reserve_pct: float,
    ) -> str:
        """Allocate power across greenhouse subsystems.

        The percentages should sum to approximately 100. Recommended defaults:
        heating=47, lighting=30, water_recycling=12, nutrient_pumps=5, reserve=6.

        Priority order: Safety (heating) > Stability (water/nutrients) > Crops
        (lighting) > Reserve.

        This call also records a preventive action in the simulation scoring
        system automatically. Do NOT try to call a separate preventive scoring
        function -- it does not exist.

        Args:
            heating_pct: Percentage of power for zone heating (0-100)
            lighting_pct: Percentage of power for grow lights (0-100)
            water_recycling_pct: Percentage for water recycling system (0-100)
            nutrient_pumps_pct: Percentage for nutrient delivery pumps (0-100)
            reserve_pct: Percentage held in reserve for safety buffer (0-100)

        Returns:
            JSON string confirming the action was queued.
        """
        return _queue(
            "energy/allocate",
            {
                "heating_pct": heating_pct,
                "lighting_pct": lighting_pct,
                "water_recycling_pct": water_recycling_pct,
                "nutrient_pumps_pct": nutrient_pumps_pct,
                "reserve_pct": reserve_pct,
            },
        )

    @tool
    def set_zone_environment(
        zone_id: str,
        target_temp_c: float | None = None,
        target_humidity_pct: float | None = None,
        target_co2_ppm: float | None = None,
        par_umol_m2s: float | None = None,
        photoperiod_hours: float | None = None,
    ) -> str:
        """Set environment targets for a greenhouse zone.

        Target values: temperature=21C, humidity=60%, CO2=1000ppm,
        PAR=220 umol/m2/s, photoperiod=16h.

        Args:
            zone_id: Zone identifier ('A', 'B', or 'C')
            target_temp_c: Target temperature in Celsius (optional)
            target_humidity_pct: Target relative humidity percent (optional)
            target_co2_ppm: Target CO2 concentration in ppm (optional)
            par_umol_m2s: Target photosynthetically active radiation (optional)
            photoperiod_hours: Hours of lighting per sol (optional)

        Returns:
            JSON string confirming the action was queued.
        """
        params: dict = {"zone_id": zone_id}
        if target_temp_c is not None:
            params["target_temp_c"] = target_temp_c
        if target_humidity_pct is not None:
            params["target_humidity_pct"] = target_humidity_pct
        if target_co2_ppm is not None:
            params["target_co2_ppm"] = target_co2_ppm
        if par_umol_m2s is not None:
            params["par_umol_m2s"] = par_umol_m2s
        if photoperiod_hours is not None:
            params["photoperiod_hours"] = photoperiod_hours
        return _queue("greenhouse/set_environment", params)

    @tool
    def set_irrigation(zone_id: str, irrigation_liters_per_sol: float) -> str:
        """Set the daily irrigation rate for a greenhouse zone.

        Args:
            zone_id: Zone identifier ('A', 'B', or 'C')
            irrigation_liters_per_sol: Daily water allocation in liters per sol

        Returns:
            JSON string confirming the action was queued.
        """
        return _queue(
            "water/set_irrigation",
            {
                "zone_id": zone_id,
                "irrigation_liters_per_sol": irrigation_liters_per_sol,
            },
        )

    @tool
    def clean_water_filters() -> str:
        """Trigger a water filter cleaning cycle.

        Improves filter health and recycling efficiency. Clean when
        filter_health_pct < 70% or every 50 sols preventively.

        This call records a preventive action in the simulation scoring
        system automatically.

        Returns:
            JSON string confirming the action was queued.
        """
        return _queue("water/maintenance", {"action": "clean_filters"})

    @tool
    def plant_crop(
        crop_type: str,
        zone_id: str,
        area_m2: float,
        batch_name: str | None = None,
    ) -> str:
        """Plant a crop in the specified greenhouse zone.

        Available crop types: potato, soybean, lettuce, radish, herbs.
        Check seeds_remaining before planting. Zone areas: A=12m2, B=18m2, C=20m2.

        Args:
            crop_type: Type of crop to plant (e.g., 'potato', 'lettuce', 'radish')
            zone_id: Zone where to plant ('A', 'B', or 'C')
            area_m2: Area in square meters to allocate for this crop
            batch_name: Optional name for tracking this planting batch

        Returns:
            JSON string confirming the action was queued.
        """
        params: dict = {"type": crop_type, "zone_id": zone_id, "area_m2": area_m2}
        if batch_name is not None:
            params["batch_name"] = batch_name
        return _queue("crops/plant", params)

    @tool
    def harvest_crop(crop_id: str) -> str:
        """Harvest a ready crop to add its yield to the food supply.

        Harvest when is_ready == True or growth_pct >= 100. Consider salvage
        harvest if growth_pct >= 80 and health is dropping (health < 0.5).

        Args:
            crop_id: The unique identifier of the crop to harvest

        Returns:
            JSON string confirming the action was queued.
        """
        return _queue("crops/harvest", {"crop_id": crop_id})

    @tool
    def remove_crop(crop_id: str, reason: str = "") -> str:
        """Remove a crop from the greenhouse (without harvesting).

        Use when: crop health < 20% (lost cause), pathogen containment required,
        water/nutrient conservation is critical and crop has low value.

        Args:
            crop_id: The unique identifier of the crop to remove
            reason: Human-readable reason for removal (for decision logging)

        Returns:
            JSON string confirming the action was queued.
        """
        return _queue("crops/remove", {"crop_id": crop_id, "reason": reason})

    @tool
    def adjust_nutrients(
        zone_id: str,
        target_ph: float | None = None,
        target_ec_ms_cm: float | None = None,
        nitrogen_boost: bool = False,
        potassium_boost: bool = False,
    ) -> str:
        """Adjust nutrient levels in a greenhouse zone.

        Guidelines:
        - Apply nitrogen boost when nitrogen_ppm < 120 (80% of 150ppm target)
        - Apply potassium boost when potassium_ppm < 180 (TARGET_K_PPM)
        - Adjust pH if it drifts from 5.8 by more than 0.5
        - Conserve nutrients if nutrient_stock_remaining_pct < 20%

        Args:
            zone_id: Zone to adjust ('A', 'B', or 'C')
            target_ph: Target pH level (optimal range 5.5-6.5, ideal 5.8)
            target_ec_ms_cm: Target electrical conductivity in mS/cm
            nitrogen_boost: Apply nitrogen supplementation if True
            potassium_boost: Apply potassium supplementation if True

        Returns:
            JSON string confirming the action was queued.
        """
        params: dict = {
            "zone_id": zone_id,
            "nitrogen_boost": nitrogen_boost,
            "potassium_boost": potassium_boost,
        }
        if target_ph is not None:
            params["target_ph"] = target_ph
        if target_ec_ms_cm is not None:
            params["target_ec_ms_cm"] = target_ec_ms_cm
        return _queue("nutrients/adjust", params)

    return {
        "allocate_energy": allocate_energy,
        "set_zone_environment": set_zone_environment,
        "set_irrigation": set_irrigation,
        "clean_water_filters": clean_water_filters,
        "plant_crop": plant_crop,
        "harvest_crop": harvest_crop,
        "remove_crop": remove_crop,
        "adjust_nutrients": adjust_nutrients,
    }
