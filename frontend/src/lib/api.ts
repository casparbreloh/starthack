/**
 * API client for the Mars Greenhouse Simulation.
 *
 * The simulation runs on http://localhost:8080 (CORS enabled).
 * This file also contains adapter functions that normalise the
 * simulation's response shapes into the types the UI components
 * expect (field renames, unit conversions, flattening wrappers).
 */

import type * as T from "@/types/game";

const BASE_URL = "http://localhost:8080";

// ─── Low-level fetch helper ───────────────────────────────────────────────────

async function fetchApi<R>(path: string, options?: RequestInit): Promise<R> {
  const res = await fetch(`${BASE_URL}${path}`, {
    ...options,
    headers: { "Content-Type": "application/json", ...options?.headers },
  });
  if (!res.ok) throw new Error(`API ${path} failed: ${res.status}`);
  return res.json() as Promise<R>;
}

// ─── Raw simulation response shapes (mirrors responses.py) ────────────────────

interface RawWeather {
  sol: number;
  min_temp_c: number;
  max_temp_c: number;
  avg_temp_c: number;
  pressure_pa: number;
  solar_irradiance_wm2: number;
  dust_opacity: number;
  season: string;
  ls: number;
  sol_in_year: number;
  confidence?: number;
}

interface RawEnergyStatus {
  solar_generation_wh: number;
  battery_level_wh: number;
  battery_capacity_wh: number;
  battery_pct: number;
  total_consumption_wh: number;
  breakdown: {
    heating_wh: number;
    lighting_wh: number;
    water_recycling_wh: number;
    nutrient_pumps_wh: number;
    sensors_control_wh: number;
  };
  surplus_wh: number;
  deficit: boolean;
  allocation: {
    heating_pct: number;
    lighting_pct: number;
    water_recycling_pct: number;
    nutrient_pumps_pct: number;
    reserve_pct: number;
  };
}

interface RawZoneEnv {
  zone_id: string;
  temp_c: number;
  humidity_pct: number;
  co2_ppm: number;
  par_umol_m2s: number;
  light_on: boolean;
  photoperiod_hours: number;
  area_m2: number;
}

interface RawGreenhouseEnv {
  zones: RawZoneEnv[];
  total_area_m2: number;
  external_temp_c: number | null;
}

interface RawWaterStatus {
  reservoir_liters: number;
  reservoir_capacity_liters: number;
  recycling_efficiency_pct: number;
  daily_crew_consumption_liters: number;
  daily_crop_consumption_liters: number;
  daily_recycled_liters: number;
  daily_net_change_liters: number;
  days_until_critical: number;
  filter_health_pct: number;
  irrigation_settings: Record<string, number>;
}

interface RawStressIndicator {
  type: string;
  since_sol: number;
  severity: number;
}

interface RawCropBatch {
  crop_id: string;
  type: string;
  zone_id: string;
  planted_sol: number;
  current_sol: number;
  days_in_cycle: number;
  expected_harvest_sol: number;
  growth_pct: number;
  health: number;
  is_ready: boolean;
  stress_indicators: RawStressIndicator[];
  area_m2: number;
  soil_moisture_pct: number;
  estimated_yield_kg: number;
  estimated_calories_kcal: number;
}

interface RawCropsStatus {
  crops: RawCropBatch[];
  total_planted_area_m2: number;
  available_area_per_zone: Record<string, number>;
  seeds_remaining: Record<string, number>;
}

interface RawZoneNutrients {
  zone_id: string;
  solution_ph: number;
  solution_ec_ms_cm: number;
  solution_temp_c: number;
  dissolved_o2_ppm: number;
  nitrogen_ppm: number;
  phosphorus_ppm: number;
  potassium_ppm: number;
  calcium_ppm: number;
  magnesium_ppm: number;
}

interface RawNutrientsStatus {
  zones: RawZoneNutrients[];
  nutrient_stock_remaining_pct: number;
  days_of_stock_remaining: number;
}

interface RawCrewMember {
  member_id: string;
  name: string;
  alive: boolean;
  status: string;
  health_pct: number;
  hydration_pct: number;
  cumulative_radiation_msv: number;
}

interface RawCrewMembers {
  current_sol: number;
  crew_size: number;
  members: RawCrewMember[];
}

