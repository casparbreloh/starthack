import type { EnergyStatus, WaterStatus, NutrientsStatus } from "../../types/simulation"

interface Props {
  energy: EnergyStatus | null
  water: WaterStatus | null
  nutrients: NutrientsStatus | null
}

function ResourceBar({
  label,
  icon,
  value,
  max,
  unit,
  color,
  warnBelow = 30,
  extra,
}: {
  label: string
  icon: string
  value: number
  max: number
  unit: string
  color: string
  warnBelow?: number
  extra?: string
}) {
  const pct = Math.min(100, Math.max(0, (value / max) * 100))
  const isWarn = pct < warnBelow

  return (
    <div
      className="flex items-center gap-3 rounded-lg px-4 py-2.5"
      style={{
        background: "rgba(0,10,5,0.85)",
        border: `1px solid ${isWarn ? "#7f1d1d" : "#1f2937"}`,
        boxShadow: isWarn ? "0 0 10px #ef444422" : "none",
      }}
    >
      <span className="text-lg">{icon}</span>
      <div className="flex-1">
        <div className="mb-1 flex justify-between font-mono text-xs">
          <span className="tracking-wide text-gray-400 uppercase">{label}</span>
          <span style={{ color: isWarn ? "#f87171" : color }}>
            {typeof value === "number" ? value.toLocaleString() : value} {unit}
          </span>
        </div>
        <div
          className="w-full overflow-hidden rounded-full"
          style={{ height: "8px", background: "rgba(0,0,0,0.6)", border: "1px solid #111" }}
        >
          <div
            className={`h-full rounded-full transition-all duration-700 ${isWarn ? "animate-pulse" : ""}`}
            style={{
              width: `${pct}%`,
              background: color,
              boxShadow: `0 0 8px ${color}99`,
            }}
          />
        </div>
      </div>
      {extra && <span className="shrink-0 font-mono text-xs text-gray-600">{extra}</span>}
    </div>
  )
}

export default function ResourceBars({ energy, water, nutrients }: Props) {
  return (
    <div className="grid grid-cols-1 gap-2 sm:grid-cols-3">
      <ResourceBar
        label="Battery"
        icon="⚡"
        value={energy?.battery_level_wh ?? 0}
        max={energy?.battery_capacity_wh ?? 20000}
        unit="Wh"
        color={energy?.deficit ? "#ef4444" : "#facc15"}
        warnBelow={25}
        extra={energy?.deficit ? "⚠ DEFICIT" : `+${energy?.surplus_wh ?? 0}Wh`}
      />
      <ResourceBar
        label="Water"
        icon="💧"
        value={water?.reservoir_liters ?? 0}
        max={water?.reservoir_capacity_liters ?? 600}
        unit="L"
        color="#38bdf8"
        warnBelow={25}
        extra={`${water?.days_until_critical ?? "—"}d`}
      />
      <ResourceBar
        label="Nutrients"
        icon="🧪"
        value={nutrients?.nutrient_stock_remaining_pct ?? 0}
        max={100}
        unit="%"
        color="#a78bfa"
        warnBelow={20}
        extra={`${nutrients?.days_of_stock_remaining ?? "—"}d`}
      />
    </div>
  )
}
