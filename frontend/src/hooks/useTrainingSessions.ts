import { useCallback, useEffect, useRef, useState } from "react"

import * as orchestrator from "@/api/orchestrator"
import type {
  SessionDetail,
  SessionInfo,
  TrainingConfig,
  TrainingResult,
} from "@/types/orchestrator"

// ── Hook ─────────────────────────────────────────────────────────────

export interface TrainingSessionsState {
  sessions: SessionInfo[]
  sessionDetails: Record<string, SessionDetail>
  selectedSession: SessionDetail | null
  resultsCache: Record<string, TrainingResult>
  loading: boolean
  error: string | null
  startSession: (config: TrainingConfig) => Promise<void>
  stopSession: (sessionId: string) => Promise<void>
  refreshSessions: () => Promise<void>
  selectSession: (sessionId: string | null) => void
  fetchResults: (runId: string) => Promise<TrainingResult | null>
}

const POLL_INTERVAL_MS = 5_000

export function useTrainingSessions(): TrainingSessionsState {
  const [sessions, setSessions] = useState<SessionInfo[]>([])
  const [sessionDetails, setSessionDetails] = useState<Record<string, SessionDetail>>({})
  const [selectedSession, setSelectedSession] = useState<SessionDetail | null>(null)
  const [resultsCache, setResultsCache] = useState<Record<string, TrainingResult>>({})
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)

  const pollRef = useRef<ReturnType<typeof setInterval> | null>(null)
  const mountedRef = useRef(true)

  // ── Refresh sessions list + details ──────────────────────────────

  const refreshSessions = useCallback(async () => {
    try {
      const sessionList = await orchestrator.listSessions()
      if (!mountedRef.current) return

      setSessions(sessionList)
      setError(null)

      // Fetch details for active / completed sessions
      const detailPromises = sessionList.map(async (s) => {
        try {
          const detail = await orchestrator.getSession(s.session_id)
          return [s.session_id, detail] as const
        } catch {
          return null
        }
      })

      const detailResults = await Promise.all(detailPromises)
      if (!mountedRef.current) return

      const detailsMap: Record<string, SessionDetail> = {}
      for (const entry of detailResults) {
        if (entry) {
          detailsMap[entry[0]] = entry[1]
        }
      }
      setSessionDetails(detailsMap)

      // Update selected session if it's currently open
      setSelectedSession((prev) => {
        if (prev && detailsMap[prev.session_id]) {
          return detailsMap[prev.session_id]
        }
        return prev
      })
    } catch (err) {
      if (!mountedRef.current) return
      const message = err instanceof Error ? err.message : "Failed to fetch sessions"
      setError(message)
    }
  }, [])

  // ── Start session ────────────────────────────────────────────────

  const startSession = useCallback(
    async (config: TrainingConfig) => {
      try {
        setError(null)
        const newSession = await orchestrator.startSession(config)
        if (!mountedRef.current) return

        setSessions((prev) => [newSession, ...prev])
        // Trigger a full refresh to pick up latest state
        await refreshSessions()
      } catch (err) {
        if (!mountedRef.current) return
        const message = err instanceof Error ? err.message : "Failed to start session"
        setError(message)
      }
    },
    [refreshSessions],
  )

  // ── Stop session ─────────────────────────────────────────────────

  const stopSession = useCallback(async (sessionId: string) => {
    try {
      setError(null)
      // Optimistic update — button disappears immediately
      setSessions((prev) =>
        prev.map((s) => (s.session_id === sessionId ? { ...s, status: "stopped" as const } : s)),
      )
      await orchestrator.stopSession(sessionId)
      // Don't refreshSessions() here — the optimistic update already
      // hides the stop button, and the next poll cycle will pick up
      // the real ECS status (STOPPING → "stopped").
    } catch (err) {
      if (!mountedRef.current) return
      const message = err instanceof Error ? err.message : "Failed to stop session"
      setError(message)
    }
  }, [])

  // ── Select session ───────────────────────────────────────────────

  const selectSession = useCallback(
    (sessionId: string | null) => {
      if (sessionId === null) {
        setSelectedSession(null)
        return
      }
      const detail = sessionDetails[sessionId] ?? null
      setSelectedSession(detail)
    },
    [sessionDetails],
  )

  // ── Fetch results ────────────────────────────────────────────────

  const fetchResults = useCallback(
    async (runId: string): Promise<TrainingResult | null> => {
      // Return cached result if available
      if (resultsCache[runId]) {
        return resultsCache[runId]
      }

      try {
        const result = await orchestrator.getResults(runId)
        if (!mountedRef.current) return null

        setResultsCache((prev) => ({ ...prev, [runId]: result }))
        return result
      } catch {
        return null
      }
    },
    [resultsCache],
  )

  // ── Initial fetch ────────────────────────────────────────────────

  useEffect(() => {
    mountedRef.current = true

    const init = async () => {
      setLoading(true)
      await refreshSessions()
      if (mountedRef.current) setLoading(false)
    }
    void init()

    return () => {
      mountedRef.current = false
    }
  }, [refreshSessions])

  // ── Polling: only when active sessions exist ─────────────────────

  useEffect(() => {
    const hasActiveSessions = sessions.some(
      (s) => s.status === "starting" || s.status === "running",
    )

    if (hasActiveSessions) {
      if (!pollRef.current) {
        pollRef.current = setInterval(() => {
          void refreshSessions()
        }, POLL_INTERVAL_MS)
      }
    } else {
      if (pollRef.current) {
        clearInterval(pollRef.current)
        pollRef.current = null
      }
    }

    return () => {
      if (pollRef.current) {
        clearInterval(pollRef.current)
        pollRef.current = null
      }
    }
  }, [sessions, refreshSessions])

  return {
    sessions,
    sessionDetails,
    selectedSession,
    resultsCache,
    loading,
    error,
    startSession,
    stopSession,
    refreshSessions,
    selectSession,
    fetchResults,
  }
}
