import { motion } from "framer-motion";
import { ArrowLeft, Heart, Droplets, Radiation, Utensils } from "lucide-react";
import crewHabitat from "@/assets/crew-habitat.png";
import type { CrewMember, CrewNutrition, CrewHealth } from "@/types/game";

interface CrewDetailViewProps {
  members: CrewMember[];
  nutrition: CrewNutrition;
  health: CrewHealth;
  onBack: () => void;
}

function statusColor(status: string): string {
  if (status === "nominal") return "bg-primary";
  if (status === "stressed") return "bg-amber-alert";
  return "bg-destructive";
}

function healthColor(pct: number): string {
  if (pct >= 80) return "text-primary";
  if (pct >= 50) return "text-amber-alert";
  return "text-destructive";
}

function barColor(pct: number): string {
  if (pct >= 80) return "bg-primary";
  if (pct >= 50) return "bg-amber-alert";
  return "bg-destructive";
}

// Position each crew member card roughly where astronauts appear in the image
const CREW_POSITIONS = [
  { bottom: "16%", left: "18%" },
  { bottom: "30%", left: "28%" },
  { bottom: "22%", left: "52%" },
  { bottom: "32%", left: "72%" },
];

export function CrewDetailView({ members, nutrition, health, onBack }: CrewDetailViewProps) {
  const calPct = Math.round((nutrition.daily_calories_consumed / nutrition.daily_calories_target) * 100);
  const protPct = Math.round((nutrition.daily_protein_consumed_g / nutrition.daily_protein_target_g) * 100);

  return (
    <motion.div
      initial={{ opacity: 0 }}
      animate={{ opacity: 1 }}
      exit={{ opacity: 0 }}
      className="relative w-full h-full overflow-hidden"
    >
      {/* Background */}
      <img
        src={crewHabitat}
        alt="Crew habitat interior"
        className="w-full h-full object-cover"
        draggable={false}
      />
      <div className="absolute inset-0 bg-background/40" />

      {/* Back button */}
      <motion.button
        initial={{ opacity: 0, x: -10 }}
        animate={{ opacity: 1, x: 0 }}
        onClick={onBack}
        className="absolute top-4 left-4 bg-card/80 backdrop-blur-sm border border-border rounded-sm px-3 py-2 flex items-center gap-2 hover:bg-card transition-colors z-20"
      >
        <ArrowLeft className="w-4 h-4 text-foreground" />
        <span className="label-aerospace">BACK</span>
      </motion.button>

      {/* Title */}
      <motion.div
        initial={{ opacity: 0, y: -10 }}
        animate={{ opacity: 1, y: 0 }}
        className="absolute top-4 inset-x-0 mx-auto w-fit bg-card/80 backdrop-blur-sm border border-border rounded-sm px-6 py-2 z-20"
      >
        <span className="font-mono text-lg tracking-[0.2em] text-foreground">CREW HABITAT</span>
      </motion.div>

      {/* Crew member cards */}
      {members.map((m, i) => (
        <motion.div
          key={m.name}
          initial={{ opacity: 0, y: 20 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ delay: 0.1 + i * 0.08 }}
          className="absolute bg-card/85 backdrop-blur-sm border border-border rounded-sm px-3 py-2.5 z-10 w-44"
          style={CREW_POSITIONS[i]}
        >
          <div className="flex items-center gap-2 mb-2">
            <div className={`w-2 h-2 rounded-full ${statusColor(m.status)} ${m.status !== "nominal" ? "animate-pulse" : ""}`} />
            <span className="font-mono text-[10px] text-foreground tracking-wider">{m.name}</span>
          </div>
          <div className="flex flex-col gap-1.5">
            <div className="flex items-center gap-1.5">
              <Heart className="w-3 h-3 text-muted-foreground" />
              <div className="h-1.5 flex-1 bg-secondary rounded-sm overflow-hidden">
                <div className={`h-full rounded-sm transition-all duration-500 ${barColor(m.health_pct)}`} style={{ width: `${m.health_pct}%` }} />
              </div>
              <span className={`font-mono text-[9px] tabular-nums w-8 text-right ${healthColor(m.health_pct)}`}>{m.health_pct}%</span>
            </div>
            <div className="flex items-center gap-1.5">
              <Droplets className="w-3 h-3 text-muted-foreground" />
              <div className="h-1.5 flex-1 bg-secondary rounded-sm overflow-hidden">
                <div className={`h-full rounded-sm transition-all duration-500 ${barColor(m.hydration_pct)}`} style={{ width: `${m.hydration_pct}%` }} />
              </div>
              <span className="font-mono text-[9px] tabular-nums text-foreground w-8 text-right">{m.hydration_pct}%</span>
            </div>
            <div className="flex items-center gap-1.5">
              <Radiation className="w-3 h-3 text-muted-foreground" />
              <span className="font-mono text-[9px] tabular-nums text-muted-foreground">{m.radiation_msv} mSv</span>
            </div>
          </div>
        </motion.div>
      ))}

      {/* Right panel: Nutrition + Food inventory */}
      <motion.div
        initial={{ opacity: 0, x: 20 }}
        animate={{ opacity: 1, x: 0 }}
        transition={{ delay: 0.2 }}
        className="absolute top-20 right-4 bg-card/80 backdrop-blur-sm border border-border rounded-sm px-4 py-3 z-20 w-56 flex flex-col gap-3"
      >
        {/* Daily intake */}
        <div>
          <span className="label-aerospace block mb-2 text-primary">NUTRITION</span>
          <div className="flex flex-col gap-2">
            <div>
              <div className="flex justify-between items-baseline mb-0.5">
                <span className="label-aerospace">CALORIES</span>
                <span className="font-mono text-xs tabular-nums text-foreground">{calPct}%</span>
              </div>
              <div className="h-1.5 bg-secondary rounded-sm overflow-hidden">
                <div className={`h-full rounded-sm transition-all duration-500 ${barColor(calPct)}`} style={{ width: `${Math.min(100, calPct)}%` }} />
              </div>
              <span className="font-mono text-[9px] text-muted-foreground">{nutrition.daily_calories_consumed.toFixed(0)} / {nutrition.daily_calories_target.toFixed(0)} kcal</span>
            </div>
            <div>
              <div className="flex justify-between items-baseline mb-0.5">
                <span className="label-aerospace">PROTEIN</span>
                <span className="font-mono text-xs tabular-nums text-foreground">{protPct}%</span>
              </div>
              <div className="h-1.5 bg-secondary rounded-sm overflow-hidden">
                <div className={`h-full rounded-sm transition-all duration-500 ${barColor(protPct)}`} style={{ width: `${Math.min(100, protPct)}%` }} />
              </div>
              <span className="font-mono text-[9px] text-muted-foreground">{nutrition.daily_protein_consumed_g.toFixed(0)} / {nutrition.daily_protein_target_g.toFixed(0)} g</span>
            </div>
          </div>
        </div>

        <div className="h-px bg-border" />

        {/* Food supply summary */}
        <div>
          <span className="label-aerospace block mb-1.5 text-primary">FOOD SUPPLY</span>
          <div className="flex flex-col gap-1.5">
            <div className="flex justify-between items-baseline">
              <span className="label-aerospace">FROM GREENHOUSE</span>
              <span className="font-mono text-xs tabular-nums text-primary">{nutrition.greenhouse_food_pct.toFixed(1)}%</span>
            </div>
            <div className="flex justify-between items-baseline">
              <span className="label-aerospace">FROM STORES</span>
              <span className="font-mono text-xs tabular-nums text-foreground">{nutrition.stored_food_pct.toFixed(1)}%</span>
            </div>
            <div className="flex justify-between items-baseline">
              <span className="label-aerospace">DAYS OF FOOD</span>
              <span className={`font-mono text-xs tabular-nums ${nutrition.days_of_food_remaining > 60 ? "text-primary" : nutrition.days_of_food_remaining > 20 ? "text-amber-alert" : "text-destructive"}`}>
                {typeof nutrition.days_of_food_remaining === "number" ? nutrition.days_of_food_remaining.toFixed(0) : "—"}
              </span>
            </div>
          </div>
        </div>

        {/* Food inventory breakdown */}
        {nutrition.food_inventory && Object.keys(nutrition.food_inventory).length > 0 && (
          <>
            <div className="h-px bg-border" />
            <div>
              <span className="label-aerospace block mb-1.5 text-primary">FOOD INVENTORY</span>
              <div className="flex flex-col gap-1.5">
                {Object.entries(nutrition.food_inventory).map(([type, kg]) => (
                  <div key={type} className="flex justify-between items-baseline">
                    <span className="label-aerospace">{type.toUpperCase()}</span>
                    <span className={`font-mono text-xs tabular-nums ${(kg as number) > 5 ? "text-primary" : (kg as number) > 1 ? "text-amber-alert" : "text-destructive"}`}>
                      {typeof kg === "number" ? kg.toFixed(1) : "0.0"} kg
                    </span>
                  </div>
                ))}
              </div>
            </div>
          </>
        )}
      </motion.div>

      {/* Left panel: Overall crew health */}
      <motion.div
        initial={{ opacity: 0, x: -20 }}
        animate={{ opacity: 1, x: 0 }}
        transition={{ delay: 0.2 }}
        className="absolute top-20 left-4 bg-card/80 backdrop-blur-sm border border-border rounded-sm px-4 py-3 z-20 w-48"
      >
        <span className="label-aerospace block mb-2 text-primary">CREW STATUS</span>
        <div className="flex flex-col gap-1.5">
          <div className="flex justify-between items-baseline">
            <span className="label-aerospace">HEALTH</span>
            <span className={`font-mono text-xs tabular-nums ${healthColor(health.overall_health_pct)}`}>{health.overall_health_pct}%</span>
          </div>
          <div className="flex justify-between items-baseline">
            <span className="label-aerospace">HYDRATION</span>
            <span className="font-mono text-xs tabular-nums text-foreground">{health.hydration_pct}%</span>
          </div>
          <div className="flex justify-between items-baseline">
            <span className="label-aerospace">RADIATION</span>
            <span className="font-mono text-xs tabular-nums text-foreground">{health.radiation_cumulative_msv} mSv</span>
          </div>
          <div className="flex justify-between items-baseline">
            <span className="label-aerospace">CO₂ IMPACT</span>
            <span className="font-mono text-xs tabular-nums text-foreground">{(health.co2_impact * 100).toFixed(0)}%</span>
          </div>
          {health.illness && (
            <div className="flex justify-between items-baseline">
              <span className="label-aerospace">ILLNESS</span>
              <span className="font-mono text-xs tabular-nums text-destructive">{health.illness}</span>
            </div>
          )}
        </div>
      </motion.div>
    </motion.div>
  );
}
