import { useState, useCallback, useEffect } from "react"

import type { SimulationData, CrewMembers } from "../types/simulation"
import { useWebSocket } from "./useWebSocket"
import type { WebSocketState } from "./useWebSocket"

const empty: SimulationData = {
  status: null,
  weather: null,
  energy: null,
  greenhouse: null,
  water: null,
  crops: null,
  nutrients: null,
  crew: null,
  crewMembers: null,
  crises: null,
  score: null,
  loading: true,
  error: null,
}

export interface SimulationControls extends SimulationData {
  running: boolean
  toggleRunning: () => void
  ws: WebSocketState
}

/**
 * Map a sol_tick state snapshot from the WebSocket into the SimulationData shape.
 * The snapshot keys match the telemetry endpoint names.
 */
function mapSnapshotToData(
  state: NonNullable<WebSocketState["lastState"]>,
  prevCrewMembers: CrewMembers | null,
): SimulationData {
  return {
    status: state.sim_status,
    weather: state.weather_current,
    energy: state.energy_status,
    greenhouse: state.greenhouse_environment,
    water: state.water_status,
    crops: state.crops_status,
    nutrients: state.nutrients_status,
    crew: state.crew_nutrition,
    crewMembers: prevCrewMembers,
    crises: state.active_crises,
    score: state.score_current,
    loading: false,
    error: null,
  }
}

export function useSimulation(): SimulationControls {
  const [data, setData] = useState<SimulationData>(empty)
  const [running, setRunning] = useState(true)

  const ws = useWebSocket()

  // When WS receives a tick, map it to SimulationData
  useEffect(() => {
    if (ws.lastState) {
      setData((prev) => mapSnapshotToData(ws.lastState!, prev.crewMembers))
    }
  }, [ws.lastState])

  const toggleRunning = useCallback(() => {
    setRunning((prev) => {
      const next = !prev
      if (next) {
        ws.resume()
      } else {
        ws.pause()
      }
      return next
    })
  }, [ws])

  return { ...data, running, toggleRunning, ws }
}
