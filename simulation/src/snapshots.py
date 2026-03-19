"""
State snapshot builder.

Assembles a full telemetry snapshot from all engine sub-models, producing
a dict whose keys match the telemetry router endpoints. This is the payload
broadcast to WebSocket clients on each tick.
"""

from __future__ import annotations

from typing import Any

from src.catalog import CROP_CATALOG
from src.constants import (
    CREW_DAILY_KCAL,
    FOOD_KCAL_PER_KG,
    FOOD_PROTEIN_G_PER_KG,
    INITIAL_FOOD_KG,
    ZONE_AREAS_M2,
)
from src.engine import SimulationEngine


def build_state_snapshot(engine: SimulationEngine) -> dict[str, Any]:
    """Build a complete state snapshot matching the telemetry router shapes."""
    return {
        "sim_status": _sim_status(engine),
        "weather_current": _weather_current(engine),
        "energy_status": _energy_status(engine),
        "greenhouse_environment": _greenhouse_environment(engine),
        "water_status": _water_status(engine),
        "crops_status": _crops_status(engine),
        "nutrients_status": _nutrients_status(engine),
        "crew_nutrition": _crew_nutrition(engine),
        "active_crises": _active_crises(engine),
        "score_current": _score_current(engine),
        "crew_members": _crew_members(engine),
        "crew_health": _crew_health(engine),
    }


def build_consultation_snapshot(engine: SimulationEngine) -> dict[str, Any]:
    """Build an enriched snapshot for agent consultations.

    Extends build_state_snapshot() with data the agent needs that isn't
    in the tick broadcast: weather history, forecast, crop catalog,
    events log, and sensor readings.
    """
    snapshot = build_state_snapshot(engine)

    # Weather history (last 30 sols)
    weather_to_dict = _weather_to_dict
    snapshot["weather_history"] = [
        weather_to_dict(w) for w in engine.weather.history(30)
    ]

    # Weather forecast (7 sols)
    snapshot["weather_forecast"] = [
        {**weather_to_dict(w), "confidence": round(max(0.5, 1.0 - i * 0.05), 2)}
        for i, w in enumerate(engine.weather.forecast(engine.current_sol, 7))
    ]

    # Crop catalog (static)
    snapshot["crop_catalog"] = {
        crop_type.value: {**info} for crop_type, info in CROP_CATALOG.items()
    }

    # Events log (last 50 sols)
    since_sol = max(0, engine.current_sol - 50)
    snapshot["events_log"] = {
        "events": [e.to_dict() for e in engine.events.since(since_sol)]
    }

    # Sensor readings
    snapshot["sensors_readings"] = {
        "timestamp_sol": engine.current_sol + 0.5,
        "readings": engine.sensor_readings(),
    }

    return snapshot


def _weather_to_dict(w: Any) -> dict[str, Any]:
    """Convert a WeatherState to a plain dict (matches telemetry router shape)."""
    return {
        "sol": w.sol,
        "min_temp_c": w.min_temp_c,
        "max_temp_c": w.max_temp_c,
        "avg_temp_c": w.avg_temp_c,
        "pressure_pa": w.pressure_pa,
        "solar_irradiance_wm2": w.solar_irradiance_wm2,
        "dust_opacity": w.dust_opacity,
        "season": w.season,
        "ls": w.ls,
        "sol_in_year": w.sol_in_year,
    }


def _sim_status(engine: SimulationEngine) -> dict[str, Any]:
    return {
        "current_sol": engine.current_sol,
        "total_sols": engine.mission_duration_sols,
        "mission_phase": engine.mission_phase.value,
        "paused": engine.paused,
    }


def _weather_current(engine: SimulationEngine) -> dict[str, Any] | None:
    w = engine.weather.current()
    if w is None:
        return None
    return {
        "sol": w.sol,
        "min_temp_c": w.min_temp_c,
        "max_temp_c": w.max_temp_c,
        "avg_temp_c": w.avg_temp_c,
        "pressure_pa": w.pressure_pa,
        "solar_irradiance_wm2": w.solar_irradiance_wm2,
        "dust_opacity": w.dust_opacity,
        "season": w.season,
        "ls": w.ls,
        "sol_in_year": w.sol_in_year,
    }


