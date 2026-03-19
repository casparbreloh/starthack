import { createContext, createElement, useContext, useMemo, type ReactNode } from "react"

import {
  adaptWeather,
  adaptEnergy,
  adaptGreenhouseEnv,
  adaptWater,
  adaptCrops,
  adaptNutrients,
  adaptCrewMembers,
  adaptCrewNutrition,
  adaptCrewHealth,
  adaptCrises,
  adaptScore,
  adaptEvents,
} from "@/lib/api"
import type * as T from "@/types/game"

import { useWebSocket, type WebSocketState } from "./useWebSocket"

// ── Adapted game state ──────────────────────────────────────────────────────

interface GameState {
  sim: T.SimStatus | undefined
  weather: T.WeatherCurrent | undefined
  energy: T.EnergyStatus | undefined
  water: T.WaterStatus | undefined
  crops: T.CropBatch[] | undefined
  zones: T.ZoneEnvironment[] | undefined
  nutrients: T.ZoneNutrients[] | undefined
  crewMembers: T.CrewMember[] | undefined
  crewNutrition: T.CrewNutrition | undefined
  crewHealth: T.CrewHealth | undefined
  crises: T.ActiveCrisis[] | undefined
  score: T.ScoreCurrent | undefined
  events: T.EventLogEntry[] | undefined
  ws: WebSocketState
}

const GameContext = createContext<GameState | null>(null)

function useGame(): GameState {
  const ctx = useContext(GameContext)
  if (!ctx) throw new Error("GameDataProvider not found in component tree")
  return ctx
}

// ── Provider ────────────────────────────────────────────────────────────────

function adaptSnapshot(ws: WebSocketState): GameState {
  const s = ws.lastState
  if (!s) {
    return {
      sim: undefined,
      weather: undefined,
      energy: undefined,
      water: undefined,
      crops: undefined,
      zones: undefined,
      nutrients: undefined,
      crewMembers: undefined,
      crewNutrition: undefined,
      crewHealth: undefined,
      crises: undefined,
      score: undefined,
      events: undefined,
      ws,
    }
  }

  return {
    sim: s.sim_status as T.SimStatus,
    weather: s.weather_current ? adaptWeather(s.weather_current) : undefined,
    energy: adaptEnergy(s.energy_status),
    water: adaptWater(s.water_status),
    crops: adaptCrops(s.crops_status),
    zones: adaptGreenhouseEnv(s.greenhouse_environment),
    nutrients: adaptNutrients(s.nutrients_status),
    crewMembers: s.crew_members ? adaptCrewMembers(s.crew_members) : undefined,
    crewNutrition: adaptCrewNutrition(s.crew_nutrition),
    crewHealth: s.crew_health ? adaptCrewHealth(s.crew_health) : undefined,
    crises: adaptCrises(s.active_crises),
    score: adaptScore(s.score_current),
    events: ws.lastEvents ? adaptEvents(ws.lastEvents) : undefined,
    ws,
  }
}

export function GameDataProvider({ children }: { children: ReactNode }) {
  const ws = useWebSocket()
  const state = useMemo(() => adaptSnapshot(ws), [ws])

  return createElement(GameContext.Provider, { value: state }, children)
}

// ── Individual hooks (same interface as the old react-query hooks) ───────────

export const useSimStatus = () => ({ data: useGame().sim })
export const useWeather = () => ({ data: useGame().weather })
export const useEnergy = () => ({ data: useGame().energy })
export const useWater = () => ({ data: useGame().water })
export const useCrops = () => ({ data: useGame().crops })
export const useGreenhouseEnv = () => ({ data: useGame().zones })
export const useNutrients = () => ({ data: useGame().nutrients })
export const useCrewMembers = () => ({ data: useGame().crewMembers })
export const useCrewNutrition = () => ({ data: useGame().crewNutrition })
export const useCrewHealth = () => ({ data: useGame().crewHealth })
export const useActiveCrises = () => ({ data: useGame().crises })
export const useScore = () => ({ data: useGame().score })
export const useEventLog = () => ({ data: useGame().events })
export const useWebSocketControls = () => useGame().ws
