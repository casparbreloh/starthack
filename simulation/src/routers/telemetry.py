"""
Telemetry (read-only) router — all GET endpoints.

Covers the full simulation spec:
  /sim/status
  /weather/current, /weather/history, /weather/forecast
  /energy/status
  /greenhouse/environment
  /water/status
  /crops/status
  /nutrients/status
  /crew/nutrition
  /sensors/readings
  /events/log, /events/active_crises
  /score/current, /score/final
  /crops/catalog
"""

from typing import Any

from fastapi import APIRouter, HTTPException, Query

from src.catalog import CROP_CATALOG
from src.constants import (
    CREW_DAILY_KCAL,
    FOOD_KCAL_PER_KG,
    FOOD_PROTEIN_G_PER_KG,
    INITIAL_FOOD_KG,
    MISSION_DURATION_SOLS,
    ZONE_AREAS_M2,
)
from src.engine import SimulationEngine
from src.enums import MissionPhase
from src.models.responses import (
    ActiveCrisesResponse,
    CrewHealthResponse,
    CrewMembersResponse,
    CrewNutritionResponse,
    CropsStatusResponse,
    EnergyStatusResponse,
    EventsLogResponse,
    GreenhouseEnvironmentResponse,
    NutrientsStatusResponse,
    ScoreCurrentResponse,
    ScoreFinalResponse,
    SensorsReadingsResponse,
    SimStatusResponse,
    WaterStatusResponse,
    WeatherForecastResponse,
    WeatherResponse,
)
from src.state import session_manager

router = APIRouter()


def _engine(session_id: str | None) -> SimulationEngine:
    return session_manager.get_or_default(session_id).engine


# ──────────────────────────────────────────────────────────────────────────────
# Simulation status
# ──────────────────────────────────────────────────────────────────────────────


@router.get("/sim/status", response_model=SimStatusResponse)
def sim_status(session_id: str | None = Query(default=None)):
    engine = _engine(session_id)
    return {
        "current_sol": engine.current_sol,
        "total_sols": MISSION_DURATION_SOLS,
        "mission_phase": engine.mission_phase.value,
        "paused": engine.paused,
    }


# ──────────────────────────────────────────────────────────────────────────────
# Mars Weather
# ──────────────────────────────────────────────────────────────────────────────


@router.get("/weather/current", response_model=WeatherResponse)
def weather_current(session_id: str | None = Query(default=None)):
    engine = _engine(session_id)
    w = engine.weather.current()
    if w is None:
        raise HTTPException(404, "No weather data yet — advance the simulation first")
    return _weather_to_dict(w)


@router.get("/weather/history", response_model=list[WeatherResponse])
def weather_history(
    last_n_sols: int = Query(default=30, ge=1, le=450),
    session_id: str | None = Query(default=None),
):
    engine = _engine(session_id)
    return [_weather_to_dict(w) for w in engine.weather.history(last_n_sols)]


@router.get("/weather/forecast", response_model=list[WeatherForecastResponse])
def weather_forecast(
    horizon: int = Query(default=7, ge=1, le=30),
    session_id: str | None = Query(default=None),
):
    engine = _engine(session_id)
    return [
        {**_weather_to_dict(w), "confidence": round(max(0.5, 1.0 - i * 0.05), 2)}
        for i, w in enumerate(engine.weather.forecast(engine.current_sol, horizon))
    ]


# ──────────────────────────────────────────────────────────────────────────────
# Energy
# ──────────────────────────────────────────────────────────────────────────────


@router.get("/energy/status", response_model=EnergyStatusResponse)
def energy_status(session_id: str | None = Query(default=None)):
    engine = _engine(session_id)
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


# ──────────────────────────────────────────────────────────────────────────────
# Greenhouse Environment
# ──────────────────────────────────────────────────────────────────────────────


@router.get("/greenhouse/environment", response_model=GreenhouseEnvironmentResponse)
def greenhouse_environment(session_id: str | None = Query(default=None)):
    engine = _engine(session_id)
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
            # Setpoints
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


# ──────────────────────────────────────────────────────────────────────────────
# Water
# ──────────────────────────────────────────────────────────────────────────────


@router.get("/water/status", response_model=WaterStatusResponse)
def water_status(session_id: str | None = Query(default=None)):
    engine = _engine(session_id)
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
    }


# ──────────────────────────────────────────────────────────────────────────────
# Crops
# ──────────────────────────────────────────────────────────────────────────────


@router.get("/crops/status", response_model=CropsStatusResponse)
def crops_status(session_id: str | None = Query(default=None)):
    engine = _engine(session_id)
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


# ──────────────────────────────────────────────────────────────────────────────
# Nutrients
# ──────────────────────────────────────────────────────────────────────────────


@router.get("/nutrients/status", response_model=NutrientsStatusResponse)
def nutrients_status(session_id: str | None = Query(default=None)):
    engine = _engine(session_id)
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


# ──────────────────────────────────────────────────────────────────────────────
# Crew & Nutrition
# ──────────────────────────────────────────────────────────────────────────────


@router.get("/crew/nutrition", response_model=CrewNutritionResponse)
def crew_nutrition(session_id: str | None = Query(default=None)):
    engine = _engine(session_id)
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


# ──────────────────────────────────────────────────────────────────────────────
# Crew Health (new — detailed vitals)
# ──────────────────────────────────────────────────────────────────────────────


@router.get("/crew/health", response_model=CrewHealthResponse)
def crew_health(session_id: str | None = Query(default=None)):
    """
    Detailed crew health vitals.

    Tracks hydration (WHO StatPearls NBK555956), radiation dose
    (Hassler et al. 2014 / NASA-STD-3001), CO2 effects (OSHA 1910.1000),
    temperature stress (NASA-STD-3001 Vol.2 §6.2.1), and starvation
    (WHO TRS 724).
    """
    engine = _engine(session_id)
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


