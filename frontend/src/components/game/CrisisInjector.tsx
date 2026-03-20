import { AnimatePresence, motion } from "framer-motion"
import { Bug, CloudFog, Droplets, Thermometer, Zap, ChevronDown, ChevronRight } from "lucide-react"
import { useState } from "react"

import { useCrops } from "@/hooks/useGameData"
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
  const [pathogenOpen, setPathogenOpen] = useState(false)
  const { data: crops = [] } = useCrops()

  const inject = (scenarioId: string) => {
    ws.injectCrisis(scenarioId)
    setOpen(false)
    setPathogenOpen(false)
  }

  const injectPathogen = (cropId: string) => {
    ws.injectCrisis("pathogen", { crop_id: cropId })
    setOpen(false)
    setPathogenOpen(false)
  }

  const handleClose = () => {
    setOpen(false)
    setPathogenOpen(false)
  }

  return (
    <div className="relative">
      <button
        onClick={() => {
          setOpen(!open)
          setPathogenOpen(false)
        }}
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
            className="absolute left-0 top-full z-50 mt-2 flex flex-col gap-0.5 rounded-sm border border-border bg-card p-1.5"
          >
            {SCENARIOS.map((s) => {
              if (s.id === "pathogen") {
                return (
                  <div key={s.id} className="relative">
                    <button
                      onClick={() => setPathogenOpen(!pathogenOpen)}
                      disabled={disabled}
                      className="flex w-full items-center gap-2 rounded-sm px-3 py-1.5 text-left transition-colors hover:bg-muted disabled:opacity-40"
                    >
                      <s.icon className={`h-3 w-3 flex-shrink-0 ${s.color}`} />
                      <span
                        className={`whitespace-nowrap font-mono text-[10px] font-bold tracking-widest ${s.color}`}
                      >
                        {s.label}
                      </span>
                      <ChevronRight
                        className={`ml-auto h-3 w-3 text-muted-foreground transition-transform ${pathogenOpen ? "rotate-90" : ""}`}
                      />
                    </button>
                    <AnimatePresence>
                      {pathogenOpen && (
                        <motion.div
                          initial={{ opacity: 0, x: -4 }}
                          animate={{ opacity: 1, x: 0 }}
                          exit={{ opacity: 0, x: -4 }}
                          className="absolute left-full top-0 ml-1 flex flex-col gap-0.5 rounded-sm border border-border bg-card p-1.5"
                        >
                          <span className="px-3 py-1 font-mono text-[9px] uppercase tracking-widest text-muted-foreground">
                            SELECT CROP
                          </span>
                          {crops.length === 0 ? (
                            <span className="px-3 py-1.5 font-mono text-[9px] text-muted-foreground">
                              No crops available
                            </span>
                          ) : (
                            crops.map((crop) => (
                              <button
                                key={crop.crop_id}
                                onClick={() => injectPathogen(crop.crop_id)}
                                className="flex items-center gap-2 rounded-sm px-3 py-1.5 text-left transition-colors hover:bg-muted"
                              >
                                <Bug className="h-3 w-3 flex-shrink-0 text-red-400" />
                                <div className="flex flex-col">
                                  <span className="whitespace-nowrap font-mono text-[10px] font-bold tracking-widest text-red-400">
                                    {crop.crop_type.toUpperCase()}
                                  </span>
                                  <span className="font-mono text-[8px] text-muted-foreground">
                                    {crop.zone_id.toUpperCase()} · {crop.crop_id}
                                  </span>
                                </div>
                              </button>
                            ))
                          )}
                        </motion.div>
                      )}
                    </AnimatePresence>
                  </div>
                )
              }

              return (
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
              )
            })}

            <div className="mt-0.5 border-t border-border pt-0.5">
              <button
                onClick={handleClose}
                className="w-full rounded-sm px-3 py-1 font-mono text-[9px] uppercase tracking-widest text-muted-foreground transition-colors hover:bg-muted"
              >
                Cancel
              </button>
            </div>
          </motion.div>
        )}
      </AnimatePresence>
    </div>
  )
}
