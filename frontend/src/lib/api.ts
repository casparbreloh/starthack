/**
 * Adapter functions that normalise the simulation's raw WebSocket snapshot
 * shapes into the types the UI components expect.
 */

import type * as T from "@/types/game"

// ─── Raw simulation snapshot shapes (mirrors snapshots.py) ──────────────────

interface RawWeather {
  min_temp_c: number
  max_temp_c: number
  pressure_pa: number
  solar_irradiance_wm2: number
  dust_opacity: number
  season: string
}

interface RawEnergyStatus {
  solar_generation_wh: number
  battery_pct: number
  total_consumption_wh: number
  breakdown: {
    heating_wh: number
    lighting_wh: number
    water_recycling_wh: number
    nutrient_pumps_wh: number
  }
  surplus_wh: number
  deficit: boolean
}

interface RawZoneEnv {
  zone_id: string
  temp_c: number
  humidity_pct: number
  co2_ppm: number
  par_umol_m2s: number
  photoperiod_hours: number
}

interface RawGreenhouseEnv {
  zones: RawZoneEnv[]
}

interface RawWaterStatus {
  reservoir_liters: number
  reservoir_capacity_liters: number
  recycling_efficiency_pct: number
  daily_crew_consumption_liters: number
  daily_crop_consumption_liters: number
  daily_recycled_liters: number
  days_until_critical: number
  filter_health_pct: number
}

interface RawStressIndicator {
  type: string
  severity: number
}

interface RawCropBatch {
  crop_id: string
  type: string
  zone_id: string
  current_sol: number
  expected_harvest_sol: number
  growth_pct: number
  health: number
  stress_indicators: RawStressIndicator[]
  area_m2: number
  estimated_yield_kg: number
}

interface RawCropsStatus {
  crops: RawCropBatch[]
}

interface RawZoneNutrients {
  zone_id: string
  solution_ph: number
  solution_ec_ms_cm: number
  nitrogen_ppm: number
  phosphorus_ppm: number
  potassium_ppm: number
  calcium_ppm: number
  magnesium_ppm: number
}

interface RawNutrientsStatus {
  zones: RawZoneNutrients[]
  nutrient_stock_remaining_pct: number
  days_of_stock_remaining: number
}

interface RawCrewMember {
  name: string
  alive: boolean
  status: string
  health_pct: number
  hydration_pct: number
  cumulative_radiation_msv: number
}

interface RawCrewMembers {
  members: RawCrewMember[]
}

interface RawCrewNutrition {
  today: {
    calories_consumed_kcal: number
    calories_target_kcal: number
    protein_consumed_g: number
    protein_target_g: number
    from_greenhouse_pct: number
    from_stored_food_pct: number
  }
  food_inventory: Record<string, { kg_remaining: number }>
  days_of_food_remaining: number
}

interface RawCrewHealth {
  overall_health_pct: number
  hydration: { hydration_pct: number }
  radiation: { cumulative_msv: number }
  co2: { health_penalty_pct: number }
  starvation: { health_penalty_pct: number }
  illness: { active: boolean; sick_member_name: string | null }
}

interface RawCrisis {
  type: string
  severity: string
  current_value: number
  threshold: number
  resolved: boolean
}

interface RawActiveCrises {
  crises: RawCrisis[]
}

interface RawScoreCurrent {
  scores: {
    survival: number
    nutrition: number
    resource_efficiency: number
    crisis_management: number
    overall_score: number
  }
}

interface RawEvent {
  sol: number
  type: string
  severity: string
  zone: string | null
  message: string
}

// ─── Adapter functions ──────────────────────────────────────────────────────

export function adaptWeather(r: unknown): T.WeatherCurrent {
  const w = r as RawWeather
  return {
    temp_min_c: w.min_temp_c,
    temp_max_c: w.max_temp_c,
    pressure_mbar: w.pressure_pa / 100,
    solar_irradiance_w_m2: w.solar_irradiance_wm2,
    dust_opacity: w.dust_opacity,
    season: w.season,
  }
}

export function adaptEnergy(r: unknown): T.EnergyStatus {
  const e = r as RawEnergyStatus
  return {
    solar_generation_kw: e.solar_generation_wh / 1000,
    battery_pct: e.battery_pct,
    consumption: {
      heating_kw: e.breakdown.heating_wh / 1000,
      lighting_kw: e.breakdown.lighting_wh / 1000,
      water_kw: e.breakdown.water_recycling_wh / 1000,
      nutrients_kw: e.breakdown.nutrient_pumps_wh / 1000,
    },
    surplus_deficit_kw: e.deficit
      ? -Math.abs(e.total_consumption_wh - e.solar_generation_wh) / 1000
      : e.surplus_wh / 1000,
  }
}

export function adaptGreenhouseEnv(r: unknown): T.ZoneEnvironment[] {
  const g = r as RawGreenhouseEnv
  return g.zones.map((z) => ({
    zone_id: z.zone_id,
    temp_c: z.temp_c,
    humidity_pct: z.humidity_pct,
    co2_ppm: z.co2_ppm,
    par_light_umol: z.par_umol_m2s,
    photoperiod_hours: z.photoperiod_hours,
  }))
}

