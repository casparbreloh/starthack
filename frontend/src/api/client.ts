import type {
  SimStatus,
  WeatherCurrent,
  EnergyStatus,
  GreenhouseEnvironment,
  WaterStatus,
  CropsStatus,
  NutrientsStatus,
  CrewNutrition,
  ActiveCrises,
  ScoreData,
} from "../types/simulation"

async function get<T>(path: string): Promise<T> {
  const res = await fetch(path)
  if (!res.ok) throw new Error(`${path} → ${res.status}`)
  return res.json() as Promise<T>
}

async function post<T>(path: string, body?: unknown): Promise<T> {
  const res = await fetch(path, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: body !== undefined ? JSON.stringify(body) : undefined,
  })
  if (!res.ok) throw new Error(`${path} → ${res.status}`)
  return res.json() as Promise<T>
}

export const api = {
  advance: (sols: number) => post<{ new_sol: number }>("/sim/advance", { sols }),
  getStatus: () => get<SimStatus>("/sim/status"),
  getWeather: () => get<WeatherCurrent>("/weather/current"),
  getEnergy: () => get<EnergyStatus>("/energy/status"),
  getGreenhouse: () => get<GreenhouseEnvironment>("/greenhouse/environment"),
  getWater: () => get<WaterStatus>("/water/status"),
  getCrops: () => get<CropsStatus>("/crops/status"),
  getNutrients: () => get<NutrientsStatus>("/nutrients/status"),
  getCrew: () => get<CrewNutrition>("/crew/nutrition"),
  getCrises: () => get<ActiveCrises>("/events/active_crises"),
  getScore: () => get<ScoreData>("/score/current"),
}
