export interface SimStatus {
  current_sol: number
  total_sols: number
  mission_phase: string
  sim_speed: number
  paused: boolean
}

export interface WeatherCurrent {
  sol: number
  min_temp_c: number
  max_temp_c: number
  pressure_pa: number
  min_ground_temp_c: number
  max_ground_temp_c: number
  solar_irradiance_wm2: number
  dust_opacity: number
  season: string
  ls: number
  sol_in_year: number
}

export interface EnergyBreakdown {
  heating_wh: number
  lighting_wh: number
  water_recycling_wh: number
  nutrient_pumps_wh: number
  sensors_control_wh: number
  other_wh: number
}

export interface EnergyStatus {
  solar_generation_wh: number
  battery_level_wh: number
  battery_capacity_wh: number
  battery_pct: number
  total_consumption_wh: number
  breakdown: EnergyBreakdown
  surplus_wh: number
  deficit: boolean
}

export interface GreenhouseZone {
  zone_id: string
  temp_c: number
  humidity_pct: number
  co2_ppm: number
  par_umol_m2s: number
  light_on: boolean
  photoperiod_hours: number
  area_m2: number
}

export interface GreenhouseEnvironment {
  zones: GreenhouseZone[]
  total_area_m2: number
  external_temp_c: number
}

export interface WaterStatus {
  reservoir_liters: number
  reservoir_capacity_liters: number
  recycling_efficiency_pct: number
  daily_crew_consumption_liters: number
  daily_crop_consumption_liters: number
  daily_recycled_liters: number
  daily_net_change_liters: number
  days_until_critical: number
  filter_health_pct: number
}

export interface StressIndicator {
  type: string
  since_sol: number
  severity: number
}

export interface Crop {
  crop_id: string
  type: string
  zone_id: string
  planted_sol: number
  current_sol: number
  days_in_cycle: number
  expected_harvest_sol: number
  growth_pct: number
  health: number
  stress_indicators: StressIndicator[]
  area_m2: number
  estimated_yield_kg: number
  estimated_calories_kcal: number
}

export interface CropsStatus {
  crops: Crop[]
  available_area_m2: number
  total_planted_area_m2: number
}

export interface NutrientZone {
  zone_id: string
  solution_ph: number
  solution_ec_ms_cm: number
  solution_temp_c: number
  dissolved_o2_ppm: number
  nitrogen_ppm: number
  phosphorus_ppm: number
  potassium_ppm: number
  calcium_ppm: number
  magnesium_ppm: number
}

export interface NutrientsStatus {
  zones: NutrientZone[]
  nutrient_stock_remaining_pct: number
  days_of_stock_remaining: number
}

export interface TodayNutrition {
  calories_consumed_kcal: number
  calories_target_kcal: number
  protein_consumed_g: number
  protein_target_g: number
  from_greenhouse_pct: number
  from_stored_food_pct: number
}

export interface StoredFood {
  remaining_kcal: number
  remaining_days_at_current_rate: number
  protein_remaining_g: number
}

export interface FoodBuffer {
  fresh_harvest_stored_kg: number
  estimated_kcal: number
  days_of_buffer: number
}

export interface CumulativeNutrition {
  avg_daily_kcal: number
  avg_daily_protein_g: number
  deficit_days: number
  surplus_days: number
}

export interface CrewNutrition {
  current_sol: number
  today: TodayNutrition
  stored_food: StoredFood
  food_buffer: FoodBuffer
  cumulative: CumulativeNutrition
}

export interface Crisis {
  id: string
  type: string
  started_sol: number
  severity: string
  current_value?: number
  threshold?: number
  resolved: boolean
}

export interface ActiveCrises {
  crises: Crisis[]
}

export interface ScoreData {
  current_sol: number
  scores: {
    survival: { crew_alive: boolean; days_without_critical_deficit: number; score: number }
    nutrition: {
      avg_daily_kcal: number
      kcal_achievement_pct: number
      avg_daily_protein_g: number
      protein_achievement_pct: number
      micronutrient_diversity_score: number
      score: number
    }
    resource_efficiency: {
      water_efficiency_pct: number
      energy_efficiency_pct: number
      crop_waste_pct: number
      score: number
    }
    crisis_management: {
      crises_encountered: number
      crises_resolved: number
      avg_resolution_sols: number
      preventive_actions_taken: number
      score: number
    }
    overall_score: number
  }
}

export interface SimulationData {
  status: SimStatus | null
  weather: WeatherCurrent | null
  energy: EnergyStatus | null
  greenhouse: GreenhouseEnvironment | null
  water: WaterStatus | null
  crops: CropsStatus | null
  nutrients: NutrientsStatus | null
  crew: CrewNutrition | null
  crises: ActiveCrises | null
  score: ScoreData | null
  loading: boolean
  error: string | null
}
