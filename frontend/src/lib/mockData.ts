import type * as T from "@/types/game";

// Mock data used when the backend API is not reachable

export const mockSimStatus: T.SimStatus = {
  current_sol: 247,
  total_sols: 450,
  mission_phase: "GROWTH",
  paused: false,
};

export const mockWeather: T.WeatherCurrent = {
  temp_min_c: -73,
  temp_max_c: -63,
  pressure_mbar: 6.1,
  solar_irradiance_w_m2: 590,
  dust_opacity: 0.3,
  season: "Ls 247 — Late Spring",
};

export const mockEnergy: T.EnergyStatus = {
  solar_generation_kw: 4.2,
  battery_pct: 81,
  consumption: { heating_kw: 1.4, lighting_kw: 0.9, water_kw: 0.6, nutrients_kw: 0.3 },
  surplus_deficit_kw: 1.0,
};

export const mockWater: T.WaterStatus = {
  reservoir_level_pct: 73,
  recycling_efficiency_pct: 94.2,
  filter_health_pct: 88,
  days_until_critical: 62,
  daily_consumption_l: 48,
  daily_recycled_l: 45.2,
};

export const mockZones: T.ZoneEnvironment[] = [
  { zone_id: "zone_a", temp_c: 22.4, humidity_pct: 68, co2_ppm: 1200, par_light_umol: 450, photoperiod_hours: 16 },
  { zone_id: "zone_b", temp_c: 21.8, humidity_pct: 72, co2_ppm: 1150, par_light_umol: 380, photoperiod_hours: 14 },
  { zone_id: "zone_c", temp_c: 23.1, humidity_pct: 65, co2_ppm: 1300, par_light_umol: 500, photoperiod_hours: 16 },
];

export const mockCrops: T.CropBatch[] = [
  // Zone A — 4 beds
  { crop_id: "a1", crop_type: "Potato", zone_id: "zone_a", growth_pct: 72, health_pct: 92, stress_water: 0.1, stress_nutrient: 0.05, stress_light: 0, stress_temp: 0.02, days_to_harvest: 28, yield_estimate_kg: 18.5, area_m2: 9 },
  { crop_id: "a2", crop_type: "Lettuce", zone_id: "zone_a", growth_pct: 85, health_pct: 95, stress_water: 0.02, stress_nutrient: 0.03, stress_light: 0, stress_temp: 0, days_to_harvest: 8, yield_estimate_kg: 4.8, area_m2: 12 },
  { crop_id: "a3", crop_type: "Herbs", zone_id: "zone_a", growth_pct: 62, health_pct: 90, stress_water: 0.08, stress_nutrient: 0.05, stress_light: 0.02, stress_temp: 0.01, days_to_harvest: 18, yield_estimate_kg: 1.2, area_m2: 2 },
  { crop_id: "a4", crop_type: "Radish", zone_id: "zone_a", growth_pct: 55, health_pct: 86, stress_water: 0.12, stress_nutrient: 0.08, stress_light: 0.03, stress_temp: 0.05, days_to_harvest: 22, yield_estimate_kg: 3.1, area_m2: 4 },
  // Zone B — 4 beds
  { crop_id: "b1", crop_type: "Potato", zone_id: "zone_b", growth_pct: 45, health_pct: 50, stress_water: 0.15, stress_nutrient: 0.1, stress_light: 0.05, stress_temp: 0, days_to_harvest: 55, yield_estimate_kg: 12.2, area_m2: 6 },
  { crop_id: "b2", crop_type: "Lettuce", zone_id: "zone_b", growth_pct: 30, health_pct: 45, stress_water: 0.2, stress_nutrient: 0.15, stress_light: 0.1, stress_temp: 0.05, days_to_harvest: 35, yield_estimate_kg: 2.1, area_m2: 8 },
  { crop_id: "b3", crop_type: "Herbs", zone_id: "zone_b", growth_pct: 20, health_pct: 40, stress_water: 0.25, stress_nutrient: 0.2, stress_light: 0.1, stress_temp: 0.08, days_to_harvest: 40, yield_estimate_kg: 0.5, area_m2: 2 },
  { crop_id: "b4", crop_type: "Radish", zone_id: "zone_b", growth_pct: 38, health_pct: 82, stress_water: 0.2, stress_nutrient: 0.12, stress_light: 0.05, stress_temp: 0.08, days_to_harvest: 22, yield_estimate_kg: 3.1, area_m2: 4 },
  // Zone C — 4 beds
  { crop_id: "c1", crop_type: "Potato", zone_id: "zone_c", growth_pct: 90, health_pct: 96, stress_water: 0.05, stress_nutrient: 0.02, stress_light: 0, stress_temp: 0, days_to_harvest: 5, yield_estimate_kg: 22.0, area_m2: 9 },
  { crop_id: "c2", crop_type: "Lettuce", zone_id: "zone_c", growth_pct: 70, health_pct: 88, stress_water: 0.08, stress_nutrient: 0.05, stress_light: 0.02, stress_temp: 0.01, days_to_harvest: 15, yield_estimate_kg: 5.2, area_m2: 10 },
  { crop_id: "c3", crop_type: "Herbs", zone_id: "zone_c", growth_pct: 0, health_pct: 100, stress_water: 0, stress_nutrient: 0, stress_light: 0, stress_temp: 0, days_to_harvest: 60, yield_estimate_kg: 0, area_m2: 2 },
  { crop_id: "c4", crop_type: "Radish", zone_id: "zone_c", growth_pct: 80, health_pct: 92, stress_water: 0.05, stress_nutrient: 0.03, stress_light: 0, stress_temp: 0.02, days_to_harvest: 10, yield_estimate_kg: 4.5, area_m2: 5 },
];

