import type { Crop } from "../../types/simulation"

interface Props {
  crop: Crop
}

const CROP_ICONS: Record<
  string,
  { seed: string; growing: string; ready: string; dead: string; color: string; glow: string }
> = {
  potato: { seed: "🌱", growing: "🌿", ready: "🥔", dead: "🪨", color: "#92400e", glow: "#d97706" },
  lettuce: {
    seed: "🌱",
    growing: "🥬",
    ready: "🥬",
    dead: "🍂",
    color: "#14532d",
    glow: "#22c55e",
  },
  bean: { seed: "🌱", growing: "🌿", ready: "🫘", dead: "🍂", color: "#1e3a5f", glow: "#60a5fa" },
  radish: { seed: "🌱", growing: "🌱", ready: "🌸", dead: "🍂", color: "#4c1d48", glow: "#e879f9" },
  herb: { seed: "🌱", growing: "🌿", ready: "🌿", dead: "🍂", color: "#134e4a", glow: "#2dd4bf" },
}

function getIcon(crop: Crop): string {
  const icons = CROP_ICONS[crop.type] ?? CROP_ICONS.herb
  if (crop.health < 0.2) return icons.dead
  if (crop.growth_pct < 20) return icons.seed
  if (crop.growth_pct < 70) return icons.growing
  return icons.ready
}

export default function PlantCell({ crop }: Props) {
  const icons = CROP_ICONS[crop.type] ?? CROP_ICONS.herb
  const icon = getIcon(crop)
  const isDead = crop.health < 0.2
  const isStressed = crop.stress_indicators.length > 0
  const healthPct = crop.health * 100

  const borderColor = isDead
    ? "#374151"
    : isStressed
      ? "#ef4444"
      : healthPct > 80
        ? icons.glow
        : "#d97706"

  const bgColor = isDead ? "rgba(17,24,39,0.8)" : `${icons.color}55`

  return (
    <div
      className="relative flex cursor-default flex-col items-center gap-1 rounded-lg p-2 transition-all duration-300"
      style={{
        border: `1px solid ${borderColor}`,
        background: bgColor,
        boxShadow: isDead ? "none" : `0 0 8px ${borderColor}44`,
        minWidth: "70px",
      }}
      title={`${crop.type} (Zone ${crop.zone_id})\nHealth: ${healthPct.toFixed(0)}%\nGrowth: ${crop.growth_pct.toFixed(0)}%\nHarvest: Sol ${crop.expected_harvest_sol}`}
    >
      {/* Stress pulse ring */}
      {isStressed && !isDead && (
        <div
          className="absolute inset-0 animate-pulse rounded-lg"
          style={{ border: "2px solid #ef444466" }}
        />
      )}

      {/* Icon */}
      <span className={`text-2xl leading-none ${isDead ? "opacity-40 grayscale" : ""}`}>
        {icon}
      </span>

      {/* Crop name */}
      <span
        className="font-mono text-xs font-bold capitalize"
        style={{ color: isDead ? "#4b5563" : icons.glow }}
      >
        {crop.type.slice(0, 3).toUpperCase()}
      </span>

      {/* Growth bar */}
      <div className="w-full overflow-hidden rounded-full bg-gray-800" style={{ height: "3px" }}>
        <div
          className="h-full rounded-full transition-all duration-500"
          style={{
            width: `${crop.growth_pct}%`,
            background: isDead ? "#374151" : icons.glow,
          }}
        />
      </div>

      {/* Health indicator dot */}
      <div className="flex gap-0.5">
        {[0.2, 0.4, 0.6, 0.8, 1.0].map((threshold, i) => (
          <div
            key={i}
            className="h-1.5 w-1.5 rounded-full"
            style={{
              background:
                crop.health >= threshold ? (crop.health > 0.7 ? icons.glow : "#d97706") : "#1f2937",
            }}
          />
        ))}
      </div>

      {/* Area label */}
      <span className="font-mono text-xs text-gray-600">{crop.area_m2}m²</span>
    </div>
  )
}
