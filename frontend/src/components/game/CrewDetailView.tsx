import { motion } from "framer-motion"
import { ArrowLeft, Heart, Droplets, Radiation } from "lucide-react"

import crewHabitat from "@/assets/crew-habitat.png"
import { num } from "@/lib/num"
import type { CrewMember, CrewNutrition, CrewHealth, AgentDecision } from "@/types/game"

import { AgentDecisionPanel } from "./AgentDecisionPanel"
import { MetricHistoryPanel } from "./MetricHistoryPanel"

interface CrewDetailViewProps {
  members: CrewMember[]
  nutrition: CrewNutrition
  health: CrewHealth
  agentDecision?: AgentDecision
  onBack: () => void
}

function statusColor(status: string): string {
  if (status === "nominal") return "bg-primary"
  if (status === "stressed") return "bg-amber-alert"
  return "bg-destructive"
}

function healthColor(pct: number): string {
  if (pct >= 80) return "text-primary"
  if (pct >= 50) return "text-amber-alert"
  return "text-destructive"
}

function barColor(pct: number): string {
  if (pct >= 80) return "bg-primary"
  if (pct >= 50) return "bg-amber-alert"
  return "bg-destructive"
}

// Position each crew member card roughly where astronauts appear in the image
const CREW_POSITIONS = [
  { bottom: "12%", left: "18%" },
  { bottom: "26%", left: "28%" },
  { bottom: "18%", left: "52%" },
  { bottom: "28%", left: "72%" },
]

