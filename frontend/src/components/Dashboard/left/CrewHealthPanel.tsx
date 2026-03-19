import type { CrewMembers } from "../../../types/simulation.ts"
import Panel from "../Panel.tsx"
import type { Severity } from "../Panel.tsx"
import ProgressBar from "../ProgressBar.tsx"

interface CrewHealthPanelProps {
  crewMembers: CrewMembers | null
}

function healthSeverity(pct: number): Severity {
  if (pct >= 70) return "ok"
  if (pct >= 40) return "warn"
  return "critical"
}

function statusColor(status: string): string {
  if (status === "nominal") return "var(--color-void-ok)"
  if (status === "warning") return "var(--color-void-warn)"
  return "var(--color-void-critical)"
}

export default function CrewHealthPanel({ crewMembers }: CrewHealthPanelProps) {
  if (!crewMembers) {
    return (
      <Panel title="Crew Health">
        <p className="text-void-text-muted text-sm">Awaiting crew data…</p>
      </Panel>
    )
  }

  return (
    <Panel title="Crew Health" subtitle={`${crewMembers.crew_size} members`}>
      <div className="grid grid-cols-4 gap-4">
        {crewMembers.members.map((m) => {
          const severity = m.alive ? healthSeverity(m.health_pct) : "critical"
          return (
            <div key={m.member_id} className="flex flex-col">
              <span className="text-void-text-secondary mb-2 text-xs font-bold uppercase tracking-wider">
                {m.name}
              </span>

              <div className="mb-1.5 flex items-baseline justify-between">
                <span className="text-void-text-tertiary text-sm">Health</span>
                <span className="text-void-text-primary font-mono text-[15px] font-semibold">
                  {m.health_pct}
                </span>
              </div>
              <ProgressBar value={m.health_pct} severity={severity} />

              <div className="mt-2 flex items-center justify-between">
                <span
                  className="font-mono text-xs font-semibold uppercase"
                  style={{ color: statusColor(m.status) }}
                >
                  {m.status}
                </span>
                <span className="text-void-text-muted font-mono text-xs">
                  {m.hydration_pct}% H₂O
                </span>
              </div>
            </div>
          )
        })}
      </div>
    </Panel>
  )
}