export function adaptWater(r: unknown): T.WaterStatus {
  const w = r as RawWaterStatus
  return {
    reservoir_level_pct: (w.reservoir_liters / w.reservoir_capacity_liters) * 100,
    recycling_efficiency_pct: w.recycling_efficiency_pct,
    filter_health_pct: w.filter_health_pct,
    days_until_critical: w.days_until_critical,
    daily_consumption_l: w.daily_crew_consumption_liters + w.daily_crop_consumption_liters,
    daily_recycled_l: w.daily_recycled_liters,
  }
}

export function adaptCrops(r: unknown): T.CropBatch[] {
  const c = r as RawCropsStatus
  return c.crops.map((crop) => {
    const stressMap: Record<string, number> = {}
    for (const s of crop.stress_indicators) {
      stressMap[s.type] = s.severity
    }
    return {
      crop_id: crop.crop_id,
      crop_type: crop.type,
      zone_id: crop.zone_id,
      growth_pct: crop.growth_pct,
      health_pct: crop.health * 100,
      stress_water: stressMap["water"] ?? 0,
      stress_nutrient: stressMap["nutrient"] ?? 0,
      stress_light: stressMap["light"] ?? 0,
      stress_temp: stressMap["temperature"] ?? stressMap["temp"] ?? 0,
      days_to_harvest: Math.max(0, crop.expected_harvest_sol - crop.current_sol),
      yield_estimate_kg: crop.estimated_yield_kg,
      area_m2: crop.area_m2,
    }
  })
}

export function adaptNutrients(r: unknown): T.ZoneNutrients[] {
  const n = r as RawNutrientsStatus
  return n.zones.map((z) => ({
    zone_id: z.zone_id,
    ph: z.solution_ph,
    ec_ms_cm: z.solution_ec_ms_cm,
    nitrogen_ppm: z.nitrogen_ppm,
    phosphorus_ppm: z.phosphorus_ppm,
    potassium_ppm: z.potassium_ppm,
    calcium_ppm: z.calcium_ppm,
    magnesium_ppm: z.magnesium_ppm,
    stock_remaining_pct: n.nutrient_stock_remaining_pct,
    days_of_stock: n.days_of_stock_remaining,
  }))
}

export function adaptCrewMembers(r: unknown): T.CrewMember[] {
  const c = r as RawCrewMembers
  return c.members.map((m) => ({
    name: m.name,
    alive: m.alive,
    status: m.status,
    health_pct: m.health_pct,
    hydration_pct: m.hydration_pct,
    radiation_msv: m.cumulative_radiation_msv,
  }))
}

export function adaptCrewNutrition(r: unknown): T.CrewNutrition {
  const c = r as RawCrewNutrition
  const foodInventory: Record<string, number> = {}
  for (const [key, item] of Object.entries(c.food_inventory)) {
    foodInventory[key] = item.kg_remaining
  }
  return {
    daily_calories_consumed: c.today.calories_consumed_kcal,
    daily_calories_target: c.today.calories_target_kcal,
    daily_protein_consumed_g: c.today.protein_consumed_g,
    daily_protein_target_g: c.today.protein_target_g,
    greenhouse_food_pct: c.today.from_greenhouse_pct,
    stored_food_pct: c.today.from_stored_food_pct,
    days_of_food_remaining: c.days_of_food_remaining,
    food_inventory: foodInventory,
  }
}

export function adaptCrewHealth(r: unknown): T.CrewHealth {
  const h = r as RawCrewHealth
  return {
    overall_health_pct: h.overall_health_pct,
    hydration_pct: h.hydration.hydration_pct,
    radiation_cumulative_msv: h.radiation.cumulative_msv,
    co2_impact: h.co2.health_penalty_pct,
    starvation_level: h.starvation.health_penalty_pct,
    illness: h.illness.active ? (h.illness.sick_member_name ?? "active") : null,
  }
}

export function adaptCrises(r: unknown): T.ActiveCrisis[] {
  const c = r as RawActiveCrises
  return c.crises
    .filter((crisis) => !crisis.resolved)
    .map((crisis) => ({
      type: crisis.type,
      severity: crisis.severity,
      threshold_breach: `${crisis.current_value.toFixed(1)} / ${crisis.threshold.toFixed(1)}`,
      resolution_status: "ongoing",
    }))
}

export function adaptScore(r: unknown): T.ScoreCurrent {
  const s = r as RawScoreCurrent
  return {
    survival: s.scores.survival,
    nutrition: s.scores.nutrition,
    resource_efficiency: s.scores.resource_efficiency,
    crisis_management: s.scores.crisis_management,
    overall_score: s.scores.overall_score,
  }
}

export function adaptEvents(r: unknown): T.EventLogEntry[] {
  const events = r as RawEvent[]
  return events.map((e) => ({
    sol: e.sol,
    type: e.type,
    severity: e.severity.toLowerCase() as T.EventLogEntry["severity"],
    zone: e.zone,
    message: e.message,
  }))
}