@router.get("/crew/members", response_model=CrewMembersResponse)
def crew_members(session_id: str | None = Query(default=None)):
    """Individual health card for each of the 4 crew members."""
    engine = _engine(session_id)
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


# ──────────────────────────────────────────────────────────────────────────────
# Sensors
# ──────────────────────────────────────────────────────────────────────────────


@router.get("/sensors/readings", response_model=SensorsReadingsResponse)
def sensors_readings(session_id: str | None = Query(default=None)):
    engine = _engine(session_id)
    return {
        "timestamp_sol": engine.current_sol + 0.5,
        "readings": engine.sensor_readings(),
    }


# ──────────────────────────────────────────────────────────────────────────────
# Events
# ──────────────────────────────────────────────────────────────────────────────


@router.get("/events/log", response_model=EventsLogResponse)
def events_log(
    since_sol: int = Query(default=0, ge=0),
    session_id: str | None = Query(default=None),
):
    engine = _engine(session_id)
    events = engine.events.since(since_sol)
    return {"events": [e.to_dict() for e in events]}


@router.get("/events/active_crises", response_model=ActiveCrisesResponse)
def events_active_crises(session_id: str | None = Query(default=None)):
    engine = _engine(session_id)
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


# ──────────────────────────────────────────────────────────────────────────────
# Scoring
# ──────────────────────────────────────────────────────────────────────────────


@router.get("/score/current", response_model=ScoreCurrentResponse)
def score_current(session_id: str | None = Query(default=None)):
    engine = _engine(session_id)
    snap = engine.scoring.snapshot
    return {
        "current_sol": snap.current_sol,
        "scores": _snapshot_to_scores(snap),
    }


@router.get("/score/final", response_model=ScoreFinalResponse)
def score_final(session_id: str | None = Query(default=None)):
    engine = _engine(session_id)
    if engine.mission_phase != MissionPhase.COMPLETE:
        raise HTTPException(
            400,
            f"Mission not yet complete (sol {engine.current_sol}/{MISSION_DURATION_SOLS})",
        )
    snap = engine.scoring.snapshot
    return {
        "final_sol": snap.current_sol,
        "mission_phase": engine.mission_phase.value,
        "final_scores": _snapshot_to_scores(snap),
        "agent_decisions_logged": len(engine.agent_decisions),
    }


# ──────────────────────────────────────────────────────────────────────────────
# Static catalog
# ──────────────────────────────────────────────────────────────────────────────


@router.get("/crops/catalog")
def catalog_crops():
    return {crop_type.value: {**info} for crop_type, info in CROP_CATALOG.items()}


# ──────────────────────────────────────────────────────────────────────────────
# Master state endpoint
# ──────────────────────────────────────────────────────────────────────────────


@router.get("/sim/state")
def sim_state(session_id: str | None = Query(default=None)):
    """Full telemetry snapshot — convenience endpoint for the frontend."""
    engine = _engine(session_id)
    return {
        "current_sol": engine.current_sol,
        "mission_phase": engine.mission_phase.value,
        "crew_inventory": {
            "stored_kcal": engine.crew.state.stored_kcal,
            "fresh_buffer_kcal": engine.crew.state.fresh_buffer_kcal,
            "total_kcal": engine.crew.total_kcal,
            "days_of_food": engine.crew.days_of_food,
            "stored_protein_g": engine.crew.state.stored_protein_g,
            "water_reservoir_L": engine.water.state.reservoir_liters,
            "crew_status": engine.crew.state.crew_status.value,
            "micronutrients_sufficient": engine.crew.state.micronutrients_sufficient,
        },
        "facility_environment": {
            "zones": [
                {
                    "zone_id": z.zone_id,
                    "temp_c": z.temp_c,
                    "co2_ppm": z.co2_ppm,
                    "humidity_pct": z.humidity_pct,
                    "par_umol_m2s": z.par_umol_m2s,
                }
                for z in engine.climate.state.values()
            ],
            "recycling_efficiency_pct": engine.water.state.recycling_efficiency_pct,
            "filter_health_pct": engine.water.state.filter_health_pct,
            "battery_pct": engine.energy.battery_pct,
            "solar_generation_wh": engine.energy.state.solar_generation_wh,
        },
        "beds": [
            {
                "crop_id": b.crop_id,
                "crop_type": b.crop_type.value,
                "zone_id": b.zone_id,
                "age_days": b.age_days,
                "growth_pct": b.growth_pct,
                "health_score": round(b.health * 100, 1),
                "soil_moisture_pct": b.soil_moisture_pct,
                "is_bolting": b.is_bolting,
                "is_ready": b.is_ready,
                "active_stressors": [s.type for s in b.stress_indicators],
            }
            for b in engine.crops.batches.values()
        ],
        "active_crises": len(engine.events.active_crises()),
        "recent_events": [
            {
                "sol": e.sol,
                "type": e.type,
                "message": e.message,
                "severity": e.severity.value,
            }
            for e in engine.events.recent(10)
        ],
        "score": engine.scoring.snapshot.overall_score,
    }


# ──────────────────────────────────────────────────────────────────────────────
# Private helpers
# ──────────────────────────────────────────────────────────────────────────────


def _snapshot_to_scores(snap) -> dict[str, Any]:
    return {
        "survival": snap.survival,
        "nutrition": snap.nutrition,
        "resource_efficiency": snap.resource_efficiency,
        "crisis_management": snap.crisis_management,
        "overall_score": snap.overall_score,
    }


def _weather_to_dict(w) -> dict[str, Any]:
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
