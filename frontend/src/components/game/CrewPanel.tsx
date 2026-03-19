import { motion } from "framer-motion";
import type { CrewMember } from "@/types/game";

interface CrewPanelProps {
  members: CrewMember[];
  nutrition: {
    daily_calories_consumed: number;
    daily_calories_target: number;
  };
}

function statusColor(status: string): string {
  if (status === "nominal") return "bg-primary";
  if (status === "stressed") return "bg-amber-alert";
  return "bg-destructive";
}

function barColor(pct: number): string {
  if (pct >= 80) return "bg-primary";
  if (pct >= 50) return "bg-amber-alert";
  return "bg-destructive";
}

export function CrewPanel({ members, nutrition }: CrewPanelProps) {
  return (
    <div className="flex flex-col gap-3">
      {members.map((m, i) => (
        <motion.div
          key={m.name}
          initial={{ opacity: 0, x: -8 }}
          animate={{ opacity: 1, x: 0 }}
          transition={{ delay: i * 0.06, type: "spring", stiffness: 400, damping: 30 }}
          className="flex items-center gap-3"
        >
          <span className="label-aerospace w-28 truncate">{m.name}</span>
          <div className={`w-2 h-2 rounded-full ${statusColor(m.status)} ${m.status !== "nominal" ? "animate-pulse-slow" : ""}`} />
          <div className="h-1.5 flex-1 bg-secondary rounded-sm overflow-hidden max-w-[80px]">
            <div
              className={`h-full rounded-sm transition-all duration-500 ${barColor(m.health_pct)}`}
              style={{ width: `${m.health_pct}%` }}
            />
          </div>
          <span className="font-mono text-[10px] tabular-nums text-muted-foreground w-24">
            {nutrition.daily_calories_consumed.toLocaleString()} / {nutrition.daily_calories_target.toLocaleString()} kcal
          </span>
        </motion.div>
      ))}
    </div>
  );
}
