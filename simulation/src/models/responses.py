"""
Pydantic response models for all telemetry and admin endpoints.

These models drive the OpenAPI schema in FastAPI's auto-generated docs
without changing any endpoint return logic (endpoints still return dicts).
"""

from __future__ import annotations

from typing import Any

from pydantic import BaseModel

# ──────────────────────────────────────────────────────────────────────────────
# /sim/status
# ──────────────────────────────────────────────────────────────────────────────


class SimStatusResponse(BaseModel):
    current_sol: int
    total_sols: int
    mission_phase: str
    paused: bool


# ──────────────────────────────────────────────────────────────────────────────
# /weather/*
# ──────────────────────────────────────────────────────────────────────────────


class WeatherResponse(BaseModel):
    sol: int
    min_temp_c: float
    max_temp_c: float
    avg_temp_c: float
    pressure_pa: float
    solar_irradiance_wm2: float
    dust_opacity: float
    season: str
    ls: float
    sol_in_year: int


class WeatherForecastResponse(WeatherResponse):
    confidence: float


# ──────────────────────────────────────────────────────────────────────────────
# /energy/status
# ──────────────────────────────────────────────────────────────────────────────


class EnergyBreakdownResponse(BaseModel):
    heating_wh: float
    lighting_wh: float
    water_recycling_wh: float
    nutrient_pumps_wh: float
    sensors_control_wh: float
    other_wh: float


class EnergyAllocationResponse(BaseModel):
    heating_pct: int
    lighting_pct: int
    water_recycling_pct: int
    nutrient_pumps_pct: int
    reserve_pct: int


class EnergyStatusResponse(BaseModel):
    solar_generation_wh: float
    battery_level_wh: float
    battery_capacity_wh: float
    battery_pct: float
    total_consumption_wh: float
    breakdown: EnergyBreakdownResponse
    surplus_wh: float
    deficit: bool
    allocation: EnergyAllocationResponse


# ──────────────────────────────────────────────────────────────────────────────
# /greenhouse/environment
# ──────────────────────────────────────────────────────────────────────────────


class ZoneEnvironmentResponse(BaseModel):
    zone_id: str
    temp_c: float
    humidity_pct: float
    co2_ppm: float
    par_umol_m2s: float
    light_on: bool
    photoperiod_hours: float
    area_m2: float
    target_temp_c: float
    target_humidity_pct: float
    target_co2_ppm: float
    target_par: float
    target_photoperiod_hours: float


class GreenhouseEnvironmentResponse(BaseModel):
    zones: list[ZoneEnvironmentResponse]
    total_area_m2: float
    external_temp_c: float | None


# ──────────────────────────────────────────────────────────────────────────────
# /water/status
# ──────────────────────────────────────────────────────────────────────────────


class WaterStatusResponse(BaseModel):
    reservoir_liters: float
    reservoir_capacity_liters: float
    recycling_efficiency_pct: float
    daily_crew_consumption_liters: float
    daily_crop_consumption_liters: float
    daily_recycled_liters: float
    daily_net_change_liters: float
    days_until_critical: float
    filter_health_pct: float
    irrigation_settings: dict[str, float]


# ──────────────────────────────────────────────────────────────────────────────
# /crops/status
# ──────────────────────────────────────────────────────────────────────────────


class StressIndicatorResponse(BaseModel):
    type: str
    since_sol: int
    severity: float


class CropBatchResponse(BaseModel):
    crop_id: str
    type: str
    zone_id: str
    planted_sol: int
    current_sol: int
    days_in_cycle: int
    expected_harvest_sol: int
    growth_pct: float
    health: float
    is_ready: bool
    stress_indicators: list[StressIndicatorResponse]
    area_m2: float
    soil_moisture_pct: float
    estimated_yield_kg: float
    estimated_calories_kcal: float


class CropsStatusResponse(BaseModel):
    crops: list[CropBatchResponse]
    total_planted_area_m2: float
    available_area_per_zone: dict[str, float]
    seeds_remaining: dict[str, int]


# ──────────────────────────────────────────────────────────────────────────────
# /nutrients/status
# ──────────────────────────────────────────────────────────────────────────────


class ZoneNutrientsResponse(BaseModel):
    zone_id: str
    solution_ph: float
    solution_ec_ms_cm: float
    solution_temp_c: float
    dissolved_o2_ppm: float
    nitrogen_ppm: float
    phosphorus_ppm: float
    potassium_ppm: float
    calcium_ppm: float
    magnesium_ppm: float


class NutrientsStatusResponse(BaseModel):
    zones: list[ZoneNutrientsResponse]
    nutrient_stock_remaining_pct: float
    days_of_stock_remaining: float


# ──────────────────────────────────────────────────────────────────────────────
# /crew/nutrition
# ──────────────────────────────────────────────────────────────────────────────


class CrewNutritionTodayResponse(BaseModel):
    calories_consumed_kcal: float
    calories_target_kcal: float
    protein_consumed_g: float
    protein_target_g: float
    from_greenhouse_pct: float
    from_stored_food_pct: float


class StoredFoodResponse(BaseModel):
    remaining_kcal: float
    remaining_days_at_current_rate: float
    protein_remaining_g: float


class FoodBufferResponse(BaseModel):
    fresh_harvest_kcal: float
    fresh_harvest_protein_g: float
    days_of_buffer: float


