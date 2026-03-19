import type { WaterStatus, EnergyStatus } from "@/types/game"

interface ResourceBarsProps {
  water: WaterStatus
  energy: EnergyStatus
  o2Level?: number
}

function ResourceBar({
  label,
  value,
  max = 100,
  unit = "%",
}: {
  label: string
  value: number
  max?: number
  unit?: string
}) {
  const pct = Math.min(100, (value / max) * 100)
  const barBg = pct > 60 ? "bg-primary" : pct > 30 ? "bg-amber-alert" : "bg-destructive"

  return (
    <div className="flex flex-col gap-1">
      <div className="flex items-baseline justify-between">
        <span className="label-aerospace">{label}</span>
        <span className="font-mono text-sm tabular-nums text-foreground">
          {Math.round(value)}
          {unit}
        </span>
      </div>
      <div className="h-2 overflow-hidden rounded-sm bg-secondary">
        <div
          className={`h-full rounded-sm transition-all duration-500 ${barBg}`}
          style={{ width: `${pct}%` }}
        />
      </div>
    </div>
  )
}

export function ResourceBars({ water, energy, o2Level = 89 }: ResourceBarsProps) {
  return (
    <div className="flex flex-col gap-3">
      <ResourceBar label="WATER" value={water.reservoir_level_pct} />
      <ResourceBar label="ENERGY" value={energy.battery_pct} />
      <ResourceBar label="O₂" value={o2Level} />
    </div>
  )
}
