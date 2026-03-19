import { useState, useEffect, useCallback, useRef } from "react"

import { api } from "../api/client"
import type { SimulationData } from "../types/simulation"

/** Real-time milliseconds between ticks */
const TICK_INTERVAL_MS = 1000
/** Simulation sols advanced per tick */
const TICK_SOLS = 1

const empty: SimulationData = {
  status: null,
  weather: null,
  energy: null,
  greenhouse: null,
  water: null,
  crops: null,
  nutrients: null,
  crew: null,
  crises: null,
  score: null,
  loading: true,
  error: null,
}

export interface SimulationControls extends SimulationData {
  running: boolean
  toggleRunning: () => void
}

export function useSimulation(): SimulationControls {
  const [data, setData] = useState<SimulationData>(empty)
  const [running, setRunning] = useState(true)
  const tickingRef = useRef(false)

  const fetchAll = useCallback(async () => {
    try {
      const [status, weather, energy, greenhouse, water, crops, nutrients, crew, crises, score] =
        await Promise.allSettled([
          api.getStatus(),
          api.getWeather(),
          api.getEnergy(),
          api.getGreenhouse(),
          api.getWater(),
          api.getCrops(),
          api.getNutrients(),
          api.getCrew(),
          api.getCrises(),
          api.getScore(),
        ])

      const resolve = <T>(r: PromiseSettledResult<T>): T | null =>
        r.status === "fulfilled" ? r.value : null

      setData({
        status: resolve(status),
        weather: resolve(weather),
        energy: resolve(energy),
        greenhouse: resolve(greenhouse),
        water: resolve(water),
        crops: resolve(crops),
        nutrients: resolve(nutrients),
        crew: resolve(crew),
        crises: resolve(crises),
        score: resolve(score),
        loading: false,
        error: null,
      })
    } catch {
      setData((prev) => ({ ...prev, loading: false, error: "Simulation offline" }))
    }
  }, [])

  const tick = useCallback(async () => {
    if (tickingRef.current) return
    tickingRef.current = true
    try {
      await api.advance(TICK_SOLS)
      await fetchAll()
    } catch {
      setData((prev) => ({ ...prev, error: "Simulation offline" }))
    } finally {
      tickingRef.current = false
    }
  }, [fetchAll])

  // Initial fetch on mount (before first tick fires)
  useEffect(() => {
    void fetchAll()
  }, [fetchAll])

  // Tick loop — advance + refresh on interval
  useEffect(() => {
    if (!running) return
    const id = setInterval(() => void tick(), TICK_INTERVAL_MS)
    return () => clearInterval(id)
  }, [running, tick])

  const toggleRunning = useCallback(() => setRunning((r) => !r), [])

  return { ...data, running, toggleRunning }
}
