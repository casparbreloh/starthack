import type { CrewNutrition } from "../../../types/simulation.ts"
import MetricRow from "../MetricRow.tsx"
import Panel from "../Panel.tsx"
import type { Severity } from "../Panel.tsx"
import ProgressBar from "../ProgressBar.tsx"

interface CrewNutritionPanelProps {
  crew: CrewNutrition | null
}

function calorieSeverity(consumed: number, target: number): Severity {
  const ratio = consumed / target
  if (ratio >= 0.85) return "ok"
  if (ratio >= 0.6) return "warn"
  return "critical"
}

export default function CrewNutritionPanel({ crew }: CrewNutritionPanelProps) {
  if (!crew) {
    return (
      <Panel title="Crew Nutrition">
        <p className="text-void-text-muted text-sm">Awaiting data…</p>
      </Panel>
    )
  }

  const { today, stored_food, food_buffer, cumulative } = crew
  const calPct = Math.round((today.calories_consumed_kcal / today.calories_target_kcal) * 100)
  const protPct = Math.round((today.protein_consumed_g / today.protein_target_g) * 100)

  return (
    <Panel
      title="Crew Nutrition"
      severity={calorieSeverity(today.calories_consumed_kcal, today.calories_target_kcal)}
    >
      <div className="grid grid-cols-2 gap-6">
        <div>
          <div className="mb-1.5 flex items-baseline justify-between">
            <span className="text-void-text-secondary text-sm font-semibold">Calories</span>
            <span className="font-mono text-sm font-semibold">
              <span className="text-void-text-primary">{calPct}</span>
              <span className="text-void-text-tertiary">%</span>
            </span>
          </div>
          <ProgressBar
            value={calPct}
            severity={calorieSeverity(today.calories_consumed_kcal, today.calories_target_kcal)}
          />
          <p className="text-void-text-muted mt-1 font-mono text-xs">
            {today.calories_consumed_kcal.toLocaleString()} /{" "}
            {today.calories_target_kcal.toLocaleString()} kcal
          </p>
        </div>
        <div>
          <div className="mb-1.5 flex items-baseline justify-between">
            <span className="text-void-text-secondary text-sm font-semibold">Protein</span>
            <span className="font-mono text-sm font-semibold">
              <span className="text-void-text-primary">{protPct}</span>
              <span className="text-void-text-tertiary">%</span>
            </span>
          </div>
          <ProgressBar value={protPct} />
          <p className="text-void-text-muted mt-1 font-mono text-xs">
            {today.protein_consumed_g} / {today.protein_target_g} g
          </p>
        </div>
      </div>

      <div className="mt-3 grid grid-cols-2 gap-x-6">
        <MetricRow label="Greenhouse" value={today.from_greenhouse_pct} unit="%" />
        <MetricRow label="Stored" value={today.from_stored_food_pct} unit="%" />
        <MetricRow label="Food left" value={stored_food.remaining_days_at_current_rate} unit="d" />
        <MetricRow label="Buffer" value={food_buffer.days_of_buffer} unit="d" />
        <MetricRow label="Avg kcal/d" value={cumulative.avg_daily_kcal} dimValue />
        <MetricRow label="Deficit days" value={cumulative.deficit_sols} dimValue />
      </div>
    </Panel>
  )
}
