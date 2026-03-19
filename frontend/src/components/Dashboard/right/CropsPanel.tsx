import type { CropsStatus } from "../../../types/simulation.ts"
import Panel from "../Panel.tsx"
import type { Severity } from "../Panel.tsx"
import ProgressBar from "../ProgressBar.tsx"

interface CropsPanelProps {
  crops: CropsStatus | null
}

function cropHealthSeverity(health: number): Severity {
  if (health >= 0.7) return "ok"
  if (health >= 0.4) return "warn"
  return "critical"
}

export default function CropsPanel({ crops }: CropsPanelProps) {
  if (!crops) {
    return (
      <Panel title="Crops">
        <p className="text-void-text-muted text-sm">Awaiting data…</p>
      </Panel>
    )
  }

  return (
    <Panel
      title="Crops"
      subtitle={`${crops.total_planted_area_m2} m² · ${Object.values(crops.available_area_per_zone).reduce((a, b) => a + b, 0)} m² free`}
    >
      {crops.crops.length === 0 ? (
        <p className="text-void-text-tertiary text-sm">No crops planted</p>
      ) : (
        <div className="grid grid-cols-2 gap-x-6 gap-y-3">
          {crops.crops.map((crop) => {
            const healthSev = cropHealthSeverity(crop.health)
            const isReady = crop.growth_pct >= 100

            return (
              <div key={crop.crop_id}>
                {/* Name + growth */}
                <div className="mb-0.5 flex items-baseline justify-between">
                  <div className="flex items-baseline gap-1">
                    <span className="text-void-text-primary text-sm font-semibold capitalize">
                      {crop.type}
                    </span>
                    <span className="text-void-text-muted font-mono text-xs">{crop.zone_id}</span>
                  </div>
                  <div className="flex items-baseline gap-1">
                    {isReady && (
                      <span
                        className="text-xs font-bold uppercase"
                        style={{ color: "var(--color-void-ok)" }}
                      >
                        RDY
                      </span>
                    )}
                    <span className="text-void-text-primary font-mono text-sm font-semibold">
                      {crop.growth_pct.toFixed(0)}%
                    </span>
                  </div>
                </div>
                <ProgressBar value={crop.growth_pct} />
                {/* Health + yield inline */}
                <div className="mt-0.5 flex items-center justify-between">
                  <span
                    className="font-mono text-xs font-medium"
                    style={{ color: `var(--color-void-${healthSev})` }}
                  >
                    {Math.round(crop.health * 100)}%
                  </span>
                  <span className="text-void-text-muted font-mono text-xs">
                    ~{crop.estimated_yield_kg.toFixed(1)} kg
                  </span>
                </div>
                {crop.stress_indicators.length > 0 && (
                  <span className="font-mono text-xs" style={{ color: "var(--color-void-warn)" }}>
                    {crop.stress_indicators.map((s) => s.type.replace(/_/g, " ")).join(", ")}
                  </span>
                )}
              </div>
            )
          })}
        </div>
      )}
    </Panel>
  )
}
