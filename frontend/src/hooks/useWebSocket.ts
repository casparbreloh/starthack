import { useCallback, useEffect, useRef, useState } from "react"

import type { CreateSessionRequest } from "../types/simulation"

// ── WebSocket message types ──────────────────────────────────────────────────

/** Raw tick payload from the simulation — field names match Python snapshot builder. */
export type TickPayload = Record<string, unknown>

type WsIncoming =
  | { type: "tick"; payload: TickPayload }
  | { type: "registered"; payload: { role: string } }
  | {
      type: "session_created"
      session_id: string
      payload: { session_id: string; paused?: boolean; config: unknown }
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
  | {
      type: "error"
      payload: {
        message: string
        code?: string
        session_id?: string
      }
    }

interface WsOutgoing {
  type: string
  session_id?: string
  payload?: Record<string, unknown>
}

// ── Session config for create_session ────────────────────────────────────────

export type CreateSessionConfig = CreateSessionRequest

// ── Demo mode defaults ───────────────────────────────────────────────────────

const DEMO_DEFAULTS: Partial<CreateSessionConfig> = {
  tick_delay_ms: 1000,
  autonomous_events_enabled: false,
}

// ── Hook return type ─────────────────────────────────────────────────────────

export interface WebSocketState {
  connected: boolean
  sessionId: string | null
  isPaused: boolean
  lastState: TickPayload | null
  lastEvents: unknown[]
  stateHistory: TickPayload[]
  error: string | null
  injectCrisis: (scenario: string, params?: Record<string, unknown>) => void
  setTickDelay: (ms: number) => void
  pause: () => void
  resume: () => void
  reset: (config?: Partial<CreateSessionConfig>) => void
  createSession: (config?: CreateSessionConfig) => void
}

export interface UseWebSocketOptions {
  url?: string | null
  bootstrapSessionId?: string | null
}

// ── Constants ────────────────────────────────────────────────────────────────

const MAX_RECONNECT_RETRIES = 5
const BASE_RECONNECT_DELAY_MS = 1000
const SESSION_STORAGE_KEY = "oasis_session_id"

// sessionStorage may throw DOMException in restricted contexts (e.g. Amplify, iframes)
function safeGetSession(): string | null {
  try {
    return sessionStorage.getItem(SESSION_STORAGE_KEY)
  } catch {
    return null
  }
}

function safeSetSession(id: string): void {
  try {
    sessionStorage.setItem(SESSION_STORAGE_KEY, id)
  } catch {
    // Storage blocked — session won't survive refresh, but app still works
  }
}

function safeClearSession(): void {
  try {
    sessionStorage.removeItem(SESSION_STORAGE_KEY)
  } catch {
    // Storage blocked — nothing to clear
  }
}

function buildWsUrl(): string {
  const envUrl = import.meta.env.VITE_SIM_WS_URL as string | undefined
  if (envUrl) return envUrl
  const wsProtocol = window.location.protocol === "https:" ? "wss:" : "ws:"
  return `${wsProtocol}//${window.location.host}/ws`
}

// ── Hook ─────────────────────────────────────────────────────────────────────

/**
 * @param options.url  Optional WebSocket URL override. When provided, the hook
 *                     connects to this URL instead of the default `buildWsUrl()`.
 *                     Pass `null` to delay connection until a URL is available.
 * @param options.bootstrapSessionId  When provided, the hook joins this
 *                                    pre-created session instead of creating one.
 */
export function useWebSocket(options?: UseWebSocketOptions | null): WebSocketState {
  const [connected, setConnected] = useState(false)
  const [sessionId, setSessionId] = useState<string | null>(null)
  const [isPaused, setIsPaused] = useState(true)
  const [lastState, setLastState] = useState<TickPayload | null>(null)
  const [lastEvents, setLastEvents] = useState<unknown[]>([])
  const [stateHistory, setStateHistory] = useState<TickPayload[]>([])
  const [error, setError] = useState<string | null>(null)

  const wsRef = useRef<WebSocket | null>(null)
  const retriesRef = useRef(0)
  const reconnectTimerRef = useRef<ReturnType<typeof setTimeout> | null>(null)
  const mountedRef = useRef(true)
  const sessionIdRef = useRef<string | null>(null)
  const bootstrapSessionIdRef = useRef<string | null>(options?.bootstrapSessionId ?? null)
  const lastErrorRef = useRef<string | null>(null)

  // Keep refs in sync with state for use in callbacks
  useEffect(() => {
    sessionIdRef.current = sessionId
  }, [sessionId])

  useEffect(() => {
    bootstrapSessionIdRef.current = options?.bootstrapSessionId ?? null
  }, [options?.bootstrapSessionId])

  const send = useCallback((msg: WsOutgoing) => {
    const ws = wsRef.current
    if (ws && ws.readyState === WebSocket.OPEN) {
      ws.send(JSON.stringify(msg))
    }
  }, [])

  // Store handleMessage in a ref so `connect` doesn't depend on it.
  // This prevents React strict mode double-mount from recreating the WS.
  const handleMessageRef = useRef<(event: MessageEvent<string>) => void>(() => {})

  // Track whether we're waiting for a join_session response so we can
  // fall back to create_session if the join fails (session was destroyed).
  const pendingJoinRef = useRef(false)

  useEffect(() => {
    handleMessageRef.current = (event: MessageEvent<string>) => {
      let msg: WsIncoming
      try {
        msg = JSON.parse(event.data) as WsIncoming
      } catch {
        return
      }

      switch (msg.type) {
        case "tick": {
          setLastState(msg.payload)
          setLastEvents((msg.payload.events as unknown[]) ?? [])
          setStateHistory((prev) => {
            const next = prev.length >= 500 ? prev.slice(1) : prev
            return [...next, msg.payload]
          })
          const simStatus = msg.payload.sim_status as { paused?: boolean } | undefined
          if (simStatus && typeof simStatus.paused === "boolean") {
            setIsPaused(simStatus.paused)
          }
          break
        }

        case "session_created":
          setSessionId(msg.session_id)
          safeSetSession(msg.session_id)
          setIsPaused("paused" in msg.payload && Boolean(msg.payload.paused))
          setError(null)
          break

        case "session_joined":
          setSessionId(msg.session_id)
          safeSetSession(msg.session_id)
          pendingJoinRef.current = false
          setError(null)
          break

        case "mission_end":
          setLastState(msg.payload.snapshot)
          safeClearSession()
          break

        case "paused":
          setIsPaused(true)
          break

        case "resumed":
          setIsPaused(false)
          break

        case "error": {
          lastErrorRef.current = msg.payload.message

          if (pendingJoinRef.current && bootstrapSessionIdRef.current === null) {
            pendingJoinRef.current = false
            safeClearSession()
            const ws = wsRef.current
            if (ws && ws.readyState === WebSocket.OPEN) {
              ws.send(
                JSON.stringify({
                  type: "create_session",
                  payload: { ...DEMO_DEFAULTS, paused: true },
                }),
              )
            }
            break
          }

          pendingJoinRef.current = false
          if (bootstrapSessionIdRef.current !== null) {
            const ws = wsRef.current
            if (ws && ws.readyState === WebSocket.OPEN) {
              ws.close()
            }
          }
          break
        }

        case "registered":
        case "crisis_injected":
        case "tick_delay_set":
          break
      }
    }
  })

  const explicitUrl = options?.url
  const effectiveUrl = explicitUrl === null ? null : (explicitUrl ?? buildWsUrl())

  const connect = useCallback(() => {
    if (!mountedRef.current) return
    if (effectiveUrl === null) return

    let url = effectiveUrl
    if (window.location.protocol === "https:" && url.startsWith("ws://")) {
      url = "wss://" + url.slice(5)
    }

    let ws: WebSocket
    try {
      ws = new WebSocket(url)
    } catch {
      console.error("[WebSocket] Failed to connect — insecure context or invalid URL:", url)
      setError("Failed to initialize the simulation connection.")
      return
    }
    wsRef.current = ws

    ws.onopen = () => {
      setConnected(true)
      setError(null)
      lastErrorRef.current = null
      retriesRef.current = 0
      ws.send(JSON.stringify({ type: "register", payload: { role: "frontend" } }))

      const bootstrapSessionId = bootstrapSessionIdRef.current
      if (bootstrapSessionId) {
        pendingJoinRef.current = true
        ws.send(
          JSON.stringify({
            type: "join_session",
            payload: { session_id: bootstrapSessionId },
          }),
        )
        return
      }

      const existingId = sessionIdRef.current || safeGetSession()
      if (existingId) {
        pendingJoinRef.current = true
        ws.send(
          JSON.stringify({
            type: "join_session",
            payload: { session_id: existingId },
          }),
        )
      } else {
        ws.send(
          JSON.stringify({
            type: "create_session",
            payload: { ...DEMO_DEFAULTS, paused: true },
          }),
        )
      }
    }

    ws.onmessage = (e) => handleMessageRef.current(e)

    ws.onclose = () => {
      setConnected(false)
      wsRef.current = null

      if (!mountedRef.current) return

      if (retriesRef.current < MAX_RECONNECT_RETRIES) {
        const delay = BASE_RECONNECT_DELAY_MS * Math.pow(2, retriesRef.current)
        retriesRef.current += 1
        reconnectTimerRef.current = setTimeout(connect, delay)
      } else {
        setError(lastErrorRef.current ?? "Unable to connect to the simulation.")
      }
    }

    ws.onerror = () => {
      // onclose will fire after onerror, handling reconnect there
    }
  }, [effectiveUrl])

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

  const reset = useCallback(
    (config?: Partial<CreateSessionConfig>) => {
      setLastEvents([])
      setLastState(null)
      setStateHistory([])
      setIsPaused(true)
      safeClearSession()
      send({
        type: "reset_session",
        session_id: sessionIdRef.current ?? undefined,
        payload: {
          ...DEMO_DEFAULTS,
          paused: true,
          ...config,
        } as Record<string, unknown>,
      })
    },
    [send],
  )

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
    isPaused,
    lastState,
    lastEvents,
    stateHistory,
    error,
    injectCrisis,
    setTickDelay,
    pause,
    resume,
    reset,
    createSession,
  }
}
