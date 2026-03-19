import type { CrewNutrition, FoodInventoryItem } from "../../types/simulation"

interface Props {
  crew: CrewNutrition | null
}

const FOOD_META: Record<string, { label: string; icon: string; color: string; role: string }> = {
  potato: { label: "Potato", icon: "🥔", color: "#a78bfa", role: "Caloric staple" },
  beans: { label: "Beans/Peas", icon: "🫘", color: "#34d399", role: "Protein source" },
  lettuce: { label: "Lettuce", icon: "🥬", color: "#86efac", role: "Micronutrients" },
  radish: { label: "Radish", icon: "🌱", color: "#f87171", role: "Emergency buffer" },
  herbs: { label: "Herbs", icon: "🌿", color: "#fbbf24", role: "Crew morale" },
}

function FoodRow({ foodType, item }: { foodType: string; item: FoodInventoryItem }) {
  const meta = FOOD_META[foodType] ?? {
    label: foodType,
    icon: "📦",
    color: "#9ca3af",
    role: "",
  }
  const pct = Math.min(100, Math.max(0, item.pct_remaining))
  const isLow = pct < 20
  const isCritical = pct < 10

  return (
    <div
      className="rounded-lg px-3 py-2"
      style={{
        background: "rgba(0,0,0,0.35)",
        border: `1px solid ${meta.color}22`,
      }}
    >
      {/* Header row */}
      <div className="mb-1.5 flex items-center justify-between gap-2">
        <div className="flex items-center gap-1.5">
          <span className="text-sm">{meta.icon}</span>
          <span className="font-mono text-xs font-bold text-gray-200">{meta.label}</span>
          <span className="font-mono text-xs text-gray-600">{meta.role}</span>
        </div>
        <span
          className={`font-mono text-xs font-bold ${isCritical ? "animate-pulse text-red-400" : isLow ? "text-orange-400" : ""}`}
          style={{ color: isCritical ? undefined : isLow ? undefined : meta.color }}
        >
          {item.kg_remaining.toFixed(1)} kg
        </span>
      </div>

      {/* Progress bar */}
      <div
        className="mb-1 overflow-hidden rounded-sm"
        style={{ height: "6px", background: "rgba(0,0,0,0.5)", border: "1px solid #1f2937" }}
      >
        <div
          className={`h-full rounded-sm transition-all duration-700 ${isCritical ? "animate-pulse" : ""}`}
          style={{
            width: `${pct}%`,
            background: isCritical ? "#ef4444" : isLow ? "#f97316" : meta.color,
            boxShadow: `0 0 5px ${meta.color}66`,
          }}
        />
      </div>

      {/* Stats row */}
      <div className="flex justify-between font-mono text-xs text-gray-600">
        <span>{item.kcal_remaining.toLocaleString()} kcal</span>
        <span>{item.protein_g_remaining.toLocaleString()} g prot</span>
        <span style={{ color: isCritical ? "#f87171" : isLow ? "#fb923c" : "#6b7280" }}>
          {pct.toFixed(1)}%
        </span>
      </div>
    </div>
  )
}

export default function FoodInventory({ crew }: Props) {
  const inventory = crew?.food_inventory
  const foodTypes = inventory ? Object.keys(inventory) : []

  const totalKcal = foodTypes.reduce((s, t) => s + (inventory?.[t]?.kcal_remaining ?? 0), 0)
  const totalProtein = foodTypes.reduce((s, t) => s + (inventory?.[t]?.protein_g_remaining ?? 0), 0)
  const daysRemaining = crew?.stored_food.remaining_days_at_current_rate ?? 0

  return (
    <div
      className="overflow-hidden rounded-xl"
      style={{
        background: "rgba(0,10,5,0.92)",
        border: "1px solid #1f2937",
        backdropFilter: "blur(4px)",
      }}
    >
      {/* Title bar */}
      <div
        className="flex items-center justify-between px-3 py-1.5"
        style={{ background: "rgba(20,20,30,0.5)", borderBottom: "1px solid #1f2937" }}
      >
        <div className="flex items-center gap-2">
          <span className="text-base">🏭</span>
          <span className="font-mono text-xs font-bold tracking-widest text-green-400 uppercase">
            Food Inventory · Starting Rations
          </span>
        </div>
        <div className="flex items-center gap-4 font-mono text-xs text-gray-500">
          <span>{totalKcal.toLocaleString()} kcal</span>
          <span>{(totalProtein / 1000).toFixed(1)} kg prot</span>
          <span
            className={
              daysRemaining < 10
                ? "animate-pulse text-red-400"
                : daysRemaining < 30
                  ? "text-orange-400"
                  : "text-purple-400"
            }
          >
            {daysRemaining} days
          </span>
        </div>
      </div>

      {/* Food rows */}
      <div className="grid grid-cols-5 gap-2 p-3">
        {foodTypes.map((foodType) => (
          <FoodRow key={foodType} foodType={foodType} item={inventory![foodType]} />
        ))}
      </div>
    </div>
  )
}
