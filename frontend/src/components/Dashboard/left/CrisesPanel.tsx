import { num } from "@/lib/num"

import type { ActiveCrises } from "../../../types/simulation.ts"
import Panel from "../Panel.tsx"
import type { Severity } from "../Panel.tsx"
import StatusDot from "../StatusDot.tsx"

interface CrisesPanelProps {
  crises: ActiveCrises | null
}

function mapSeverity(s: string): Severity {
  if (s === "critical" || s === "high") return "critical"
  if (s === "warning" || s === "medium") return "warn"
  return "ok"
}

function mapDotSeverity(s: string): "ok" | "warn" | "critical" | "info" | "inactive" {
  if (s === "critical" || s === "high") return "critical"
  if (s === "warning" || s === "medium") return "warn"
  return "info"
}

export default function CrisesPanel({ crises }: CrisesPanelProps) {
  const activeCrises = crises?.crises.filter((c) => !c.resolved) ?? []
  const panelSeverity: Severity | undefined =
    activeCrises.length > 0
      ? activeCrises.some((c) => c.severity === "critical" || c.severity === "high")
        ? "critical"
        : "warn"
      : undefined

  return (
    <Panel title="Active Crises" severity={panelSeverity}>
      {activeCrises.length === 0 ? (
        <p className="text-void-text-tertiary text-sm">No active crises</p>
      ) : (
        <div className="space-y-2">
          {activeCrises.map((crisis) => (
            <div
              key={crisis.id}
              className="border-void-border-subtle flex items-start gap-2 border-b pb-2 last:border-0 last:pb-0"
            >
              <StatusDot severity={mapDotSeverity(crisis.severity)} active className="mt-[3px]" />
              <div className="min-w-0 flex-1">
                <div className="flex items-baseline justify-between gap-2">
                  <span
                    className="text-xs font-bold uppercase tracking-wider"
                    style={{ color: `var(--color-void-${mapSeverity(crisis.severity)})` }}
                  >
                    {crisis.type.replace(/_/g, " ")}
                  </span>
                  <span className="text-void-text-muted shrink-0 font-mono text-xs">
                    SOL {crisis.started_sol}
                  </span>
                </div>
                {crisis.current_value !== undefined && crisis.threshold !== undefined && (
                  <p className="text-void-text-tertiary mt-0.5 font-mono text-xs">
                    {num(crisis.current_value).toFixed(1)} / {num(crisis.threshold).toFixed(1)}
                  </p>
                )}
              </div>
            </div>
          ))}
        </div>
      )}
    </Panel>
  )
}