def _energy_status(engine: SimulationEngine) -> dict[str, Any]:
    s = engine.energy.state
    return {
        "solar_generation_wh": s.solar_generation_wh,
        "battery_level_wh": s.battery_level_wh,
        "battery_capacity_wh": s.battery_capacity_wh,
        "battery_pct": engine.energy.battery_pct,
        "total_consumption_wh": s.total_consumption_wh,
        "breakdown": s.breakdown,
        "surplus_wh": s.surplus_wh,
        "deficit": s.deficit,
        "allocation": s.allocation,
    }


def _greenhouse_environment(engine: SimulationEngine) -> dict[str, Any]:
    zones = [
        {
            "zone_id": z.zone_id,
            "temp_c": z.temp_c,
            "humidity_pct": z.humidity_pct,
            "co2_ppm": z.co2_ppm,
            "par_umol_m2s": z.par_umol_m2s,
            "light_on": z.light_on,
            "photoperiod_hours": z.photoperiod_hours,
            "area_m2": z.area_m2,
            "target_temp_c": z.target_temp_c,
            "target_humidity_pct": z.target_humidity_pct,
            "target_co2_ppm": z.target_co2_ppm,
            "target_par": z.target_par,
            "target_photoperiod_hours": z.target_photoperiod_hours,
        }
        for z in engine.climate.state.values()
    ]
    w = engine.weather.current()
    return {
        "zones": zones,
        "total_area_m2": sum(ZONE_AREAS_M2.values()),
        "external_temp_c": w.avg_temp_c if w else None,
    }


def _water_status(engine: SimulationEngine) -> dict[str, Any]:
    s = engine.water.state
    return {
        "reservoir_liters": s.reservoir_liters,
        "reservoir_capacity_liters": s.reservoir_capacity_liters,
        "recycling_efficiency_pct": s.recycling_efficiency_pct,
        "daily_crew_consumption_liters": s.daily_crew_consumption_liters,
        "daily_crop_consumption_liters": s.daily_crop_consumption_liters,
        "daily_recycled_liters": s.daily_recycled_liters,
        "daily_net_change_liters": s.daily_net_change_liters,
        "days_until_critical": s.days_until_critical,
        "filter_health_pct": s.filter_health_pct,
        "irrigation_settings": s.irrigation_settings,
        "drill_health_pct": s.drill_health_pct,
        "last_mining_sol": s.last_mining_sol,
        "daily_mined_liters": s.daily_mined_liters,
        "total_mined_liters": s.total_mined_liters,
    }


def _crops_status(engine: SimulationEngine) -> dict[str, Any]:
    crops = []
    for batch in engine.crops.batches.values():
        crops.append(
            {
                "crop_id": batch.crop_id,
                "type": batch.crop_type.value,
                "zone_id": batch.zone_id,
                "planted_sol": batch.planted_sol,
                "current_sol": engine.current_sol,
                "days_in_cycle": batch.age_days,
                "expected_harvest_sol": batch.planted_sol + batch.growth_days,
                "growth_pct": batch.growth_pct,
                "health": batch.health,
                "is_ready": batch.is_ready,
                "stress_indicators": [
                    {"type": s.type, "since_sol": s.since_sol, "severity": s.severity}
                    for s in batch.stress_indicators
                ],
                "area_m2": batch.area_m2,
                "soil_moisture_pct": batch.soil_moisture_pct,
                "is_bolting": batch.is_bolting,
                "estimated_yield_kg": batch.estimated_yield_kg(),
                "estimated_calories_kcal": batch.estimated_calories_kcal(),
            }
        )

    total_planted = engine.crops.total_planted_area()
    available_per_zone = {
        z_id: max(0.0, area - engine.crops.zone_used_area(z_id))
        for z_id, area in ZONE_AREAS_M2.items()
    }
    return {
        "crops": crops,
        "total_planted_area_m2": total_planted,
        "available_area_per_zone": available_per_zone,
        "seeds_remaining": {
            k.value: v for k, v in engine.crops.seeds_remaining.items()
        },
    }