interface RawCrewNutrition {
  current_sol: number;
  today: {
    calories_consumed_kcal: number;
    calories_target_kcal: number;
    protein_consumed_g: number;
    protein_target_g: number;
    from_greenhouse_pct: number;
    from_stored_food_pct: number;
  };
  stored_food: {
    remaining_kcal: number;
    remaining_days_at_current_rate: number;
    protein_remaining_g: number;
  };
  food_buffer: { fresh_harvest_kcal: number; days_of_buffer: number };
  cumulative: {
    avg_daily_kcal: number;
    avg_daily_protein_g: number;
    deficit_sols: number;
    surplus_sols: number;
  };
  crew_status: string;
  micronutrients: {
    sufficient_today: boolean;
    level: string;
    consecutive_deficit_sols: number;
    health_penalty_pct: number;
  };
  food_inventory: Record<
    string,
    {
      kg_remaining: number;
      kcal_remaining: number;
      protein_g_remaining: number;
      pct_remaining: number;
    }
  >;
  days_of_food_remaining: number;
  days_of_protein_remaining: number;
}

interface RawCrewHealth {
  current_sol: number;
  alive: boolean;
  cause_of_death: string | null;
  overall_health_pct: number;
  hydration: { hydration_pct: number; level: string };
  radiation: { cumulative_msv: number; warning_active: boolean; critical_active: boolean };
  temperature: { health_penalty_pct: number };
  co2: { health_penalty_pct: number };
  starvation: { level: string; health_penalty_pct: number };
  illness: { active: boolean; sick_member_name: string | null };
}

interface RawEvent {
  sol: number;
  type: string;
  category: string;
  message: string;
  severity: string;
  zone: string | null;
  data: Record<string, unknown> | null;
}

interface RawEventsLog {
  events: RawEvent[];
}

interface RawCrisis {
  id: string;
  type: string;
  started_sol: number;
  severity: string;
  message: string;
  current_value: number;
  threshold: number;
  resolved: boolean;
  resolved_sol: number | null;
}

interface RawActiveCrises {
  crises: RawCrisis[];
}

interface RawScoreCurrent {
  current_sol: number;
  scores: {
    survival: { score: number };
    nutrition: { score: number };
    resource_efficiency: { score: number };
    crisis_management: { score: number };
    overall_score: number;
  };
}

// ─── Adapter helpers ──────────────────────────────────────────────────────────

function adaptWeather(r: RawWeather): T.WeatherCurrent {
  return {
    temp_min_c: r.min_temp_c,
    temp_max_c: r.max_temp_c,
    pressure_mbar: r.pressure_pa / 100,
    solar_irradiance_w_m2: r.solar_irradiance_wm2,
    dust_opacity: r.dust_opacity,
    season: r.season,
  };
}

function adaptWeatherForecast(r: RawWeather & { confidence: number }): T.WeatherForecastDay {
  return {
    sol: r.sol,
    temp_min_c: r.min_temp_c,
    temp_max_c: r.max_temp_c,
    dust_opacity: r.dust_opacity,
    solar_irradiance_w_m2: r.solar_irradiance_wm2,
    confidence: r.confidence ?? 1,
  };
}

function adaptWeatherHistory(r: RawWeather): T.WeatherHistoryEntry {
  return {
    sol: r.sol,
    temp_min_c: r.min_temp_c,
    temp_max_c: r.max_temp_c,
    pressure_mbar: r.pressure_pa / 100,
    solar_irradiance_w_m2: r.solar_irradiance_wm2,
    dust_opacity: r.dust_opacity,
  };
}

function adaptEnergy(r: RawEnergyStatus): T.EnergyStatus {
  return {
    solar_generation_kw: r.solar_generation_wh / 1000,
    battery_pct: r.battery_pct,
    consumption: {
      heating_kw: r.breakdown.heating_wh / 1000,
      lighting_kw: r.breakdown.lighting_wh / 1000,
      water_kw: r.breakdown.water_recycling_wh / 1000,
      nutrients_kw: r.breakdown.nutrient_pumps_wh / 1000,
    },
    surplus_deficit_kw: r.deficit
      ? -Math.abs(r.total_consumption_wh - r.solar_generation_wh) / 1000
      : r.surplus_wh / 1000,
  };
}

function adaptGreenhouseEnv(r: RawGreenhouseEnv): T.ZoneEnvironment[] {
  return r.zones.map((z) => ({
    zone_id: z.zone_id,
    temp_c: z.temp_c,
    humidity_pct: z.humidity_pct,
    co2_ppm: z.co2_ppm,
    par_light_umol: z.par_umol_m2s,
    photoperiod_hours: z.photoperiod_hours,
  }));
}

