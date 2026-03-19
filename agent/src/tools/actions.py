"""Action @tool functions for the Mars greenhouse agent.

Each function wraps a SimClient POST endpoint. These tools allow the LLM
to directly control the greenhouse simulation.

Note: advance_simulation is a plain function (NO @tool decorator). It is
called programmatically by run_sol only, NEVER given to specialist agents.
"""

from __future__ import annotations

import json

from strands import tool

from ..config import SIM_BASE_URL
from ..sim_client import SimClient

_client = SimClient(SIM_BASE_URL)


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
        JSON string with the new energy allocation confirmation.
    """
    result = _client.allocate_energy(
        heating_pct=heating_pct,
        lighting_pct=lighting_pct,
        water_recycling_pct=water_recycling_pct,
        nutrient_pumps_pct=nutrient_pumps_pct,
        reserve_pct=reserve_pct,
    )
    return json.dumps(result, indent=2)


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
        JSON string with the new environment setpoints confirmation.
    """
    result = _client.set_environment(
        zone_id=zone_id,
        target_temp_c=target_temp_c,
        target_humidity_pct=target_humidity_pct,
        target_co2_ppm=target_co2_ppm,
        par_umol_m2s=par_umol_m2s,
        photoperiod_hours=photoperiod_hours,
    )
    return json.dumps(result, indent=2)


@tool
def set_irrigation(zone_id: str, irrigation_liters_per_sol: float) -> str:
    """Set the daily irrigation rate for a greenhouse zone.

    The simulation also accepts an optional irrigation_frequency field
    (default: 'continuous'). The default is appropriate for all scenarios.

    Args:
        zone_id: Zone identifier ('A', 'B', or 'C')
        irrigation_liters_per_sol: Daily water allocation in liters per sol

    Returns:
        JSON string confirming the new irrigation setting.
    """
    result = _client.set_irrigation(
        zone_id=zone_id,
        irrigation_liters_per_sol=irrigation_liters_per_sol,
    )
    return json.dumps(result, indent=2)


@tool
def clean_water_filters() -> str:
    """Trigger a water filter cleaning cycle.

    Improves filter health and recycling efficiency. Clean when
    filter_health_pct < 70% or every 50 sols preventively.

    This call records a preventive action in the simulation scoring
    system automatically.

    Returns:
        JSON string confirming the maintenance action.
    """
    result = _client.water_maintenance(action="clean_filters")
    return json.dumps(result, indent=2)


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
        JSON string with the new crop record including crop_id.
    """
    result = _client.plant_crop(
        crop_type=crop_type,
        zone_id=zone_id,
        area_m2=area_m2,
        batch_name=batch_name,
    )
    return json.dumps(result, indent=2)


@tool
def harvest_crop(crop_id: str) -> str:
    """Harvest a ready crop to add its yield to the food supply.

    Harvest when is_ready == True or growth_pct >= 100. Consider salvage
    harvest if growth_pct >= 80 and health is dropping (health < 0.5).

    Args:
        crop_id: The unique identifier of the crop to harvest

    Returns:
        JSON string with harvest yield data (kg, kcal, protein_g).
    """
    result = _client.harvest_crop(crop_id=crop_id)
    return json.dumps(result, indent=2)


@tool
def remove_crop(crop_id: str, reason: str = "") -> str:
    """Remove a crop from the greenhouse (without harvesting).

    Use when: crop health < 20% (lost cause), pathogen containment required,
    water/nutrient conservation is critical and crop has low value.

    Args:
        crop_id: The unique identifier of the crop to remove
        reason: Human-readable reason for removal (for decision logging)

    Returns:
        JSON string confirming removal and freed area.
    """
    result = _client.remove_crop(crop_id=crop_id, reason=reason)
    return json.dumps(result, indent=2)


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
        JSON string with updated nutrient readings after adjustment.
    """
    result = _client.adjust_nutrients(
        zone_id=zone_id,
        target_ph=target_ph,
        target_ec_ms_cm=target_ec_ms_cm,
        nitrogen_boost=nitrogen_boost,
        potassium_boost=potassium_boost,
    )
    return json.dumps(result, indent=2)


def advance_simulation(sols: int = 1) -> dict:
    """Advance the simulation by N sols (plain function — NOT a @tool).

    This function is called programmatically by run_sol ONLY.
    It is NEVER given as a tool to any LLM agent (orchestrator or specialist).

    Args:
        sols: Number of sols to advance (default 1)

    Returns:
        The advance response dict containing new_sol, mission_phase, and events.
    """
    return _client.advance(sols=sols)
