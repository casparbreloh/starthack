import type { CrewHealth } from "../../../types/simulation.ts"
import MetricRow from "../MetricRow.tsx"
import Panel from "../Panel.tsx"
import type { Severity } from "../Panel.tsx"
import ProgressBar from "../ProgressBar.tsx"

interface CrewSurvivalPanelProps {
  crewHealth: CrewHealth | null
}

function healthSeverity(pct: number): Severity {
  if (pct >= 70) return "ok"
  if (pct >= 40) return "warn"
  return "critical"
}

export default function CrewSurvivalPanel({ crewHealth }: CrewSurvivalPanelProps) {
  if (!crewHealth) {
    return (
      <Panel title="Crew Survival">
        <p className="text-void-text-muted text-sm">Awaiting vitals…</p>
      </Panel>
    )
  }

  const severity = crewHealth.alive ? healthSeverity(crewHealth.overall_health_pct) : "critical"

  return (
    <Panel title="Crew Survival" severity={severity}>
      <div className="mb-3 flex items-baseline justify-between">
        <span className="text-void-text-secondary text-sm font-semibold">
          {crewHealth.alive ? "ALIVE" : "DECEASED"}
        </span>
        <span className="text-void-text-primary font-mono text-2xl leading-none font-light">
          {crewHealth.overall_health_pct}
          <span className="text-void-text-tertiary text-sm">%</span>
        </span>
      </div>
      <ProgressBar value={crewHealth.overall_health_pct} severity={severity} />

      {crewHealth.cause_of_death && (
        <p className="text-void-critical mt-1.5 font-mono text-sm">{crewHealth.cause_of_death}</p>
      )}

      {/* Vitals — 2 col grid */}
      <div className="mt-3 grid grid-cols-2 gap-x-6">
        <MetricRow label="Hydration" value={crewHealth.hydration.hydration_pct} unit="%" />
        <MetricRow label="Radiation" value={crewHealth.radiation.pct_of_career_limit} unit="%" />
        <MetricRow label="Starvation" value={crewHealth.starvation.level} />
        <MetricRow
          label="Cum. rad."
          value={crewHealth.radiation.cumulative_msv}
          unit="mSv"
          dimValue
        />
      </div>
    </Panel>
  )
}