function adaptWater(r: RawWaterStatus): T.WaterStatus {
  return {
    reservoir_level_pct: (r.reservoir_liters / r.reservoir_capacity_liters) * 100,
    recycling_efficiency_pct: r.recycling_efficiency_pct,
    filter_health_pct: r.filter_health_pct,
    days_until_critical: r.days_until_critical,
    daily_consumption_l: r.daily_crew_consumption_liters + r.daily_crop_consumption_liters,
    daily_recycled_l: r.daily_recycled_liters,
  };
}

function adaptCrops(r: RawCropsStatus): T.CropBatch[] {
  return r.crops.map((c) => {
    const stressMap: Record<string, number> = {};
    for (const s of c.stress_indicators) {
      stressMap[s.type] = s.severity;
    }
    return {
      crop_id: c.crop_id,
      crop_type: c.type,
      zone_id: c.zone_id,
      growth_pct: c.growth_pct,
      health_pct: c.health * 100,
      stress_water: stressMap["water"] ?? 0,
      stress_nutrient: stressMap["nutrient"] ?? 0,
      stress_light: stressMap["light"] ?? 0,
      stress_temp: stressMap["temperature"] ?? stressMap["temp"] ?? 0,
      days_to_harvest: Math.max(0, c.expected_harvest_sol - c.current_sol),
      yield_estimate_kg: c.estimated_yield_kg,
      area_m2: c.area_m2,
    };
  });
}

function adaptNutrients(r: RawNutrientsStatus): T.ZoneNutrients[] {
  return r.zones.map((z) => ({
    zone_id: z.zone_id,
    ph: z.solution_ph,
    ec_ms_cm: z.solution_ec_ms_cm,
    nitrogen_ppm: z.nitrogen_ppm,
    phosphorus_ppm: z.phosphorus_ppm,
    potassium_ppm: z.potassium_ppm,
    calcium_ppm: z.calcium_ppm,
    magnesium_ppm: z.magnesium_ppm,
    stock_remaining_pct: r.nutrient_stock_remaining_pct,
    days_of_stock: r.days_of_stock_remaining,
  }));
}

function adaptCrewMembers(r: RawCrewMembers): T.CrewMember[] {
  return r.members.map((m) => ({
    name: m.name,
    alive: m.alive,
    status: m.status,
    health_pct: m.health_pct,
    hydration_pct: m.hydration_pct,
    radiation_msv: m.cumulative_radiation_msv,
  }));
}

function adaptCrewHealth(r: RawCrewHealth): T.CrewHealth {
  return {
    overall_health_pct: r.overall_health_pct,
    hydration_pct: r.hydration.hydration_pct,
    radiation_cumulative_msv: r.radiation.cumulative_msv,
    co2_impact: r.co2.health_penalty_pct,
    starvation_level: r.starvation.health_penalty_pct,
    illness: r.illness.active ? (r.illness.sick_member_name ?? "active") : null,
  };
}

function adaptCrewNutrition(r: RawCrewNutrition): T.CrewNutrition {
  const foodInventory: Record<string, number> = {};
  for (const [key, item] of Object.entries(r.food_inventory)) {
    foodInventory[key] = item.kg_remaining;
  }
  return {
    daily_calories_consumed: r.today.calories_consumed_kcal,
    daily_calories_target: r.today.calories_target_kcal,
    daily_protein_consumed_g: r.today.protein_consumed_g,
    daily_protein_target_g: r.today.protein_target_g,
    greenhouse_food_pct: r.today.from_greenhouse_pct,
    stored_food_pct: r.today.from_stored_food_pct,
    days_of_food_remaining: r.days_of_food_remaining,
    food_inventory: foodInventory,
  };
}

function adaptEvents(r: RawEventsLog): T.EventLogEntry[] {
  return r.events.map((e) => ({
    sol: e.sol,
    type: e.type,
    severity: e.severity.toLowerCase() as T.EventLogEntry["severity"],
    zone: e.zone,
    message: e.message,
  }));
}

function adaptCrises(r: RawActiveCrises): T.ActiveCrisis[] {
  return r.crises
    .filter((c) => !c.resolved)
    .map((c) => ({
      type: c.type,
      severity: c.severity,
      threshold_breach: `${c.current_value.toFixed(1)} / ${c.threshold.toFixed(1)}`,
      resolution_status: "ongoing",
    }));
}

function adaptScore(r: RawScoreCurrent): T.ScoreCurrent {
  return {
    survival: r.scores.survival.score,
    nutrition: r.scores.nutrition.score,
    resource_efficiency: r.scores.resource_efficiency.score,
    crisis_management: r.scores.crisis_management.score,
    overall_score: r.scores.overall_score,
  };
}

// ─── Public API client ────────────────────────────────────────────────────────

