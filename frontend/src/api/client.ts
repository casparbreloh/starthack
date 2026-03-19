import type {
  SimStatus,
  WeatherCurrent,
  EnergyStatus,
  GreenhouseEnvironment,
  WaterStatus,
  CropsStatus,
  NutrientsStatus,
  CrewNutrition,
  CrewMembers,
  ActiveCrises,
  ScoreData,
  CreateSessionRequest,
  CreateSessionResponse,
  ListSessionsResponse,
} from "../types/simulation"

const BASE = "/simulation"

async function get<T>(path: string): Promise<T> {
  const res = await fetch(`${BASE}${path}`)
  if (!res.ok) throw new Error(`${path} → ${res.status}`)
  return res.json() as Promise<T>
}

async function post<T>(path: string, body?: unknown): Promise<T> {
  const res = await fetch(`${BASE}${path}`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: body !== undefined ? JSON.stringify(body) : undefined,
  })
  if (!res.ok) throw new Error(`${path} → ${res.status}`)
  return res.json() as Promise<T>
}

// ── API client ───────────────────────────────────────────────────────────────

export const api = {
  // Session management
  createSession: (config?: CreateSessionRequest) =>
    post<CreateSessionResponse>("/sessions", config ?? {}),
  listSessions: () => get<ListSessionsResponse>("/sessions"),

  // Telemetry (read-only)
  getStatus: () => get<SimStatus>("/sim/status"),
  getWeather: () => get<WeatherCurrent>("/weather/current"),
  getEnergy: () => get<EnergyStatus>("/energy/status"),
  getGreenhouse: () => get<GreenhouseEnvironment>("/greenhouse/environment"),
  getWater: () => get<WaterStatus>("/water/status"),
  getCrops: () => get<CropsStatus>("/crops/status"),
  getNutrients: () => get<NutrientsStatus>("/nutrients/status"),
  getCrew: () => get<CrewNutrition>("/crew/nutrition"),
  getCrewMembers: () => get<CrewMembers>("/crew/members"),
  getCrises: () => get<ActiveCrises>("/events/active_crises"),
  getScore: () => get<ScoreData>("/score/current"),
}