def _nutrients_status(engine: SimulationEngine) -> dict[str, Any]:
    zones = [
        {
            "zone_id": z.zone_id,
            "solution_ph": z.solution_ph,
            "solution_ec_ms_cm": z.solution_ec_ms_cm,
            "base_salt_ppm": z.base_salt_ppm,
            "solution_temp_c": z.solution_temp_c,
            "dissolved_o2_ppm": z.dissolved_o2_ppm,
            "nitrogen_ppm": z.nitrogen_ppm,
            "phosphorus_ppm": z.phosphorus_ppm,
            "potassium_ppm": z.potassium_ppm,
            "calcium_ppm": z.calcium_ppm,
            "magnesium_ppm": z.magnesium_ppm,
        }
        for z in engine.nutrients.state.values()
    ]
    return {
        "zones": zones,
        "nutrient_stock_remaining_pct": engine.nutrients.stock_remaining_pct,
        "days_of_stock_remaining": engine.nutrients.days_of_stock_remaining,
    }


def _crew_nutrition(engine: SimulationEngine) -> dict[str, Any]:
    s = engine.crew.state
    total_stored_kcal = s.stored_kcal + s.fresh_buffer_kcal
    days_at_rate = total_stored_kcal / CREW_DAILY_KCAL if CREW_DAILY_KCAL > 0 else 999
    return {
        "current_sol": engine.current_sol,
        "today": {
            "calories_consumed_kcal": s.today_kcal_consumed,
            "calories_target_kcal": s.today_kcal_target,
            "protein_consumed_g": s.today_protein_consumed_g,
            "protein_target_g": s.today_protein_target_g,
            "from_greenhouse_pct": s.from_greenhouse_pct,
            "from_stored_food_pct": s.from_stored_pct,
        },
        "stored_food": {
            "remaining_kcal": round(s.stored_kcal, 0),
            "remaining_days_at_current_rate": round(days_at_rate, 1),
            "protein_remaining_g": s.stored_protein_g,
        },
        "food_buffer": {
            "fresh_harvest_kcal": round(s.fresh_buffer_kcal, 0),
            "fresh_harvest_protein_g": round(s.fresh_buffer_protein_g, 0),
            "days_of_buffer": round(s.fresh_buffer_kcal / CREW_DAILY_KCAL, 2)
            if CREW_DAILY_KCAL
            else 0,
        },
        "cumulative": {
            "avg_daily_kcal": s.cumulative_avg_kcal,
            "avg_daily_protein_g": s.cumulative_avg_protein_g,
            "deficit_sols": s.deficit_sols,
            "surplus_sols": s.surplus_sols,
        },
        "crew_status": s.crew_status.value,
        "micronutrients": {
            "sufficient_today": s.micronutrients_sufficient,
            "level": engine.crew.health.micronutrient_level.value,
            "consecutive_deficit_sols": engine.crew.health.consecutive_micronutrient_deficit_sols,
            "health_penalty_pct": engine.crew.health.micronutrient_health_penalty,
        },
        "food_inventory": {
            food_type: {
                "kg_remaining": round(kg, 2),
                "kcal_remaining": round(kg * FOOD_KCAL_PER_KG[food_type]),
                "protein_g_remaining": round(kg * FOOD_PROTEIN_G_PER_KG[food_type]),
                "pct_remaining": round(kg / INITIAL_FOOD_KG[food_type] * 100.0, 1)
                if INITIAL_FOOD_KG[food_type] > 0
                else 0.0,
            }
            for food_type, kg in s.stored_food_kg.items()
        },
        "days_of_food_remaining": round(engine.crew.days_of_food, 1),
        "days_of_protein_remaining": round(engine.crew.days_of_protein, 1),
    }


