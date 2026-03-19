import { useState, useEffect, useCallback, useRef } from "react"

// ── WebSocket message types ──────────────────────────────────────────────────

/** Raw tick payload from the simulation — field names match Python snapshot builder. */
export type TickPayload = Record<string, unknown>
import type { CreateSessionRequest } from "../types/simulation"

type WsIncoming =
  | { type: "tick"; payload: TickPayload }
  | { type: "registered"; payload: { role: string } }
  | {
      type: "session_created"
      session_id: string
      payload: { session_id: string; config: unknown }
    }
  | {
      type: "mission_end"
      payload: {
        mission_phase: string
        final_sol: number
        snapshot: TickPayload
      }
    }
  | {
      type: "session_joined"
      session_id: string
      payload: { session_id: string }
    }
  | { type: "paused"; session_id: string; payload: Record<string, never> }
  | { type: "resumed"; session_id: string; payload: Record<string, never> }
  | {
      type: "crisis_injected"
      session_id: string
      payload: { scenario: string; sol: number }
    }
  | {
      type: "tick_delay_set"
      session_id: string
      payload: { tick_delay_ms: number }
    }
  | { type: "error"; payload: { message: string } }

interface WsOutgoing {
  type: string
  session_id?: string
  payload?: Record<string, unknown>
}

// ── Session config for create_session ────────────────────────────────────────

export type CreateSessionConfig = CreateSessionRequest

// ── Hook return type ─────────────────────────────────────────────────────────

export interface WebSocketState {
  connected: boolean
  sessionId: string | null
  lastState: TickPayload | null
  lastEvents: unknown[]
  injectCrisis: (scenario: string, params?: Record<string, unknown>) => void
  setTickDelay: (ms: number) => void
  pause: () => void
  resume: () => void
  createSession: (config?: CreateSessionConfig) => void
}

// ── Constants ────────────────────────────────────────────────────────────────

const MAX_RECONNECT_RETRIES = 5
const BASE_RECONNECT_DELAY_MS = 1000

function buildWsUrl(): string {
  const envUrl = import.meta.env.VITE_SIM_WS_URL as string | undefined
  if (envUrl) return envUrl
  const wsProtocol = window.location.protocol === "https:" ? "wss:" : "ws:"
  return `${wsProtocol}//${window.location.host}/ws`
}

// ── Hook ─────────────────────────────────────────────────────────────────────

export function useWebSocket(): WebSocketState {
  const [connected, setConnected] = useState(false)
  const [sessionId, setSessionId] = useState<string | null>(null)
  const [lastState, setLastState] = useState<TickPayload | null>(null)
  const [lastEvents, setLastEvents] = useState<unknown[]>([])

  const wsRef = useRef<WebSocket | null>(null)
  const retriesRef = useRef(0)
  const reconnectTimerRef = useRef<ReturnType<typeof setTimeout> | null>(null)
  const mountedRef = useRef(true)
  const sessionIdRef = useRef<string | null>(null)

  // Keep ref in sync with state for use in send callbacks
  useEffect(() => {
    sessionIdRef.current = sessionId
  }, [sessionId])

  const send = useCallback((msg: WsOutgoing) => {
    const ws = wsRef.current
    if (ws && ws.readyState === WebSocket.OPEN) {
      ws.send(JSON.stringify(msg))
    }
  }, [])

  const handleMessage = useCallback((event: MessageEvent<string>) => {
    let msg: WsIncoming
    try {
      msg = JSON.parse(event.data) as WsIncoming
    } catch {
      return
    }

    switch (msg.type) {
      case "tick":
        setLastState(msg.payload)
        setLastEvents((msg.payload.events as unknown[]) ?? [])
        break

      case "session_created":
        setSessionId(msg.session_id)
        break

      case "mission_end":
        setLastState(msg.payload.snapshot)
        break

      case "registered":
      case "session_joined":
      case "paused":
      case "resumed":
      case "crisis_injected":
      case "tick_delay_set":
      case "error":
        // Acknowledged; no state change needed
        break
    }
  }, [])

  const connect = useCallback(() => {
    if (!mountedRef.current) return

    const ws = new WebSocket(buildWsUrl())
    wsRef.current = ws

    ws.onopen = () => {
      setConnected(true)
      retriesRef.current = 0
      // Register as frontend
      ws.send(JSON.stringify({ type: "register", payload: { role: "frontend" } }))
      // Re-join existing session or auto-create a new one
      if (sessionIdRef.current) {
        ws.send(
          JSON.stringify({
            type: "join_session",
            payload: { session_id: sessionIdRef.current },
          }),
        )
      } else {
        ws.send(
          JSON.stringify({
            type: "create_session",
            payload: { tick_delay_ms: 100 },
          }),
        )
      }
    }

    ws.onmessage = handleMessage

    ws.onclose = () => {
      setConnected(false)
      wsRef.current = null

      if (!mountedRef.current) return

      // Exponential backoff reconnect
      if (retriesRef.current < MAX_RECONNECT_RETRIES) {
        const delay = BASE_RECONNECT_DELAY_MS * Math.pow(2, retriesRef.current)
        retriesRef.current += 1
        reconnectTimerRef.current = setTimeout(connect, delay)
      }
    }

    ws.onerror = () => {
      // onclose will fire after onerror, handling reconnect there
    }
  }, [handleMessage])

  // Connect on mount, clean up on unmount
  useEffect(() => {
    mountedRef.current = true
    connect()

    return () => {
      mountedRef.current = false
      if (reconnectTimerRef.current !== null) {
        clearTimeout(reconnectTimerRef.current)
        reconnectTimerRef.current = null
      }
      if (wsRef.current) {
        wsRef.current.onclose = null
        wsRef.current.close()
        wsRef.current = null
      }
    }
  }, [connect])

  // ── Control methods ──────────────────────────────────────────────────────

  const injectCrisis = useCallback(
    (scenario: string, params?: Record<string, unknown>) => {
      send({
        type: "inject_crisis",
        session_id: sessionIdRef.current ?? undefined,
        payload: { scenario, ...params },
      })
    },
    [send],
  )

  const setTickDelay = useCallback(
    (ms: number) => {
      send({
        type: "set_tick_delay",
        session_id: sessionIdRef.current ?? undefined,
        payload: { tick_delay_ms: ms },
      })
    },
    [send],
  )

  const pause = useCallback(() => {
    send({
      type: "pause",
      session_id: sessionIdRef.current ?? undefined,
    })
  }, [send])

  const resume = useCallback(() => {
    send({
      type: "resume",
      session_id: sessionIdRef.current ?? undefined,
    })
  }, [send])

  const createSession = useCallback(
    (config?: CreateSessionConfig) => {
      send({
        type: "create_session",
        payload: (config as Record<string, unknown>) ?? {},
      })
    },
    [send],
  )

  return {
    connected,
    sessionId,
    lastState,
    lastEvents,
    injectCrisis,
    setTickDelay,
    pause,
    resume,
    createSession,
  }
}
