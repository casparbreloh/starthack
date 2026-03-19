"""7-sol energy budget projection for the Mars greenhouse agent.

Pure Python module — no LLM calls. Computes projected solar generation,
estimated consumption, and battery trajectory for the next 7 sols based on
LSTM weather forecast and current energy state.
"""

from __future__ import annotations

from .config import (
    EFFECTIVE_SOLAR_HOURS_PER_SOL,
    SOLAR_PANEL_AREA_M2,
    SOLAR_PANEL_EFFICIENCY,
)


def project_energy_budget(
    forecast_7sol: list[dict],
    current_energy: dict,
    current_weather: dict,
) -> list[dict]:
    """Project the energy budget for the next 7 sols.

    Uses current weather data for solar irradiance and dust opacity since
    the LSTM forecast does not predict these fields. Assumes constant solar
    conditions across the projection window (conservative estimate).

    Args:
        forecast_7sol: List of 7 forecast dicts from WeatherForecaster.get_7sol_forecast().
                       If empty (first ~30 sols before LSTM history accumulates),
                       returns empty list immediately.
        current_energy: Dict from SimClient.get_energy_status() — must have keys:
                        battery_level_wh, battery_capacity_wh, total_consumption_wh.
        current_weather: Dict from SimClient.get_weather_current() — must have keys:
                         solar_irradiance_wm2, dust_opacity.

    Returns:
        List of up to 7 projection dicts, each with:
        {sol, solar_generation_wh, estimated_consumption_wh, net_wh,
         projected_battery_wh, deficit (bool)}.
        Returns empty list if forecast_7sol is empty.
    """
    if not forecast_7sol:
        return []

    # Clamp dust opacity to prevent negative solar generation [R5-M1]
    dust_opacity = min(current_weather.get("dust_opacity", 0.0), 1.0)
    irradiance = current_weather.get("solar_irradiance_wm2", 400.0)

    # Solar generation (constant across projection — LSTM doesn't predict irradiance)
    solar_wh = (
        irradiance
        * SOLAR_PANEL_AREA_M2
        * SOLAR_PANEL_EFFICIENCY
        * EFFECTIVE_SOLAR_HOURS_PER_SOL
        * (1.0 - dust_opacity)
    )

    # Use current consumption as baseline for all projected sols
    consumption_wh = current_energy.get("total_consumption_wh", 0.0)

    battery_wh = current_energy.get("battery_level_wh", 0.0)
    battery_capacity = current_energy.get("battery_capacity_wh", 1.0)

    projection = []
    for entry in forecast_7sol:
        net_wh = solar_wh - consumption_wh

        # Update cumulative battery level clamped to [0, capacity]
        battery_wh = max(0.0, min(battery_capacity, battery_wh + net_wh))

        projection.append(
            {
                "sol": entry.get("sol", 0),
                "solar_generation_wh": round(solar_wh, 1),
                "estimated_consumption_wh": round(consumption_wh, 1),
                "net_wh": round(net_wh, 1),
                "projected_battery_wh": round(battery_wh, 1),
                "deficit": net_wh < 0,
            }
        )

    return projection


def summarize_energy_projection(projection: list[dict]) -> str:
    """Return a human-readable summary of the 7-sol energy projection.

    This string is injected into the orchestrator's per-sol prompt.

    Args:
        projection: Output from project_energy_budget(). May be empty list
                    for first ~30 sols before LSTM history accumulates.

    Returns:
        A concise summary string suitable for LLM context injection.
    """
    if not projection:
        return "Energy projection: unavailable (no forecast data)."

    deficit_sols = [p for p in projection if p["deficit"]]
    n_deficit = len(deficit_sols)

    min_battery = min(p["projected_battery_wh"] for p in projection)
    min_battery_sol = min(projection, key=lambda p: p["projected_battery_wh"])["sol"]

    action_needed = n_deficit > 0 or min_battery < 5000  # noqa: PLR2004 — threshold

    return (
        f"Energy projection ({len(projection)} sols): "
        f"{n_deficit} sols with deficit, "
        f"min battery at sol {min_battery_sol} ({min_battery:.0f} Wh). "
        f"Action needed: {'yes' if action_needed else 'no'}."
    )