class CumulativeNutritionResponse(BaseModel):
    avg_daily_kcal: float
    avg_daily_protein_g: float
    deficit_sols: int
    surplus_sols: int


class CrewNutritionResponse(BaseModel):
    current_sol: int
    today: CrewNutritionTodayResponse
    stored_food: StoredFoodResponse
    food_buffer: FoodBufferResponse
    cumulative: CumulativeNutritionResponse
    crew_status: str
    micronutrients_sufficient: bool
    days_of_food_remaining: float
    days_of_protein_remaining: float


# ──────────────────────────────────────────────────────────────────────────────
# /crew/health
# ──────────────────────────────────────────────────────────────────────────────


class HydrationResponse(BaseModel):
    hydration_pct: float
    level: str
    daily_water_received_l: float
    daily_water_required_l: float
    water_fraction_met: float
    consecutive_deficit_sols: int


class RadiationResponse(BaseModel):
    cumulative_msv: float
    daily_dose_msv: float
    warning_active: bool
    critical_active: bool
    nasa_career_limit_msv: float
    pct_of_career_limit: float


class TemperatureHealthResponse(BaseModel):
    ambient_temp_c: float
    hypothermia_risk: bool
    hyperthermia_risk: bool
    health_penalty_pct: float
    nasa_comfort_range_c: list[float]


class Co2HealthResponse(BaseModel):
    ambient_co2_ppm: float
    health_impaired: bool
    health_penalty_pct: float
    osha_8h_limit_ppm: int


class StarvationResponse(BaseModel):
    level: str
    consecutive_deficit_sols: int
    health_penalty_pct: float


class CrewHealthResponse(BaseModel):
    current_sol: int
    alive: bool
    cause_of_death: str | None
    overall_health_pct: float
    hydration: HydrationResponse
    radiation: RadiationResponse
    temperature: TemperatureHealthResponse
    co2: Co2HealthResponse
    starvation: StarvationResponse


# ──────────────────────────────────────────────────────────────────────────────
# /crew/members
# ──────────────────────────────────────────────────────────────────────────────


class CrewMemberResponse(BaseModel):
    member_id: int
    name: str
    alive: bool
    status: str
    health_pct: float
    hydration_pct: float
    cumulative_radiation_msv: float


class CrewMembersResponse(BaseModel):
    current_sol: int
    crew_size: int
    members: list[CrewMemberResponse]


# ──────────────────────────────────────────────────────────────────────────────
# /sensors/readings
# ──────────────────────────────────────────────────────────────────────────────


class SensorReadingResponse(BaseModel):
    sensor_id: str
    zone: str
    type: str
    value: float
    unit: str
    status: str


class SensorsReadingsResponse(BaseModel):
    timestamp_sol: float
    readings: list[SensorReadingResponse]


# ──────────────────────────────────────────────────────────────────────────────
# /events/log
# ──────────────────────────────────────────────────────────────────────────────


class EventResponse(BaseModel):
    sol: int
    type: str
    category: str
    message: str
    severity: str
    zone: str | None
    data: dict[str, Any] | None


class EventsLogResponse(BaseModel):
    events: list[EventResponse]


# ──────────────────────────────────────────────────────────────────────────────
# /events/active_crises
# ──────────────────────────────────────────────────────────────────────────────


class CrisisResponse(BaseModel):
    id: str
    type: str
    started_sol: int
    severity: str
    message: str
    current_value: float
    threshold: float
    resolved: bool
    resolved_sol: int | None


class ActiveCrisesResponse(BaseModel):
    crises: list[CrisisResponse]


# ──────────────────────────────────────────────────────────────────────────────
# /score/current
# ──────────────────────────────────────────────────────────────────────────────


class SurvivalScoreResponse(BaseModel):
    crew_alive: bool
    days_without_critical_deficit: int
    score: int


class NutritionScoreResponse(BaseModel):
    avg_daily_kcal: float
    target_kcal: int
    kcal_achievement_pct: float
    avg_daily_protein_g: float
    protein_achievement_pct: float
    micronutrient_diversity_score: float
    score: int


class ResourceEfficiencyScoreResponse(BaseModel):
    water_efficiency_pct: float
    energy_efficiency_pct: float
    crop_waste_pct: float
    score: int


class CrisisManagementScoreResponse(BaseModel):
    crises_encountered: int
    crises_resolved: int
    avg_resolution_sols: float
    preventive_actions_taken: int
    score: int


class ScoreBreakdownResponse(BaseModel):
    survival: SurvivalScoreResponse
    nutrition: NutritionScoreResponse
    resource_efficiency: ResourceEfficiencyScoreResponse
    crisis_management: CrisisManagementScoreResponse
    overall_score: int


class ScoreCurrentResponse(BaseModel):
    current_sol: int
    scores: ScoreBreakdownResponse


# ──────────────────────────────────────────────────────────────────────────────
# /score/final
# ──────────────────────────────────────────────────────────────────────────────


class ScoreFinalResponse(BaseModel):
    final_sol: int
    mission_phase: str
    final_scores: ScoreBreakdownResponse
    agent_decisions_logged: int


# ──────────────────────────────────────────────────────────────────────────────
# POST /sim/advance
# ──────────────────────────────────────────────────────────────────────────────


class SimAdvanceResponse(BaseModel):
    new_sol: int
    mission_phase: str
    events: list[dict[str, Any]]
