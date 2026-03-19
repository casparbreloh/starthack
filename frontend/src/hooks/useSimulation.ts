import { useCallback, useMemo } from "react"

import type {
  SimulationData,
  SimStatus,
  WeatherCurrent,
  EnergyStatus,
  GreenhouseEnvironment,
  WaterStatus,
  CropsStatus,
  NutrientsStatus,
  CrewNutrition,
  CrewHealth,
  CrewMembers,
  ActiveCrises,
  EventsLog,
  ScoreData,
} from "../types/simulation"
import { useWebSocketControls } from "./useGameData"
import type { WebSocketState, CreateSessionConfig } from "./useWebSocket"

export interface SimulationControls extends SimulationData {
  running: boolean
  toggleRunning: () => void
  reset: (config?: Partial<CreateSessionConfig>) => void
  ws: WebSocketState
}

export function useSimulation(): SimulationControls {
  const ws = useWebSocketControls()
  const running = !ws.isPaused

  const toggleRunning = useCallback(() => {
    if (running) {
      ws.pause()
    } else {
      ws.resume()
    }
  }, [ws, running])

  const reset = useCallback(
    (config?: Partial<CreateSessionConfig>) => {
      ws.reset(config)
    },
    [ws],
  )

  const data: SimulationData = useMemo(() => {
    const s = ws.lastState
    if (!s) {
      return {
        status: null,
        weather: null,
        energy: null,
        greenhouse: null,
        water: null,
        crops: null,
        nutrients: null,
        crew: null,
        crewHealth: null,
        crewMembers: null,
        crises: null,
        events: null,
        score: null,
        loading: true,
        error: null,
      }
    }

    return {
      status: (s.sim_status as SimStatus) ?? null,
      weather: (s.weather_current as WeatherCurrent) ?? null,
      energy: (s.energy_status as EnergyStatus) ?? null,
      greenhouse: (s.greenhouse_environment as GreenhouseEnvironment) ?? null,
      water: (s.water_status as WaterStatus) ?? null,
      crops: (s.crops_status as CropsStatus) ?? null,
      nutrients: (s.nutrients_status as NutrientsStatus) ?? null,
      crew: (s.crew_nutrition as CrewNutrition) ?? null,
      crewHealth: (s.crew_health as CrewHealth) ?? null,
      crewMembers: (s.crew_members as CrewMembers) ?? null,
      crises: (s.active_crises as ActiveCrises) ?? null,
      events: s.events ? ({ events: s.events } as EventsLog) : null,
      score: (s.score_current as ScoreData) ?? null,
      loading: false,
      error: null,
    }
  }, [ws.lastState])

  return { ...data, running, toggleRunning, reset, ws }
}
