"""Telemetry @tool functions for the Mars greenhouse agent.

Each function reads from the consultation snapshot dict instead of
making REST calls. The snapshot is updated each consultation.
"""

from __future__ import annotations

import json

from strands import tool


def create_telemetry_tools(snapshot: dict) -> dict:
    """Create telemetry tool functions that read from a snapshot dict.

    The snapshot is a mutable reference — the orchestrator updates it
    each consultation before creating tools.

    Returns a dict with keys matching the tool function names.
    """

    @tool
    def get_simulation_status() -> str:
        """Return the current simulation status including sol number and mission phase.

        Returns:
            JSON string with simulation status data including current_sol,
            mission_phase, and other sim state.
        """
        return json.dumps(snapshot.get("sim_status", {}), default=str)

    @tool
    def get_current_weather() -> str:
        """Return the current Mars weather readings for the greenhouse exterior.

        Returns:
            JSON string with weather data including temperature, pressure,
            dust_opacity, and solar_irradiance_wm2. Check dust_opacity > 1.0
            to detect potential dust storms.
        """
        return json.dumps(snapshot.get("weather_current", {}), default=str)

    @tool
    def get_weather_forecast(horizon: int = 7) -> str:
        """Return the simulation's weather forecast for the next N sols.

        Args:
            horizon: Number of sols to forecast ahead (default 7)

        Returns:
            JSON string with list of forecast weather dicts.
        """
        forecast = snapshot.get("weather_forecast", [])
        return json.dumps(forecast[:horizon], default=str)

    @tool
    def get_weather_history(last_n_sols: int = 30) -> str:
        """Return recent weather history from the simulation.

        Args:
            last_n_sols: Number of past sols of weather data to retrieve (default 30)

        Returns:
            JSON string with list of historical weather dicts ordered by sol.
        """
        history = snapshot.get("weather_history", [])
        return json.dumps(history[-last_n_sols:], default=str)

    @tool
    def get_energy_status() -> str:
        """Return the current energy system status including battery and allocations.

        Returns:
            JSON string with battery_level_wh, battery_capacity_wh, battery_pct,
            solar_generation_wh, total_consumption_wh, and current allocation
            percentages per subsystem.
        """
        return json.dumps(snapshot.get("energy_status", {}), default=str)

    @tool
    def get_greenhouse_environment() -> str:
        """Return the current greenhouse zone environment readings.

        Returns:
            JSON string with zones list (each zone has zone_id, temp_c, humidity_pct,
            co2_ppm, par_umol_m2s, photoperiod_hours), total_area_m2, and
            external_temp_c.
        """
        return json.dumps(snapshot.get("greenhouse_environment", {}), default=str)

    @tool
    def get_water_status() -> str:
        """Return the current water system status.

        Returns:
            JSON string with reservoir_liters, recycling_efficiency_pct,
            filter_health_pct, and daily water consumption/recycling stats.
        """
        return json.dumps(snapshot.get("water_status", {}), default=str)

    @tool
    def get_crops_status() -> str:
        """Return the status of all planted crops.

        Returns:
            JSON string with crops list where each crop has crop_id, type, zone_id,
            area_m2, growth_pct, health, is_ready, water_demand_l_per_sol, and stress
            indicators. Also includes total planted area and free area per zone.
        """
        return json.dumps(snapshot.get("crops_status", {}), default=str)

    @tool
    def get_nutrients_status() -> str:
        """Return the current nutrient levels in each greenhouse zone.

        Returns:
            JSON string with per-zone nutrient readings including nitrogen_ppm,
            potassium_ppm, ph, ec_ms_cm, and overall nutrient_stock_remaining_pct.
        """
        return json.dumps(snapshot.get("nutrients_status", {}), default=str)

    @tool
    def get_crew_nutrition() -> str:
        """Return the crew nutrition and food supply status.

        Returns:
            JSON string with days_of_food_remaining, daily_kcal_available,
            daily_protein_g_available, and the crew's nutritional needs vs supply.
        """
        return json.dumps(snapshot.get("crew_nutrition", {}), default=str)

    @tool
    def get_sensors_readings() -> str:
        """Return raw sensor readings from all greenhouse sensors.

        Returns:
            JSON string with per-zone sensor data and any flagged anomalies.
        """
        return json.dumps(snapshot.get("sensors_readings", {}), default=str)

    @tool
    def get_events_log(since_sol: int = 0) -> str:
        """Return the event log starting from the given sol number.

        Args:
            since_sol: Only return events from this sol onwards (default 0)

        Returns:
            JSON string with list of event dicts ordered by sol.
        """
        events = snapshot.get("events_log", [])
        if since_sol > 0 and isinstance(events, list):
            events = [
                e
                for e in events
                if isinstance(e, dict) and e.get("sol", 0) >= since_sol
            ]
        return json.dumps(events, default=str)

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
        return json.dumps(snapshot.get("active_crises", {}), default=str)

    @tool
    def get_current_score() -> str:
        """Return the current mission score breakdown.

        Returns:
            JSON string with scores dict containing overall_score and subscores
            for survival, nutrition, resource_efficiency, and crisis_management.
        """
        return json.dumps(snapshot.get("score_current", {}), default=str)

    @tool
    def read_all_telemetry() -> str:
        """Read all telemetry data from the current consultation snapshot.

        This is the primary telemetry tool for the orchestrator. Returns
        the full state snapshot provided by the simulation.

        Keys in returned dict:
            sim_status, weather_current, weather_history, weather_forecast,
            energy_status, greenhouse_environment, water_status, crops_status,
            nutrients_status, crew_nutrition, sensors_readings, events_log,
            active_crises, score_current, crop_catalog.

        Returns:
            JSON string with all telemetry data combined.
        """
        return json.dumps(snapshot, default=str)

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
        return json.dumps(snapshot.get("crop_catalog", {}), default=str)

    return {
        "get_simulation_status": get_simulation_status,
        "get_current_weather": get_current_weather,
        "get_weather_forecast": get_weather_forecast,
        "get_weather_history": get_weather_history,
        "get_energy_status": get_energy_status,
        "get_greenhouse_environment": get_greenhouse_environment,
        "get_water_status": get_water_status,
        "get_crops_status": get_crops_status,
        "get_nutrients_status": get_nutrients_status,
        "get_crew_nutrition": get_crew_nutrition,
        "get_sensors_readings": get_sensors_readings,
        "get_events_log": get_events_log,
        "get_active_crises": get_active_crises,
        "get_current_score": get_current_score,
        "read_all_telemetry": read_all_telemetry,
        "get_crop_catalog": get_crop_catalog,
    }
