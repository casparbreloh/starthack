import type { WaterStatus } from "../../../types/simulation.ts"
import MetricRow from "../MetricRow.tsx"
import Panel from "../Panel.tsx"
import type { Severity } from "../Panel.tsx"
import ProgressBar from "../ProgressBar.tsx"

interface WaterPanelProps {
  water: WaterStatus | null
}

function waterSeverity(water: WaterStatus): Severity {
  if (water.days_until_critical <= 14) return "critical"
  if (water.days_until_critical <= 60) return "warn"
  return "ok"
}

export default function WaterPanel({ water }: WaterPanelProps) {
  if (!water) {
    return (
      <Panel title="Water">
        <p className="text-void-text-muted text-sm">Awaiting data…</p>
      </Panel>
    )
  }

  const severity = waterSeverity(water)
  const reservoirPct = Math.round((water.reservoir_liters / water.reservoir_capacity_liters) * 100)

  return (
    <Panel title="Water" subtitle={`${reservoirPct}%`} severity={severity}>
      <ProgressBar value={reservoirPct} severity={severity} />
      <p className="text-void-text-muted mt-1 font-mono text-xs">
        {Math.round(water.reservoir_liters).toLocaleString()} /{" "}
        {water.reservoir_capacity_liters.toLocaleString()} L
      </p>

      <div className="mt-3 grid grid-cols-2 gap-x-6">
        <MetricRow
          label="Net/day"
          value={
            water.daily_net_change_liters > 0
              ? `+${water.daily_net_change_liters}`
              : String(water.daily_net_change_liters)
          }
          unit="L"
        />
        <MetricRow label="Critical in" value={water.days_until_critical} unit="d" />
        <MetricRow label="Filter" value={water.filter_health_pct} unit="%" />
        <MetricRow label="Recycling" value={water.recycling_efficiency_pct} unit="%" />
        <MetricRow
          label="Crew use"
          value={water.daily_crew_consumption_liters}
          unit="L/d"
          dimValue
        />
        <MetricRow
          label="Crop use"
          value={water.daily_crop_consumption_liters}
          unit="L/d"
          dimValue
        />
      </div>
    </Panel>
  )
}
