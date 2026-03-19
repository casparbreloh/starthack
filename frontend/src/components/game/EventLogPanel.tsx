import { motion } from "framer-motion"

import type { EventLogEntry } from "@/types/game"

interface EventLogPanelProps {
  events: EventLogEntry[]
  currentSol: number
}

function severityColor(severity: string): string {
  if (severity === "critical") return "text-destructive font-bold"
  if (severity === "warning") return "text-amber-alert font-semibold"
  return "text-muted-foreground"
}

export function EventLogPanel({ events, currentSol }: EventLogPanelProps) {
  const recent = events.slice(-5).reverse()

  return (
    <div className="flex flex-col gap-1.5">
      {recent.map((e, i) => (
        <motion.div
          key={`${e.sol}-${e.message}-${i}`}
          initial={{ opacity: 0, x: 8 }}
          animate={{ opacity: 1, x: 0 }}
          transition={{ delay: i * 0.04 }}
          className="flex items-center gap-2"
        >
          <span className="label-aerospace shrink-0 text-muted-foreground">
            S{e.sol} {String(14 - i * 1).padStart(2, "0")}:{String(20 - i * 15).padStart(2, "0")}:
          </span>
          <span className={`truncate font-mono text-[11px] ${severityColor(e.severity)}`}>
            {e.message}
          </span>
        </motion.div>
      ))}
    </div>
  )
}
