import { AnimatePresence, motion } from "framer-motion"
import { Bug, CloudFog, Droplets, Thermometer, Zap, ChevronDown } from "lucide-react"
import { useState } from "react"

import type { WebSocketState } from "@/hooks/useWebSocket"

interface CrisisInjectorProps {
  ws: WebSocketState
  disabled?: boolean
}

const SCENARIOS = [
  { id: "water_leak", label: "WATER LEAK", icon: Droplets, color: "text-blue-400" },
  { id: "hvac_failure", label: "HVAC FAILURE", icon: Thermometer, color: "text-amber-400" },
  { id: "pathogen", label: "PATHOGEN", icon: Bug, color: "text-red-400" },
  { id: "dust_storm", label: "DUST STORM", icon: CloudFog, color: "text-orange-400" },
  { id: "energy_disruption", label: "ENERGY LOSS", icon: Zap, color: "text-yellow-400" },
] as const

export function CrisisInjector({ ws, disabled }: CrisisInjectorProps) {
  const [open, setOpen] = useState(false)

  const inject = (scenarioId: string) => {
    ws.injectCrisis(scenarioId)
    setOpen(false)
  }

  return (
    <div className="relative">
      <button
        onClick={() => setOpen(!open)}
        className="flex items-center gap-1.5 font-mono text-[10px] uppercase tracking-widest text-destructive transition-colors hover:text-red-300"
      >
        <Zap className="h-3 w-3" />
        INJECT
        <ChevronDown
          className={`h-3 w-3 text-muted-foreground transition-transform ${open ? "rotate-180" : ""}`}
        />
      </button>

      <AnimatePresence>
        {open && (
          <motion.div
            initial={{ opacity: 0, y: -4 }}
            animate={{ opacity: 1, y: 0 }}
            exit={{ opacity: 0, y: -4 }}
            className="absolute left-0 top-full mt-2 flex flex-col gap-0.5 rounded-sm border border-border bg-card p-1.5"
          >
            {SCENARIOS.map((s) => (
              <button
                key={s.id}
                onClick={() => inject(s.id)}
                disabled={disabled}
                className="flex items-center gap-2 rounded-sm px-3 py-1.5 text-left transition-colors hover:bg-muted disabled:opacity-40"
              >
                <s.icon className={`h-3 w-3 flex-shrink-0 ${s.color}`} />
                <span
                  className={`whitespace-nowrap font-mono text-[10px] font-bold tracking-widest ${s.color}`}
                >
                  {s.label}
                </span>
              </button>
            ))}
          </motion.div>
        )}
      </AnimatePresence>
    </div>
  )
}