export const mockNutrients: T.ZoneNutrients[] = [
  { zone_id: "zone_a", ph: 6.2, ec_ms_cm: 1.8, nitrogen_ppm: 180, phosphorus_ppm: 45, potassium_ppm: 210, calcium_ppm: 160, magnesium_ppm: 48, stock_remaining_pct: 72, days_of_stock: 85 },
  { zone_id: "zone_b", ph: 6.0, ec_ms_cm: 1.5, nitrogen_ppm: 165, phosphorus_ppm: 40, potassium_ppm: 195, calcium_ppm: 150, magnesium_ppm: 42, stock_remaining_pct: 68, days_of_stock: 78 },
  { zone_id: "zone_c", ph: 6.4, ec_ms_cm: 2.0, nitrogen_ppm: 195, phosphorus_ppm: 50, potassium_ppm: 225, calcium_ppm: 170, magnesium_ppm: 52, stock_remaining_pct: 65, days_of_stock: 72 },
];

export const mockCrewMembers: T.CrewMember[] = [
  { name: "CDR. CHEN", alive: true, status: "nominal", health_pct: 94, hydration_pct: 88, radiation_msv: 42 },
  { name: "DR. OKAFOR", alive: true, status: "nominal", health_pct: 91, hydration_pct: 92, radiation_msv: 38 },
  { name: "ENG. VASQUEZ", alive: true, status: "stressed", health_pct: 78, hydration_pct: 76, radiation_msv: 45 },
  { name: "SCI. LINDQVIST", alive: true, status: "nominal", health_pct: 88, hydration_pct: 85, radiation_msv: 40 },
];

export const mockCrewNutrition: T.CrewNutrition = {
  daily_calories_consumed: 2840,
  daily_calories_target: 3000,
  daily_protein_consumed_g: 85,
  daily_protein_target_g: 100,
  greenhouse_food_pct: 62,
  stored_food_pct: 38,
  days_of_food_remaining: 180,
  food_inventory: { potato: 120, lettuce: 24, soybean: 45, radish: 18, herbs: 8 },
};

export const mockCrewHealth: T.CrewHealth = {
  overall_health_pct: 88,
  hydration_pct: 85,
  radiation_cumulative_msv: 165,
  co2_impact: 0.12,
  starvation_level: 0.05,
  illness: null,
};

export const mockEvents: T.EventLogEntry[] = [
  { sol: 247, type: "harvest", severity: "info", zone: "zone_c", message: "SOY HARV" },
  { sol: 247, type: "environment", severity: "warning", zone: "zone_a", message: "ZONE A TEMP" },
  { sol: 247, type: "water", severity: "critical", zone: null, message: "WTR REC" },
  { sol: 247, type: "lighting", severity: "info", zone: "zone_b", message: "LITE D" },
  { sol: 247, type: "protocol", severity: "info", zone: null, message: "PROT." },
];

export const mockScore: T.ScoreCurrent = {
  survival: 92,
  nutrition: 85,
  resource_efficiency: 78,
  crisis_management: 88,
  overall_score: 86,
};
