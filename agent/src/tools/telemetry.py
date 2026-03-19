"""Telemetry @tool functions for the Mars greenhouse agent.

Each function wraps a SimClient GET endpoint and returns JSON string
so the LLM can read the data directly.
"""

from __future__ import annotations

import json

from strands import tool

from ..config import SIM_BASE_URL
from ..sim_client import SimClient

_client = SimClient(SIM_BASE_URL)


@tool
def get_simulation_status() -> str:
    """Return the current simulation status including sol number and mission phase.

    Returns:
        JSON string with simulation status data including current_sol,
        mission_phase, and other sim state.
    """
    return json.dumps(_client.get_sim_status(), indent=2)


@tool
def get_current_weather() -> str:
    """Return the current Mars weather readings for the greenhouse exterior.

    Returns:
        JSON string with weather data including temperature, pressure,
        dust_opacity, and solar_irradiance_wm2. Check dust_opacity > 1.0
        to detect potential dust storms.
    """
    return json.dumps(_client.get_weather_current(), indent=2)


@tool
def get_weather_forecast(horizon: int = 7) -> str:
    """Return the simulation's weather forecast for the next N sols.

    Note: The LSTM-based forecast is provided separately in your telemetry
    context each sol. This endpoint provides the simulation's own deterministic
    forecast as a backup/comparison.

    Args:
        horizon: Number of sols to forecast ahead (default 7)

    Returns:
        JSON string with list of forecast weather dicts.
    """
    return json.dumps(_client.get_weather_forecast(horizon=horizon), indent=2)


@tool
def get_weather_history(last_n_sols: int = 30) -> str:
    """Return recent weather history from the simulation.

    Args:
        last_n_sols: Number of past sols of weather data to retrieve (default 30)

    Returns:
        JSON string with list of historical weather dicts ordered by sol.
    """
    return json.dumps(_client.get_weather_history(last_n_sols=last_n_sols), indent=2)


@tool
def get_energy_status() -> str:
    """Return the current energy system status including battery and allocations.

    Returns:
        JSON string with battery_level_wh, battery_capacity_wh, battery_pct,
        solar_generation_wh, total_consumption_wh, and current allocation
        percentages per subsystem.
    """
    return json.dumps(_client.get_energy_status(), indent=2)


@tool
def get_greenhouse_environment() -> str:
    """Return the current greenhouse zone environment readings.

    Returns:
        JSON string with zones list (each zone has zone_id, temp_c, humidity_pct,
        co2_ppm, par_umol_m2s, photoperiod_hours), total_area_m2, and
        external_temp_c.
    """
    return json.dumps(_client.get_greenhouse_environment(), indent=2)


@tool
def get_water_status() -> str:
    """Return the current water system status.

    Returns:
        JSON string with reservoir_liters, recycling_efficiency_pct,
        filter_health_pct, and daily water consumption/recycling stats.
    """
    return json.dumps(_client.get_water_status(), indent=2)


@tool
def get_crops_status() -> str:
    """Return the status of all planted crops.

    Returns:
        JSON string with crops list where each crop has crop_id, type, zone_id,
        area_m2, growth_pct, health, is_ready, water_demand_l_per_sol, and stress
        indicators. Also includes total planted area and free area per zone.
    """
    return json.dumps(_client.get_crops_status(), indent=2)


@tool
def get_nutrients_status() -> str:
    """Return the current nutrient levels in each greenhouse zone.

    Returns:
        JSON string with per-zone nutrient readings including nitrogen_ppm,
        potassium_ppm, ph, ec_ms_cm, and overall nutrient_stock_remaining_pct.
    """
    return json.dumps(_client.get_nutrients_status(), indent=2)


@tool
def get_crew_nutrition() -> str:
    """Return the crew nutrition and food supply status.

    Returns:
        JSON string with days_of_food_remaining, daily_kcal_available,
        daily_protein_g_available, and the crew's nutritional needs vs supply.
    """
    return json.dumps(_client.get_crew_nutrition(), indent=2)


@tool
def get_sensors_readings() -> str:
    """Return raw sensor readings from all greenhouse sensors.

    Useful for detecting sensor anomalies or cross-checking environment
    readings against the LSTM weather sanity check output.

    Returns:
        JSON string with per-zone sensor data and any flagged anomalies.
    """
    return json.dumps(_client.get_sensors_readings(), indent=2)


@tool
def get_events_log(since_sol: int = 0) -> str:
    """Return the event log starting from the given sol number.

    Note: The event log is limited to the most recent 200 events in the
    simulation. Track your own maintenance schedules rather than relying
    on this log for historical records older than ~50 sols.

    Args:
        since_sol: Only return events from this sol onwards (default 0)

    Returns:
        JSON string with list of event dicts ordered by sol.
    """
    return json.dumps(_client.get_events_log(since_sol=since_sol), indent=2)


@tool
def get_active_crises() -> str:
    """Return all currently active crises in the greenhouse system.

    Crisis types: water_recycling_decline, water_shortage, energy_disruption,
    pathogen_outbreak, temperature_failure, co2_imbalance, nutrient_depletion,
    food_shortage.

    Note: dust_storm is NOT a crisis type. Detect dust storms via weather
    telemetry (dust_opacity > 1.0).

    Returns:
        JSON string with crises list where each crisis has id, type, severity,
        start_sol, and description.
    """
    return json.dumps(_client.get_active_crises(), indent=2)


@tool
def get_current_score() -> str:
    """Return the current mission score breakdown.

    Returns:
        JSON string with scores dict containing overall_score and subscores
        for survival, nutrition, resource_efficiency, and crisis_management.
    """
    return json.dumps(_client.get_score_current(), indent=2)


@tool
def read_all_telemetry() -> str:
    """Read all 14 telemetry endpoints and return a combined JSON object.

    This is the primary telemetry tool for the orchestrator. It fetches
    all monitoring data in a single call to minimize tool call overhead.

    Keys in returned dict:
        sim_status, weather_current, weather_history, weather_forecast,
        energy_status, greenhouse_environment, water_status, crops_status,
        nutrients_status, crew_nutrition, sensors_readings, events_log,
        active_crises, score_current.

    NOT included:
        - score_final (throws HTTP 400 unless mission is complete)
        - crop_catalog (static data — call get_crop_catalog() on sol 0 instead)

    Size bounding:
        - events_log: only last 50 sols of events
        - weather_history: only last 30 sols

    Returns:
        JSON string with all 14 telemetry data dicts combined.
    """
    return json.dumps(_client.read_all_telemetry(), indent=2)


@tool
def get_crop_catalog() -> str:
    """Return the static crop catalog with growth parameters.

    Call this on sol 0 to retrieve exact crop parameters from the simulation:
    growth days, yields (kg/m2), kcal/kg, protein/kg, and water demand.
    Memorize these values — do NOT call every sol (static data).

    Returns:
        JSON string with crop catalog listing all available crop types and
        their exact simulation parameters.
    """
    return json.dumps(_client.get_crop_catalog(), indent=2)