export function CrewDetailView({
  members,
  nutrition,
  health,
  agentDecision,
  onBack,
}: CrewDetailViewProps) {
  const calPct = Math.round(
    (nutrition.daily_calories_consumed / nutrition.daily_calories_target) * 100,
  )
  const protPct = Math.round(
    (nutrition.daily_protein_consumed_g / nutrition.daily_protein_target_g) * 100,
  )

  return (
    <motion.div
      initial={{ opacity: 0 }}
      animate={{ opacity: 1 }}
      exit={{ opacity: 0 }}
      className="relative h-full w-full overflow-hidden"
    >
      {/* Background */}
      <img
        src={crewHabitat}
        alt="Crew habitat interior"
        className="h-full w-full object-cover"
        draggable={false}
      />
      <div className="absolute inset-0 bg-background/40" />

      {/* Back button */}
      <motion.button
        initial={{ opacity: 0, x: -10 }}
        animate={{ opacity: 1, x: 0 }}
        onClick={onBack}
        className="absolute left-4 top-4 z-30 flex items-center gap-2 rounded-sm border border-border bg-card/80 px-3 py-2 backdrop-blur-sm transition-colors hover:bg-card"
      >
        <ArrowLeft className="h-4 w-4 text-foreground" />
        <span className="label-aerospace">BACK</span>
      </motion.button>

      {/* Title + mission charts dropdown */}
      <motion.div
        initial={{ opacity: 0, y: -10 }}
        animate={{ opacity: 1, y: 0 }}
        className="absolute inset-x-0 top-4 z-20 flex flex-col items-center gap-1"
      >
        <div className="rounded-sm border border-border bg-card/80 px-6 py-2 backdrop-blur-sm">
          <span className="font-mono text-lg tracking-[0.2em] text-foreground">CREW HABITAT</span>
        </div>
        <MetricHistoryPanel />
      </motion.div>

      {/* Crew member cards */}
      {members.map((m, i) => (
        <motion.div
          key={m.name}
          initial={{ opacity: 0, y: 20 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ delay: 0.1 + i * 0.08 }}
          className="absolute z-10 w-44 rounded-sm border border-border bg-card/85 px-3 py-2.5 backdrop-blur-sm"
          style={CREW_POSITIONS[i]}
        >
          <div className="mb-2 flex items-center gap-2">
            <div
              className={`h-2 w-2 rounded-full ${statusColor(m.status)} ${m.status !== "nominal" ? "animate-pulse" : ""}`}
            />
            <span className="font-mono text-[10px] tracking-wider text-foreground">{m.name}</span>
          </div>
          <div className="flex flex-col gap-1.5">
            <div className="flex items-center gap-1.5">
              <Heart className="h-3 w-3 text-muted-foreground" />
              <div className="h-1.5 flex-1 overflow-hidden rounded-sm bg-secondary">
                <div
                  className={`h-full rounded-sm transition-all duration-500 ${barColor(m.health_pct)}`}
                  style={{ width: `${m.health_pct}%` }}
                />
              </div>
              <span
                className={`w-8 text-right font-mono text-[9px] tabular-nums ${healthColor(m.health_pct)}`}
              >
                {m.health_pct}%
              </span>
            </div>
            <div className="flex items-center gap-1.5">
              <Droplets className="h-3 w-3 text-muted-foreground" />
              <div className="h-1.5 flex-1 overflow-hidden rounded-sm bg-secondary">
                <div
                  className={`h-full rounded-sm transition-all duration-500 ${barColor(m.hydration_pct)}`}
                  style={{ width: `${m.hydration_pct}%` }}
                />
              </div>
              <span className="w-8 text-right font-mono text-[9px] tabular-nums text-foreground">
                {m.hydration_pct}%
              </span>
            </div>
            <div className="flex items-center gap-1.5">
              <Radiation className="h-3 w-3 text-muted-foreground" />
              <span className="font-mono text-[9px] tabular-nums text-muted-foreground">
                {m.radiation_msv} mSv
              </span>
            </div>
          </div>
        </motion.div>
      ))}

      {/* Right panel: Nutrition + Food inventory */}
      <motion.div
        initial={{ opacity: 0, x: 20 }}
        animate={{ opacity: 1, x: 0 }}
        transition={{ delay: 0.2 }}
        className="absolute right-4 top-20 z-20 flex w-56 flex-col gap-3 rounded-sm border border-border bg-card/80 px-4 py-3 backdrop-blur-sm"
      >
        {/* Daily intake */}
        <div>
          <span className="label-aerospace mb-2 block text-primary">NUTRITION</span>
          <div className="flex flex-col gap-2">
            <div>
              <div className="mb-0.5 flex items-baseline justify-between">
                <span className="label-aerospace">CALORIES</span>
                <span className="font-mono text-xs tabular-nums text-foreground">{calPct}%</span>
              </div>
              <div className="h-1.5 overflow-hidden rounded-sm bg-secondary">
                <div
                  className={`h-full rounded-sm transition-all duration-500 ${barColor(calPct)}`}
                  style={{ width: `${Math.min(100, calPct)}%` }}
                />
              </div>
              <span className="font-mono text-[9px] text-muted-foreground">
                {num(nutrition.daily_calories_consumed).toFixed(0)} /{" "}
                {num(nutrition.daily_calories_target).toFixed(0)} kcal
              </span>
            </div>
            <div>
              <div className="mb-0.5 flex items-baseline justify-between">
                <span className="label-aerospace">PROTEIN</span>
                <span className="font-mono text-xs tabular-nums text-foreground">{protPct}%</span>
              </div>
              <div className="h-1.5 overflow-hidden rounded-sm bg-secondary">
                <div
                  className={`h-full rounded-sm transition-all duration-500 ${barColor(protPct)}`}
                  style={{ width: `${Math.min(100, protPct)}%` }}
                />
              </div>
              <span className="font-mono text-[9px] text-muted-foreground">
                {num(nutrition.daily_protein_consumed_g).toFixed(0)} /{" "}
                {num(nutrition.daily_protein_target_g).toFixed(0)} g
              </span>
            </div>
          </div>
        </div>

        <div className="h-px bg-border" />

        {/* Food supply summary */}
        <div>
          <span className="label-aerospace mb-1.5 block text-primary">FOOD SUPPLY</span>
          <div className="flex flex-col gap-1.5">
            <div className="flex items-baseline justify-between">
              <span className="label-aerospace">FROM GREENHOUSE</span>
              <span className="font-mono text-xs tabular-nums text-primary">
                {num(nutrition.greenhouse_food_pct).toFixed(1)}%
              </span>
            </div>
            <div className="flex items-baseline justify-between">
              <span className="label-aerospace">FROM STORES</span>
              <span className="font-mono text-xs tabular-nums text-foreground">
                {num(nutrition.stored_food_pct).toFixed(1)}%
              </span>
            </div>
            <div className="flex items-baseline justify-between">
              <span className="label-aerospace">DAYS OF FOOD</span>
              <span
                className={`font-mono text-xs tabular-nums ${nutrition.days_of_food_remaining > 60 ? "text-primary" : nutrition.days_of_food_remaining > 20 ? "text-amber-alert" : "text-destructive"}`}
              >
                {typeof nutrition.days_of_food_remaining === "number"
                  ? num(nutrition.days_of_food_remaining).toFixed(0)
                  : "—"}
              </span>
            </div>
          </div>
        </div>

        {/* Food inventory breakdown */}
        {nutrition.food_inventory && Object.keys(nutrition.food_inventory).length > 0 && (
          <>
            <div className="h-px bg-border" />
            <div>
              <span className="label-aerospace mb-1.5 block text-primary">FOOD INVENTORY</span>
              <div className="flex flex-col gap-1.5">
                {Object.entries(nutrition.food_inventory).map(([type, kg]) => (
                  <div key={type} className="flex items-baseline justify-between">
                    <span className="label-aerospace">{type.toUpperCase()}</span>
                    <span
                      className={`font-mono text-xs tabular-nums ${(kg as number) > 5 ? "text-primary" : (kg as number) > 1 ? "text-amber-alert" : "text-destructive"}`}
                    >
                      {num(kg).toFixed(1)} kg
                    </span>
                  </div>
                ))}
              </div>
            </div>
          </>
        )}
      </motion.div>

      {/* Left panel: Agent Decision */}
      <div className="absolute left-4 top-20 z-20 flex flex-col gap-3">
        <AgentDecisionPanel decision={agentDecision} />

        {/* Overall crew health */}
        <motion.div
          initial={{ opacity: 0, x: -20 }}
          animate={{ opacity: 1, x: 0 }}
          transition={{ delay: 0.2 }}
          className="w-48 rounded-sm border border-border bg-card/80 px-4 py-3 backdrop-blur-sm"
        >
          <span className="label-aerospace mb-2 block text-primary">CREW STATUS</span>
          <div className="flex flex-col gap-1.5">
            <div className="flex items-baseline justify-between">
              <span className="label-aerospace">HEALTH</span>
              <span
                className={`font-mono text-xs tabular-nums ${healthColor(health.overall_health_pct)}`}
              >
                {health.overall_health_pct}%
              </span>
            </div>
            <div className="flex items-baseline justify-between">
              <span className="label-aerospace">HYDRATION</span>
              <span className="font-mono text-xs tabular-nums text-foreground">
                {health.hydration_pct}%
              </span>
            </div>
            <div className="flex items-baseline justify-between">
              <span className="label-aerospace">RADIATION</span>
              <span className="font-mono text-xs tabular-nums text-foreground">
                {health.radiation_cumulative_msv} mSv
              </span>
            </div>
            <div className="flex items-baseline justify-between">
              <span className="label-aerospace">CO₂ IMPACT</span>
              <span className="font-mono text-xs tabular-nums text-foreground">
                {(num(health.co2_impact) * 100).toFixed(0)}%
              </span>
            </div>
            {health.illness && (
              <div className="flex items-baseline justify-between">
                <span className="label-aerospace">ILLNESS</span>
                <span className="font-mono text-xs tabular-nums text-destructive">
                  {health.illness}
                </span>
              </div>
            )}
          </div>
        </motion.div>
      </div>
    </motion.div>
  )
}