export const api = {
  // Sim control
  getSimStatus: () => fetchApi<T.SimStatus>("/sim/status"),
  advanceSol: (sols = 1) =>
    fetchApi<T.SimStatus>("/sim/advance", {
      method: "POST",
      body: JSON.stringify({ sols }),
    }),
  resetSim: (difficulty = "normal") =>
    fetchApi<T.SimStatus>("/sim/reset", {
      method: "POST",
      body: JSON.stringify({ difficulty }),
    }),

  // Weather
  getWeather: () => fetchApi<RawWeather>("/weather/current").then(adaptWeather),
  getWeatherForecast: (horizon = 7) =>
    fetchApi<(RawWeather & { confidence: number })[]>(`/weather/forecast?horizon=${horizon}`).then((arr) =>
      arr.map(adaptWeatherForecast),
    ),
  getWeatherHistory: (lastNSols = 30) =>
    fetchApi<RawWeather[]>(`/weather/history?last_n_sols=${lastNSols}`).then((arr) =>
      arr.map(adaptWeatherHistory),
    ),

  // Energy
  getEnergy: () => fetchApi<RawEnergyStatus>("/energy/status").then(adaptEnergy),
  allocateEnergy: (allocation: Record<string, number>) =>
    fetchApi<void>("/energy/allocate", { method: "POST", body: JSON.stringify(allocation) }),

  // Greenhouse
  getGreenhouseEnv: () => fetchApi<RawGreenhouseEnv>("/greenhouse/environment").then(adaptGreenhouseEnv),
  setGreenhouseEnv: (data: Partial<T.ZoneEnvironment>) =>
    fetchApi<void>("/greenhouse/set_environment", { method: "POST", body: JSON.stringify(data) }),

  // Water
  getWater: () => fetchApi<RawWaterStatus>("/water/status").then(adaptWater),
  setIrrigation: (data: Record<string, number>) =>
    fetchApi<void>("/water/set_irrigation", { method: "POST", body: JSON.stringify(data) }),
  waterMaintenance: () => fetchApi<void>("/water/maintenance", { method: "POST" }),

  // Crops
  getCrops: () => fetchApi<RawCropsStatus>("/crops/status").then(adaptCrops),
  getCropCatalog: () => fetchApi<T.CropCatalogEntry[]>("/crops/catalog"),
  plantCrop: (data: { crop_type: string; zone_id: string; area_m2: number }) =>
    fetchApi<void>("/crops/plant", { method: "POST", body: JSON.stringify(data) }),
  harvestCrop: (cropId: string) =>
    fetchApi<void>("/crops/harvest", { method: "POST", body: JSON.stringify({ crop_id: cropId }) }),
  removeCrop: (cropId: string) =>
    fetchApi<void>("/crops/remove", { method: "POST", body: JSON.stringify({ crop_id: cropId }) }),

  // Nutrients
  getNutrients: () => fetchApi<RawNutrientsStatus>("/nutrients/status").then(adaptNutrients),
  adjustNutrients: (data: { zone_id: string; [key: string]: unknown }) =>
    fetchApi<void>("/nutrients/adjust", { method: "POST", body: JSON.stringify(data) }),

  // Crew
  getCrewHealth: () => fetchApi<RawCrewHealth>("/crew/health").then(adaptCrewHealth),
  getCrewMembers: () => fetchApi<RawCrewMembers>("/crew/members").then(adaptCrewMembers),
  getCrewNutrition: () => fetchApi<RawCrewNutrition>("/crew/nutrition").then(adaptCrewNutrition),

  // Events
  getEventLog: (sinceSol = 0) =>
    fetchApi<RawEventsLog>(`/events/log?since_sol=${sinceSol}`).then(adaptEvents),
  getActiveCrises: () => fetchApi<RawActiveCrises>("/events/active_crises").then(adaptCrises),

  // Score
  getScore: () => fetchApi<RawScoreCurrent>("/score/current").then(adaptScore),

  // Admin scenarios
  triggerDustStorm: () => fetchApi<void>("/admin/scenario/dust_storm", { method: "POST" }),
  triggerWaterLeak: () => fetchApi<void>("/admin/scenario/water_leak", { method: "POST" }),
  triggerHvacFailure: () => fetchApi<void>("/admin/scenario/hvac_failure", { method: "POST" }),
  triggerPathogen: (cropId: string) =>
    fetchApi<void>("/admin/scenario/pathogen", {
      method: "POST",
      body: JSON.stringify({ crop_id: cropId }),
    }),
  triggerEnergyDisruption: () =>
    fetchApi<void>("/admin/scenario/energy_disruption", { method: "POST" }),
};
