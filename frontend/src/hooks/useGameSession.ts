import { useCallback, useEffect, useRef, useState } from "react"

import * as orchestrator from "@/api/orchestrator"
import type { TrainingConfig, SessionStatus } from "@/types/orchestrator"

// ── Constants ────────────────────────────────────────────────────────────────

const POLL_INTERVAL_MS = 2_000
const MAX_POLL_ATTEMPTS = 90 // ~3 minutes at 2s intervals

// ── Types ────────────────────────────────────────────────────────────────────

export interface GameSessionState {
  /** WebSocket URL once the container is ready, `null` while starting */
  wsUrl: string | null
  /** Orchestrator session ID (available immediately after startSession) */
  sessionId: string | null
  /** Current session status from the orchestrator */
  status: SessionStatus | null
  /** True while the Fargate container is spinning up */
  isStarting: boolean
  /** Error message if session creation or polling failed */
  error: string | null
  /** Kick off a new orchestrated session */
  startSession: (config?: TrainingConfig) => void
}

// ── Orchestrator mode detection ──────────────────────────────────────────────

const ORCHESTRATOR_URL = import.meta.env.VITE_ORCHESTRATOR_URL as string | undefined

/** Returns true when the orchestrator is configured (deployed environment). */
export function isOrchestratorMode(): boolean {
  return Boolean(ORCHESTRATOR_URL)
}

// ── Hook ─────────────────────────────────────────────────────────────────────

/**
 * Manages session lifecycle via the Lambda orchestrator.
 *
 * 1. Calls `orchestrator.startSession` to spawn a Fargate container.
 * 2. Polls `orchestrator.getSession` until status is "running", `ws_ready`
 *    is true, and `ws_url` is available.
 * 3. Returns the `wsUrl` for `useWebSocket` to connect to.
 *
 * Only used when `VITE_ORCHESTRATOR_URL` is set — see `isOrchestratorMode`.
 */
export function useGameSession(): GameSessionState {
  const [wsUrl, setWsUrl] = useState<string | null>(null)
  const [sessionId, setSessionId] = useState<string | null>(null)
  const [status, setStatus] = useState<SessionStatus | null>(null)
  const [isStarting, setIsStarting] = useState(false)
  const [error, setError] = useState<string | null>(null)

  const pollTimerRef = useRef<ReturnType<typeof setTimeout> | null>(null)
  const pollCountRef = useRef(0)
  const mountedRef = useRef(true)

  // Cleanup on unmount
  useEffect(() => {
    mountedRef.current = true
    return () => {
      mountedRef.current = false
      if (pollTimerRef.current !== null) {
        clearTimeout(pollTimerRef.current)
        pollTimerRef.current = null
      }
    }
  }, [])

  const pollSession = useCallback((sid: string) => {
    if (!mountedRef.current) return

    pollCountRef.current += 1
    if (pollCountRef.current > MAX_POLL_ATTEMPTS) {
      setError("Session took too long to start. Please try again.")
      setIsStarting(false)
      return
    }

    orchestrator
      .getSession(sid)
      .then((detail) => {
        if (!mountedRef.current) return

        setStatus(detail.status)

        if (detail.status === "running" && detail.ws_ready && detail.ws_url) {
          setWsUrl(detail.ws_url)
          setIsStarting(false)
          return
        }

        if (detail.status === "failed") {
          setError("Session failed to start. Check infrastructure logs.")
          setIsStarting(false)
          return
        }

        if (detail.status === "completed" || detail.status === "stopped") {
          setError("Session ended before it became available.")
          setIsStarting(false)
          return
        }

        // Still starting — poll again
        pollTimerRef.current = setTimeout(() => pollSession(sid), POLL_INTERVAL_MS)
      })
      .catch((err: unknown) => {
        if (!mountedRef.current) return
        const message = err instanceof Error ? err.message : "Failed to poll session"
        setError(message)
        setIsStarting(false)
      })
  }, [])

  const startSession = useCallback(
    (config?: TrainingConfig) => {
      // Reset state
      setWsUrl(null)
      setSessionId(null)
      setStatus(null)
      setError(null)
      setIsStarting(true)
      pollCountRef.current = 0

      if (pollTimerRef.current !== null) {
        clearTimeout(pollTimerRef.current)
        pollTimerRef.current = null
      }

      const sessionConfig: TrainingConfig = {
        difficulty: "normal",
        mission_sols: 450,
        mode: "interactive",
        ...config,
      }

      orchestrator
        .startSession(sessionConfig)
        .then((info) => {
          if (!mountedRef.current) return
          setSessionId(info.session_id)
          setStatus(info.status)

          // If already running with a ws_url (unlikely but possible)
          if (info.status === "running" && info.ws_ready && info.ws_url) {
            setWsUrl(info.ws_url)
            setIsStarting(false)
            return
          }

          // Start polling
          pollTimerRef.current = setTimeout(() => pollSession(info.session_id), POLL_INTERVAL_MS)
        })
        .catch((err: unknown) => {
          if (!mountedRef.current) return
          const message = err instanceof Error ? err.message : "Failed to start session"
          setError(message)
          setIsStarting(false)
        })
    },
    [pollSession],
  )

  return {
    wsUrl,
    sessionId,
    status,
    isStarting,
    error,
    startSession,
  }
}
