import { ChevronDown } from "lucide-react"
import { useState } from "react"
import { AreaChart, Area, XAxis, YAxis, Tooltip, ResponsiveContainer } from "recharts"

import { useStateHistory } from "@/hooks/useGameData"
import type { TickPayload } from "@/hooks/useWebSocket"

// ── The 5 mission-critical metrics ───────────────────────────────────────────

interface MetricDef {
  key: string
  label: string
  unit: string
  color: string
  extract: (tick: TickPayload) => number | null
  domain?: [number | "auto", number | "auto"]
  formatValue?: (v: number) => string
}

const METRICS: MetricDef[] = [
  {
    key: "battery_pct",
    label: "BATTERY",
    unit: "%",
    color: "#4ade80",
    extract: (t) => (t.energy_status as { battery_pct?: number } | undefined)?.battery_pct ?? null,
    domain: [0, 100],
  },
  {
    key: "water_reservoir_pct",
    label: "WATER RESERVOIR",
    unit: "%",
    color: "#f97316",
    extract: (t) => {
      const w = t.water_status as
        | { reservoir_liters?: number; reservoir_capacity_liters?: number }
        | undefined
      if (!w?.reservoir_liters || !w?.reservoir_capacity_liters) return null
      return Math.round((w.reservoir_liters / w.reservoir_capacity_liters) * 1000) / 10
    },
    domain: [0, 100],
  },
  {
    key: "crew_health_pct",
    label: "CREW HEALTH",
    unit: "%",
    color: "#60a5fa",
    extract: (t) =>
      (t.crew_health as { overall_health_pct?: number } | undefined)?.overall_health_pct ?? null,
    domain: [0, 100],
  },
  {
    key: "calories_pct",
    label: "CALORIE INTAKE",
    unit: "%",
    color: "#a78bfa",
    extract: (t) => {
      const n = t.crew_nutrition as
        | { today?: { calories_consumed_kcal?: number; calories_target_kcal?: number } }
        | undefined
      if (!n?.today?.calories_consumed_kcal || !n?.today?.calories_target_kcal) return null
      return Math.round((n.today.calories_consumed_kcal / n.today.calories_target_kcal) * 1000) / 10
    },
    domain: [0, "auto"],
    formatValue: (v) => v.toFixed(1),
  },
  {
    key: "avg_crop_health",
    label: "AVG CROP HEALTH",
    unit: "%",
    color: "#86efac",
    extract: (t) => {
      const c = t.crops_status as { crops?: Array<{ health?: number }> } | undefined
      if (!c?.crops?.length) return null
      const avg = c.crops.reduce((sum, crop) => sum + (crop.health ?? 0), 0) / c.crops.length
      return Math.round(avg * 1000) / 10
    },
    domain: [0, 100],
  },
]

// ── Mini chart card ───────────────────────────────────────────────────────────

function MiniChart({
  metric,
  data,
}: {
  metric: MetricDef
  data: { sol: number; value: number }[]
}) {
  const latest = data.at(-1)
  const display = latest
    ? metric.formatValue
      ? metric.formatValue(latest.value)
      : latest.value % 1 === 0
        ? String(latest.value)
        : latest.value.toFixed(1)
    : "—"

  return (
    <div className="flex flex-col gap-1 rounded-sm border border-border bg-background/30 px-3 py-2">
      <div className="flex items-baseline justify-between">
        <span className="label-aerospace" style={{ color: metric.color }}>
          {metric.label}
        </span>
        <span className="font-mono text-[11px] tabular-nums text-foreground">
          {display}
          <span className="ml-0.5 font-mono text-[9px] text-muted-foreground">{metric.unit}</span>
        </span>
      </div>
      <div className="h-[72px]">
        {data.length < 2 ? (
          <div className="flex h-full items-center justify-center">
            <span className="font-mono text-[9px] text-muted-foreground">AWAITING DATA</span>
          </div>
        ) : (
          <ResponsiveContainer width="100%" height="100%">
            <AreaChart data={data} margin={{ top: 2, right: 2, bottom: 0, left: 0 }}>
              <defs>
                <linearGradient id={`grad_${metric.key}`} x1="0" y1="0" x2="0" y2="1">
                  <stop offset="5%" stopColor={metric.color} stopOpacity={0.3} />
                  <stop offset="95%" stopColor={metric.color} stopOpacity={0.02} />
                </linearGradient>
              </defs>
              <XAxis dataKey="sol" hide />
              <YAxis domain={metric.domain ?? ["auto", "auto"]} hide />
              <Tooltip
                content={({ active, payload }) => {
                  if (!active || !payload?.length) return null
                  const val = payload[0].value as number
                  const d = metric.formatValue
                    ? metric.formatValue(val)
                    : val % 1 === 0
                      ? String(val)
                      : val.toFixed(1)
                  return (
                    <div className="rounded-sm border border-border bg-card/90 px-2 py-1">
                      <span className="font-mono text-[9px] tabular-nums text-foreground">
                        {d} {metric.unit}
                      </span>
                    </div>
                  )
                }}
              />
              <Area
                type="monotone"
                dataKey="value"
                stroke={metric.color}
                strokeWidth={1.5}
                fill={`url(#grad_${metric.key})`}
                dot={false}
                activeDot={{ r: 2, fill: metric.color, strokeWidth: 0 }}
                isAnimationActive={false}
              />
            </AreaChart>
          </ResponsiveContainer>
        )}
      </div>
    </div>
  )
}

// ── Main panel ────────────────────────────────────────────────────────────────

export function MetricHistoryPanel() {
  const stateHistory = useStateHistory()
  const [open, setOpen] = useState(false)

  const chartDataByKey = Object.fromEntries(
    METRICS.map((m) => [
      m.key,
      stateHistory
        .map((tick) => {
          const sol = (tick.sim_status as { current_sol?: number } | undefined)?.current_sol ?? 0
          const value = m.extract(tick)
          return value != null ? { sol, value } : null
        })
        .filter((d): d is { sol: number; value: number } => d !== null),
    ]),
  )

  return (
    <div className="flex flex-col items-center">
      {/* Trigger button */}
      <button
        onClick={() => setOpen((o) => !o)}
        className="flex items-center gap-1.5 rounded-sm border border-border bg-card/80 px-4 py-1.5 backdrop-blur-sm transition-colors hover:bg-card"
      >
        <span className="label-aerospace text-muted-foreground">MISSION CHARTS</span>
        <ChevronDown
          className="h-3 w-3 text-muted-foreground transition-transform duration-200"
          style={{ transform: open ? "rotate(180deg)" : "rotate(0deg)" }}
        />
      </button>

      {/* Dropdown panel */}
      {open && (
        <div className="mt-1 w-[680px] rounded-sm border border-border bg-card/90 p-3 backdrop-blur-sm">
          <div className="grid grid-cols-2 gap-2">
            {METRICS.slice(0, 4).map((m) => (
              <MiniChart key={m.key} metric={m} data={chartDataByKey[m.key]} />
            ))}
          </div>
          <div className="mt-2">
            <MiniChart metric={METRICS[4]} data={chartDataByKey[METRICS[4].key]} />
          </div>
        </div>
      )}
    </div>
  )
}
