import type { components } from "../contracts/simulation"

type Schemas = components["schemas"]

// ── API response types (re-exported from generated contract) ──────────
export type SimStatus = Schemas["SimStatusResponse"]
export type WeatherCurrent = Schemas["WeatherResponse"]
export type EnergyBreakdown = Schemas["EnergyBreakdownResponse"]
export type EnergyStatus = Schemas["EnergyStatusResponse"]
export type GreenhouseZone = Schemas["ZoneEnvironmentResponse"]
export type GreenhouseEnvironment = Schemas["GreenhouseEnvironmentResponse"]
export type WaterStatus = Schemas["WaterStatusResponse"]
export type StressIndicator = Schemas["StressIndicatorResponse"]
export type Crop = Schemas["CropBatchResponse"]
export type CropsStatus = Schemas["CropsStatusResponse"]
export type NutrientZone = Schemas["ZoneNutrientsResponse"]
export type NutrientsStatus = Schemas["NutrientsStatusResponse"]
export type TodayNutrition = Schemas["CrewNutritionTodayResponse"]
export type StoredFood = Schemas["StoredFoodResponse"]
export type FoodBuffer = Schemas["FoodBufferResponse"]
export type CumulativeNutrition = Schemas["CumulativeNutritionResponse"]
export type FoodInventoryItem = Schemas["FoodInventoryItemResponse"]
export type CrewNutrition = Schemas["CrewNutritionResponse"]
export type CrewMember = Schemas["CrewMemberResponse"]
export type CrewMembers = Schemas["CrewMembersResponse"]
export type Crisis = Schemas["CrisisResponse"]
export type ActiveCrises = Schemas["ActiveCrisesResponse"]
export type ScoreData = Schemas["ScoreCurrentResponse"]
export type SimAdvanceResponse = Schemas["SimAdvanceResponse"]

// ── Frontend-only state (not an API response) ─────────────────────────
export interface SimulationData {
  status: SimStatus | null
  weather: WeatherCurrent | null
  energy: EnergyStatus | null
  greenhouse: GreenhouseEnvironment | null
  water: WaterStatus | null
  crops: CropsStatus | null
  nutrients: NutrientsStatus | null
  crew: CrewNutrition | null
  crewMembers: CrewMembers | null
  crises: ActiveCrises | null
  score: ScoreData | null
  loading: boolean
  error: string | null
}
