import type { SessionInfo, SessionStatus } from "@/types/orchestrator"

// ── Status badge config ──────────────────────────────────────────────

const STATUS_CONFIG: Record<SessionStatus, { label: string; color: string; bgColor: string }> = {
  starting: {
    label: "Starting",
    color: "text-yellow-400",
    bgColor: "bg-yellow-400/10 border-yellow-400/20",
  },
  running: {
    label: "Running",
    color: "text-blue-400",
    bgColor: "bg-blue-400/10 border-blue-400/20",
  },
  completed: {
    label: "Completed",
    color: "text-green-400",
    bgColor: "bg-green-400/10 border-green-400/20",
  },
  failed: {
    label: "Failed",
    color: "text-red-400",
    bgColor: "bg-red-400/10 border-red-400/20",
  },
  stopped: {
    label: "Stopped",
    color: "text-neutral-400",
    bgColor: "bg-neutral-400/10 border-neutral-400/20",
  },
}

// ── Component ────────────────────────────────────────────────────────

interface SessionCardProps {
  session: SessionInfo
  detail?: { current_sol?: number; final_score?: number }
  onSelect: (sessionId: string) => void
  onStop: (sessionId: string) => void
}

export default function SessionCard({ session, detail, onSelect, onStop }: SessionCardProps) {
  const statusCfg = STATUS_CONFIG[session.status]
  const startedAt = new Date(session.started_at)
  const timeLabel = startedAt.toLocaleTimeString([], { hour: "2-digit", minute: "2-digit" })

  return (
    <button
      type="button"
      onClick={() => onSelect(session.session_id)}
      className="surface-card w-full cursor-pointer p-4 text-left transition-colors hover:border-secondary-foreground/30"
    >
      {/* Header: status badge + time */}
      <div className="mb-3 flex items-center justify-between">
        <span
          className={`inline-flex items-center gap-1.5 rounded border px-2 py-0.5 font-mono text-xs ${statusCfg.bgColor} ${statusCfg.color}`}
        >
          {session.status === "starting" && (
            <span className="inline-block h-2 w-2 animate-spin rounded-full border border-current border-t-transparent" />
          )}
          {session.status === "running" && (
            <span className="inline-block h-1.5 w-1.5 animate-pulse rounded-full bg-current" />
          )}
          {statusCfg.label}
        </span>
        <span className="font-mono text-xs text-muted-foreground">{timeLabel}</span>
      </div>

      {/* Run ID */}
      <p className="mb-2 truncate font-mono text-sm text-foreground">{session.run_id}</p>

      {/* Sol progress (running sessions) */}
      {session.status === "running" && detail?.current_sol != null && (
        <div className="mb-2">
          <div className="mb-1 flex items-baseline justify-between">
            <span className="label-aerospace">Sol Progress</span>
            <span className="font-mono text-xs text-foreground">{detail.current_sol} / 450</span>
          </div>
          <div className="h-1.5 w-full overflow-hidden rounded-full bg-border">
            <div
              className="h-full rounded-full bg-blue-400/60 transition-all duration-500"
              style={{ width: `${(detail.current_sol / 450) * 100}%` }}
            />
          </div>
        </div>
      )}

      {/* Final score (completed sessions) */}
      {session.status === "completed" && detail?.final_score != null && (
        <div className="flex items-baseline gap-2">
          <span className="label-aerospace">Score</span>
          <span className="font-mono text-lg font-semibold text-green-400">
            {detail.final_score.toFixed(1)}
          </span>
        </div>
      )}

      {/* Stopped sessions: show sol if available */}
      {session.status === "stopped" && detail?.current_sol != null && (
        <div className="flex items-baseline gap-2">
          <span className="label-aerospace">Stopped at Sol</span>
          <span className="font-mono text-sm text-muted-foreground">{detail.current_sol}</span>
        </div>
      )}

      {/* Failed sessions */}
      {session.status === "failed" && detail?.current_sol != null && (
        <div className="flex items-baseline gap-2">
          <span className="label-aerospace">Failed at Sol</span>
          <span className="font-mono text-sm text-red-400">{detail.current_sol}</span>
        </div>
      )}

      {/* Stop button for active sessions */}
      {(session.status === "running" || session.status === "starting") && (
        <button
          type="button"
          onClick={(e) => {
            e.stopPropagation()
            onStop(session.session_id)
          }}
          className="mt-3 w-full rounded border border-red-400/20 bg-red-400/5 px-3 py-1 font-mono text-xs text-red-400 transition-colors hover:bg-red-400/10"
        >
          Stop
        </button>
      )}
    </button>
  )
}
