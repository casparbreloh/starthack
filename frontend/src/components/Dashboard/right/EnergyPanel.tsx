import type { EnergyStatus } from "../../../types/simulation.ts"
import MetricRow from "../MetricRow.tsx"
import Panel from "../Panel.tsx"
import type { Severity } from "../Panel.tsx"
import ProgressBar from "../ProgressBar.tsx"

interface EnergyPanelProps {
  energy: EnergyStatus | null
}

function energySeverity(energy: EnergyStatus): Severity {
  if (energy.deficit) return "critical"
  if (energy.battery_pct < 30) return "warn"
  return "ok"
}

export default function EnergyPanel({ energy }: EnergyPanelProps) {
  if (!energy) {
    return (
      <Panel title="Energy">
        <p className="text-void-text-muted text-sm">Awaiting data…</p>
      </Panel>
    )
  }

  const severity = energySeverity(energy)

  return (
    <Panel title="Energy" subtitle={`${Math.round(energy.battery_pct)}%`} severity={severity}>
      <ProgressBar value={energy.battery_pct} severity={severity} />
      <p className="text-void-text-muted mt-1 font-mono text-xs">
        {energy.battery_level_wh.toLocaleString()} / {energy.battery_capacity_wh.toLocaleString()}{" "}
        Wh
      </p>

      <div className="mt-3 grid grid-cols-2 gap-x-6">
        <MetricRow label="Solar" value={energy.solar_generation_wh} unit="Wh" />
        <MetricRow label="Consumption" value={energy.total_consumption_wh} unit="Wh" />
        <MetricRow
          label="Surplus"
          value={energy.deficit ? "DEFICIT" : `+${energy.surplus_wh}`}
          unit={energy.deficit ? undefined : "Wh"}
        />
        <MetricRow label="Heating" value={energy.breakdown.heating_wh} unit="Wh" dimValue />
        <MetricRow label="Lighting" value={energy.breakdown.lighting_wh} unit="Wh" dimValue />
        <MetricRow
          label="Water rec."
          value={energy.breakdown.water_recycling_wh}
          unit="Wh"
          dimValue
        />
      </div>
    </Panel>
  )
}
