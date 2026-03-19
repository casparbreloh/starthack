import type { CrewNutrition, ActiveCrises } from "../../types/simulation"

interface Props {
  crew: CrewNutrition | null
  crises: ActiveCrises | null
}

function HUDBar({
  value,
  max,
  color,
  label,
}: {
  value: number
  max: number
  color: string
  label: string
}) {
  const pct = Math.min(100, Math.max(0, (value / max) * 100))
  const isLow = pct < 30
  return (
    <div className="flex items-center gap-2">
      <span className="w-16 shrink-0 font-mono text-xs text-gray-400">{label}</span>
      <div
        className="bg-opacity-60 flex-1 overflow-hidden rounded-sm bg-black"
        style={{ height: "10px", border: "1px solid #1f2937" }}
      >
        <div
          className={`h-full transition-all duration-700 ${isLow ? "animate-pulse" : ""}`}
          style={{ width: `${pct}%`, background: color, boxShadow: `0 0 6px ${color}` }}
        />
      </div>
      <span className="w-10 text-right font-mono text-xs" style={{ color }}>
        {pct.toFixed(0)}%
      </span>
    </div>
  )
}

export default function AstronautHUD({ crew, crises }: Props) {
  const activeCrises = crises?.crises ?? []
  const hasCritical = activeCrises.some((c) => c.severity === "critical")

  const calPct = crew
    ? (crew.today.calories_consumed_kcal / crew.today.calories_target_kcal) * 100
    : 0
  const proteinPct = crew ? (crew.today.protein_consumed_g / crew.today.protein_target_g) * 100 : 0
  const storedDays = crew?.stored_food.remaining_days_at_current_rate ?? 0

  return (
    <div
      className="overflow-hidden rounded-xl"
      style={{
        background: "rgba(0,10,5,0.92)",
        border: "1px solid #065f46",
        boxShadow: hasCritical ? "0 0 20px #ef444466" : "0 0 12px #065f4644",
        minWidth: "220px",
        backdropFilter: "blur(4px)",
      }}
    >
      {/* Title bar */}
      <div
        className="flex items-center gap-2 px-3 py-1.5"
        style={{ background: "rgba(6,95,70,0.4)", borderBottom: "1px solid #065f46" }}
      >
        <span className="text-base">👨‍🚀</span>
        <span className="font-mono text-xs font-bold tracking-widest text-green-400 uppercase">
          CREW · 4 ASTRONAUTS
        </span>
        {hasCritical && (
          <span className="ml-auto animate-pulse font-mono text-xs text-red-400">⚠ CRITICAL</span>
        )}
      </div>

      <div className="space-y-2 p-3">
        {/* Vital bars */}
        <div className="space-y-1.5">
          <HUDBar
            value={crew?.today.calories_consumed_kcal ?? 0}
            max={crew?.today.calories_target_kcal ?? 12000}
            color={calPct >= 90 ? "#22c55e" : calPct >= 60 ? "#eab308" : "#ef4444"}
            label="CALORIES"
          />
          <HUDBar
            value={crew?.today.protein_consumed_g ?? 0}
            max={crew?.today.protein_target_g ?? 450}
            color={proteinPct >= 90 ? "#60a5fa" : proteinPct >= 60 ? "#f59e0b" : "#ef4444"}
            label="PROTEIN"
          />
          <HUDBar
            value={Math.min(storedDays, 450)}
            max={450}
            color={storedDays > 90 ? "#a78bfa" : storedDays > 30 ? "#eab308" : "#ef4444"}
            label="RESERVES"
          />
        </div>

        {/* Stats */}
        <div className="grid grid-cols-2 gap-x-3 border-t border-gray-800 pt-1">
          <div>
            <div className="font-mono text-xs text-gray-600">KCAL TODAY</div>
            <div className="font-mono text-sm font-bold text-green-400">
              {crew?.today.calories_consumed_kcal.toLocaleString() ?? "—"}
            </div>
          </div>
          <div>
            <div className="font-mono text-xs text-gray-600">STORED DAYS</div>
            <div
              className={`font-mono text-sm font-bold ${storedDays > 60 ? "text-purple-400" : "text-red-400"}`}
            >
              {storedDays}
            </div>
          </div>
          <div>
            <div className="font-mono text-xs text-gray-600">FROM GH</div>
            <div className="font-mono text-sm font-bold text-teal-400">
              {crew?.today.from_greenhouse_pct ?? "—"}%
            </div>
          </div>
          <div>
            <div className="font-mono text-xs text-gray-600">DEFICIT DAYS</div>
            <div
              className={`font-mono text-sm font-bold ${(crew?.cumulative.deficit_days ?? 0) === 0 ? "text-green-400" : "text-red-400"}`}
            >
              {crew?.cumulative.deficit_days ?? "—"}
            </div>
          </div>
        </div>

        {/* Active crises */}
        {activeCrises.length > 0 && (
          <div className="space-y-1 border-t border-gray-800 pt-1">
            {activeCrises.slice(0, 3).map((c) => (
              <div
                key={c.id}
                className="flex items-center gap-1.5 font-mono text-xs"
                style={{ color: c.severity === "critical" ? "#f87171" : "#fbbf24" }}
              >
                <span>{c.severity === "critical" ? "🔴" : "🟡"}</span>
                <span className="truncate">{c.type.replace(/_/g, " ")}</span>
              </div>
            ))}
          </div>
        )}
      </div>
    </div>
  )
}
