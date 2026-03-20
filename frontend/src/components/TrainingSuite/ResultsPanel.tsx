import { useEffect, useState } from "react"

import type { SessionDetail, TrainingResult } from "@/types/orchestrator"

interface ResultsPanelProps {
  session: SessionDetail
  fetchResults: (runId: string) => Promise<TrainingResult | null>
  onClose: () => void
}

export default function ResultsPanel({ session, fetchResults, onClose }: ResultsPanelProps) {
  const isCompleted = session.status === "completed"

  const [result, setResult] = useState<TrainingResult | null>(null)
  const [resultLoading, setResultLoading] = useState(false)
  const [resultError, setResultError] = useState<string | null>(null)

  useEffect(() => {
    if (!isCompleted) return

    let cancelled = false

    const load = async () => {
      setResultLoading(true)
      setResultError(null)

      const fetched = await fetchResults(session.run_id)

      if (cancelled) return

      if (fetched) {
        setResult(fetched)
      } else {
        setResultError("Results not available.")
      }
      setResultLoading(false)
    }

    void load()

    return () => {
      cancelled = true
    }
  }, [isCompleted, session.run_id, fetchResults])

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/60 backdrop-blur-sm">
      <div className="surface-card w-full max-w-lg p-6">
        {/* Header */}
        <div className="mb-5 flex items-center justify-between">
          <h2 className="font-mono text-sm font-bold uppercase tracking-[0.15em] text-foreground">
            Session Results
          </h2>
          <button
            type="button"
            onClick={onClose}
            className="font-mono text-xs text-muted-foreground transition-colors hover:text-foreground"
          >
            Close
          </button>
        </div>

        {/* Session info */}
        <div className="mb-4 space-y-2">
          <div className="flex justify-between">
            <span className="label-aerospace">Run ID</span>
            <span className="font-mono text-xs text-foreground">{session.run_id}</span>
          </div>
          <div className="flex justify-between">
            <span className="label-aerospace">Status</span>
            <span className="font-mono text-xs capitalize text-foreground">{session.status}</span>
          </div>
          {session.current_sol != null && (
            <div className="flex justify-between">
              <span className="label-aerospace">Final Sol</span>
              <span className="font-mono text-xs text-foreground">{session.current_sol} / 450</span>
            </div>
          )}
        </div>

        {/* Completed session with results */}
        {isCompleted && resultLoading && (
          <div className="py-6 text-center">
            <p className="font-mono text-sm text-muted-foreground">Loading results...</p>
          </div>
        )}

        {isCompleted && resultError && (
          <div className="py-6 text-center">
            <p className="font-mono text-sm text-red-400">{resultError}</p>
          </div>
        )}

        {isCompleted && result && (
          <>
            <div className="my-4 h-px bg-border" />

            {/* Overall score */}
            <div className="mb-4 text-center">
              <span className="label-aerospace mb-1 block">Overall Score</span>
              <span className="font-mono text-4xl font-extralight text-green-400">
                {result.final_score.toFixed(1)}
              </span>
            </div>

            {/* Score breakdown */}
            <div className="space-y-2">
              {Object.entries(result.score_breakdown).map(([category, score]) => (
                <div key={category} className="flex items-center justify-between">
                  <span className="label-aerospace">{category.replace(/_/g, " ")}</span>
                  <div className="flex items-center gap-3">
                    <div className="h-1.5 w-24 overflow-hidden rounded-full bg-border">
                      <div
                        className="h-full rounded-full bg-green-400/50"
                        style={{ width: `${Math.min(score, 100)}%` }}
                      />
                    </div>
                    <span className="w-10 text-right font-mono text-xs text-foreground">
                      {score.toFixed(1)}
                    </span>
                  </div>
                </div>
              ))}
            </div>

            <div className="my-4 h-px bg-border" />

            {/* Metadata */}
            <div className="space-y-2">
              <div className="flex justify-between">
                <span className="label-aerospace">Total Crises</span>
                <span className="font-mono text-xs text-foreground">{result.total_crises}</span>
              </div>
              <div className="flex justify-between">
                <span className="label-aerospace">Mission Phase</span>
                <span className="font-mono text-xs capitalize text-foreground">
                  {result.mission_phase}
                </span>
              </div>
              <div className="flex justify-between">
                <span className="label-aerospace">Seed</span>
                <span className="font-mono text-xs text-foreground">{result.seed}</span>
              </div>
              <div className="flex justify-between">
                <span className="label-aerospace">Difficulty</span>
                <span className="font-mono text-xs capitalize text-foreground">
                  {result.difficulty}
                </span>
              </div>
              <div className="flex justify-between">
                <span className="label-aerospace">Completed At</span>
                <span className="font-mono text-xs text-foreground">
                  {new Date(result.completed_at).toLocaleString()}
                </span>
              </div>
            </div>
          </>
        )}

        {/* Non-completed session message */}
        {!isCompleted && (
          <div className="py-6 text-center">
            <p className="font-mono text-sm text-muted-foreground">
              Results are only available for completed sessions.
            </p>
          </div>
        )}
      </div>
    </div>
  )
}
