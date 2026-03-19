// Hand-written adapter types used by the GameView components.
// These are shaped by lib/api.ts adapters (not the raw API format).

// === Simulation Control ===
export interface SimStatus {
  current_sol: number;
  total_sols: number;
  mission_phase: string;
  paused: boolean;
}

// === Weather ===
export interface WeatherCurrent {
  temp_min_c: number;
  temp_max_c: number;
  pressure_mbar: number;
  solar_irradiance_w_m2: number;
  dust_opacity: number;
  season: string;
}

export interface WeatherForecastDay {
  sol: number;
  temp_min_c: number;
  temp_max_c: number;
  dust_opacity: number;
  solar_irradiance_w_m2: number;
  confidence: number;
}

export interface WeatherHistoryEntry {
  sol: number;
  temp_min_c: number;
  temp_max_c: number;
  pressure_mbar: number;
  solar_irradiance_w_m2: number;
  dust_opacity: number;
}

// === Energy ===
export interface EnergyStatus {
  solar_generation_kw: number;
  battery_pct: number;
  consumption: {
    heating_kw: number;
    lighting_kw: number;
    water_kw: number;
    nutrients_kw: number;
  };
  surplus_deficit_kw: number;
}

// === Greenhouse Zones ===
export interface ZoneEnvironment {
  zone_id: string;
  temp_c: number;
  humidity_pct: number;
  co2_ppm: number;
  par_light_umol: number;
  photoperiod_hours: number;
}

// === Water ===
export interface WaterStatus {
  reservoir_level_pct: number;
  recycling_efficiency_pct: number;
  filter_health_pct: number;
  days_until_critical: number;
  daily_consumption_l: number;
  daily_recycled_l: number;
}

// === Crops ===
export interface CropBatch {
  crop_id: string;
  crop_type: string;
  zone_id: string;
  growth_pct: number;
  health_pct: number;
  stress_water: number;
  stress_nutrient: number;
  stress_light: number;
  stress_temp: number;
  days_to_harvest: number;
  yield_estimate_kg: number;
  area_m2: number;
}

export interface CropCatalogEntry {
  crop_type: string;
  growth_days: number;
  water_need_l_per_sol: number;
  light_need_hours: number;
  optimal_temp_c: number;
  yield_kg_per_m2: number;
}

// === Nutrients ===
export interface ZoneNutrients {
  zone_id: string;
  ph: number;
  ec_ms_cm: number;
  nitrogen_ppm: number;
  phosphorus_ppm: number;
  potassium_ppm: number;
  calcium_ppm: number;
  magnesium_ppm: number;
  stock_remaining_pct: number;
  days_of_stock: number;
}

// === Crew ===
export interface CrewHealth {
  overall_health_pct: number;
  hydration_pct: number;
  radiation_cumulative_msv: number;
  co2_impact: number;
  starvation_level: number;
  illness: string | null;
}

export interface CrewMember {
  name: string;
  alive: boolean;
  status: string;
  health_pct: number;
  hydration_pct: number;
  radiation_msv: number;
}

export interface CrewNutrition {
  daily_calories_consumed: number;
  daily_calories_target: number;
  daily_protein_consumed_g: number;
  daily_protein_target_g: number;
  greenhouse_food_pct: number;
  stored_food_pct: number;
  days_of_food_remaining: number;
  food_inventory: Record<string, number>;
}

// === Events ===
export interface EventLogEntry {
  sol: number;
  type: string;
  severity: "info" | "warning" | "critical";
  zone: string | null;
  message: string;
}

export interface ActiveCrisis {
  type: string;
  severity: string;
  threshold_breach: string;
  resolution_status: string;
}

// === Score ===
export interface ScoreCurrent {
  survival: number;
  nutrition: number;
  resource_efficiency: number;
  crisis_management: number;
  overall_score: number;
}