def _active_crises(engine: SimulationEngine) -> dict[str, Any]:
    return {
        "crises": [
            {
                "id": c.id,
                "type": c.type.value,
                "started_sol": c.started_sol,
                "severity": c.severity.value,
                "message": c.message,
                "current_value": c.current_value,
                "threshold": c.threshold,
                "resolved": c.resolved,
                "resolved_sol": c.resolved_sol,
            }
            for c in engine.events.active_crises()
        ]
    }


def _score_current(engine: SimulationEngine) -> dict[str, Any]:
    snap = engine.scoring.snapshot
    return {
        "current_sol": snap.current_sol,
        "scores": {
            "survival": snap.survival,
            "nutrition": snap.nutrition,
            "resource_efficiency": snap.resource_efficiency,
            "crisis_management": snap.crisis_management,
            "overall_score": snap.overall_score,
        },
    }


def _crew_members(engine: SimulationEngine) -> dict[str, Any]:
    return {
        "current_sol": engine.current_sol,
        "crew_size": len(engine.crew.health.members),
        "members": [
            {
                "member_id": m.member_id,
                "name": m.name,
                "alive": m.alive,
                "status": m.status.value,
                "health_pct": m.health_pct,
                "hydration_pct": m.hydration_pct,
                "cumulative_radiation_msv": m.cumulative_radiation_msv,
            }
            for m in engine.crew.health.members
        ],
    }


def _crew_health(engine: SimulationEngine) -> dict[str, Any]:
    h = engine.crew.health
    return {
        "current_sol": engine.current_sol,
        "alive": h.alive,
        "cause_of_death": h.cause_of_death,
        "overall_health_pct": h.overall_health_pct,
        "hydration": {
            "hydration_pct": h.hydration_pct,
            "level": h.dehydration_level.value,
            "daily_water_received_l": h.daily_water_received_l,
            "daily_water_required_l": h.daily_water_required_l,
            "water_fraction_met": round(h.water_fraction_met, 3),
            "consecutive_deficit_sols": h.consecutive_water_deficit_sols,
        },
        "radiation": {
            "cumulative_msv": h.cumulative_radiation_msv,
            "daily_dose_msv": round(h.daily_radiation_msv, 3),
            "warning_active": h.radiation_warning_active,
            "critical_active": h.radiation_critical_active,
            "nasa_career_limit_msv": 600.0,
            "pct_of_career_limit": round(h.cumulative_radiation_msv / 600.0 * 100.0, 1),
        },
        "temperature": {
            "ambient_temp_c": h.ambient_temp_c,
            "hypothermia_risk": h.hypothermia_risk,
            "hyperthermia_risk": h.hyperthermia_risk,
            "health_penalty_pct": h.temperature_health_penalty,
            "nasa_comfort_range_c": [18.3, 26.7],
        },
        "co2": {
            "ambient_co2_ppm": h.ambient_co2_ppm,
            "health_impaired": h.co2_health_impaired,
            "health_penalty_pct": h.co2_health_penalty,
            "osha_8h_limit_ppm": 5000,
        },
        "starvation": {
            "level": h.starvation_level.value,
            "consecutive_deficit_sols": h.consecutive_caloric_deficit_sols,
            "health_penalty_pct": h.starvation_health_penalty,
        },
        "micronutrients": {
            "level": h.micronutrient_level.value,
            "consecutive_deficit_sols": h.consecutive_micronutrient_deficit_sols,
            "health_penalty_pct": h.micronutrient_health_penalty,
        },
        "illness": {
            "active": h.illness.active,
            "sick_member_name": h.illness.sick_member_name,
            "duration_remaining_sols": h.illness.duration_remaining_sols,
            "kcal_multiplier": h.illness.kcal_multiplier,
            "protein_multiplier": h.illness.protein_multiplier,
        },
    }
