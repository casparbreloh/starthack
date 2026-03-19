import { motion } from "framer-motion"
import {
  Thermometer,
  Sun,
  CloudFog,
  Gauge,
  AlertTriangle,
  CheckCircle,
  Play,
  Pause,
  RotateCcw,
} from "lucide-react"
import { useState } from "react"

import marsLandscape from "@/assets/mars-landscape.png"
import { useActiveCrises, useScore, useWebSocketControls } from "@/hooks/useGameData"
import type { WeatherCurrent, SimStatus } from "@/types/game"

import { CrisisInjector } from "./CrisisInjector"
import { DifficultySelector } from "./DifficultySelector"

interface MarsOverviewProps {
  onSelectZone: (zone: string) => void
  onSelectCrew: () => void
  weather: WeatherCurrent
  sim: SimStatus
}

const HOTSPOTS = [
  { id: "zone_a", label: "ZONE A", x: "12%", y: "48%", w: "22%", h: "32%" },
  { id: "zone_b", label: "ZONE B", x: "70%", y: "50%", w: "20%", h: "30%" },
  { id: "zone_c", label: "ZONE C", x: "30%", y: "32%", w: "10%", h: "10%" },
  { id: "crew", label: "HABITAT", x: "50%", y: "35%", w: "16%", h: "16%" },
]

export function MarsOverview({ onSelectZone, onSelectCrew, weather, sim }: MarsOverviewProps) {
  const { data: crises = [] } = useActiveCrises()
  const { data: score } = useScore()
  const ws = useWebSocketControls()
  const [difficulty, setDifficulty] = useState("normal")

  const handleDifficultySelect = (d: string) => {
    setDifficulty(d)
    ws.reset({ difficulty: d })
  }

  const handleReset = () => {
    ws.reset({ difficulty })
  }

  return (
    <div className="relative h-full w-full overflow-hidden">
      {/* Background image */}
      <img
        src={marsLandscape}
        alt="Mars landscape with greenhouse domes"
        className="h-full w-full object-cover"
        draggable={false}
      />

      {/* Dark overlay for readability */}
      <div className="absolute inset-0 bg-gradient-to-t from-background/80 via-background/20 to-background/40" />

      {/* Clickable hotspots */}
      {HOTSPOTS.map((spot) => (
        <motion.button
          key={spot.id}
          onClick={() => (spot.id === "crew" ? onSelectCrew() : onSelectZone(spot.id))}
          className="group absolute cursor-pointer"
          style={{ left: spot.x, top: spot.y, width: spot.w, height: spot.h }}
          whileHover={{ scale: 1.02 }}
          whileTap={{ scale: 0.98 }}
        >
          {/* Label */}
          <motion.div
            initial={{ opacity: 0, y: 8 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ delay: 0.2 }}
            className="absolute bottom-0 left-1/2 -translate-x-1/2 translate-y-1/2 rounded-sm border border-border bg-card/90 px-3 py-1.5 opacity-0 backdrop-blur-sm transition-opacity duration-200 group-hover:opacity-100"
          >
            <span className="label-aerospace whitespace-nowrap text-primary">{spot.label}</span>
          </motion.div>
        </motion.button>
      ))}

      {/* Top-left: Mission info */}
      <motion.div
        initial={{ opacity: 0, y: -10 }}
        animate={{ opacity: 1, y: 0 }}
        className="absolute left-4 top-4 rounded-sm border border-border bg-card/80 px-4 py-3 backdrop-blur-sm"
      >
        <div className="mb-2 flex items-center gap-3">
          <span className="font-mono text-lg tracking-[0.2em] text-foreground">O A S I S</span>
        </div>
        <div className="flex items-center gap-4">
          <div className="flex items-center gap-1.5">
            <span className="label-aerospace">SOL</span>
            <span className="font-mono text-sm tabular-nums text-foreground">
              {sim.current_sol}
            </span>
          </div>
          <span className="text-border">|</span>
          <div className="flex items-center gap-1.5">
            <span className="label-aerospace">PHASE</span>
            <span className="font-mono text-[10px] text-primary">{sim.mission_phase}</span>
          </div>
        </div>
      </motion.div>

      {/* Top-right: Weather data */}
      <motion.div
        initial={{ opacity: 0, y: -10 }}
        animate={{ opacity: 1, y: 0 }}
        transition={{ delay: 0.1 }}
        className="absolute right-4 top-14 rounded-sm border border-border bg-card/80 px-4 py-3 backdrop-blur-sm"
      >
        <span className="label-aerospace mb-2 block">MARS WEATHER</span>
        <div className="flex flex-col gap-1.5">
          <div className="flex items-center gap-2">
            <Thermometer className="h-3.5 w-3.5 text-muted-foreground" />
            <span className="font-mono text-xs tabular-nums text-foreground">
              {weather.temp_max_c}°C
            </span>
          </div>
          <div className="flex items-center gap-2">
            <Gauge className="h-3.5 w-3.5 text-muted-foreground" />
            <span className="font-mono text-xs tabular-nums text-foreground">
              {weather.pressure_mbar} mbar
            </span>
          </div>
          <div className="flex items-center gap-2">
            <Sun className="h-3.5 w-3.5 text-muted-foreground" />
            <span className="font-mono text-xs tabular-nums text-foreground">
              {weather.solar_irradiance_w_m2} W/m²
            </span>
          </div>
          <div className="flex items-center gap-2">
            <CloudFog className="h-3.5 w-3.5 text-muted-foreground" />
            <span
              className={`font-mono text-xs tabular-nums ${weather.dust_opacity >= 1 ? "text-amber-alert" : "text-foreground"}`}
            >
              DUST {weather.dust_opacity < 0.5 ? "LOW" : weather.dust_opacity < 1 ? "MED" : "HIGH"}
            </span>
          </div>
        </div>
      </motion.div>

      {/* Bottom-right: Crisis dashboard */}
      <motion.div
        initial={{ opacity: 0, y: 10 }}
        animate={{ opacity: 1, y: 0 }}
        transition={{ delay: 0.2 }}
        className="absolute bottom-4 right-4 z-20 w-64 rounded-sm border border-border bg-card/80 px-4 py-3 backdrop-blur-sm"
      >
        <div className="mb-2 flex items-center justify-between">
          <span className="label-aerospace text-primary">CRISIS DASHBOARD</span>
          {score && (
            <span className="font-mono text-[10px] tabular-nums text-muted-foreground">
              SCORE {score.overall_score}
            </span>
          )}
        </div>
        {crises.length === 0 ? (
          <div className="flex items-center gap-2">
            <CheckCircle className="h-3.5 w-3.5 text-primary" />
            <span className="font-mono text-[10px] text-primary">ALL SYSTEMS NOMINAL</span>
          </div>
        ) : (
          <div className="flex flex-col gap-1.5">
            {crises.map((c, i) => (
              <div key={i} className="flex items-start gap-2">
                <AlertTriangle
                  className={`mt-px h-3.5 w-3.5 flex-shrink-0 ${c.severity === "critical" ? "animate-pulse text-destructive" : "text-amber-alert"}`}
                />
                <div className="flex flex-col">
                  <span
                    className={`font-mono text-[10px] font-bold ${c.severity === "critical" ? "text-destructive" : "text-amber-alert"}`}
                  >
                    {c.type.toUpperCase().replace(/_/g, " ")}
                  </span>
                  <span className="font-mono text-[9px] text-muted-foreground">
                    {c.threshold_breach}
                  </span>
                </div>
              </div>
            ))}
          </div>
        )}
        {score && (
          <>
            <div className="my-2 h-px bg-border" />
            <div className="grid grid-cols-2 gap-x-4 gap-y-1">
              <ScoreRow label="SURVIVAL" value={score.survival} />
              <ScoreRow label="NUTRITION" value={score.nutrition} />
              <ScoreRow label="RESOURCES" value={score.resource_efficiency} />
              <ScoreRow label="CRISIS MGT." value={score.crisis_management} />
            </div>
          </>
        )}
      </motion.div>

      {/* Top-center: Sim controls */}
      <motion.div
        initial={{ opacity: 0, y: -10 }}
        animate={{ opacity: 1, y: 0 }}
        transition={{ delay: 0.2 }}
        className="absolute inset-x-0 top-4 z-30 mx-auto flex w-fit items-center gap-4 rounded-sm border border-border bg-card/80 px-5 py-2 backdrop-blur-sm"
      >
        <span
          className={`label-aerospace ${ws.isPaused ? "text-muted-foreground" : "text-primary"}`}
        >
          {ws.isPaused ? "PAUSED" : "● RUNNING"}
        </span>
        <div className="h-4 w-px bg-border" />
        <DifficultySelector current={difficulty} onSelect={handleDifficultySelect} />
        <div className="h-4 w-px bg-border" />
        <button
          onClick={() => (ws.isPaused ? ws.resume() : ws.pause())}
          className="flex items-center gap-1.5 font-mono text-[10px] uppercase tracking-widest text-foreground transition-colors hover:text-primary"
        >
          {ws.isPaused ? <Play className="h-3 w-3" /> : <Pause className="h-3 w-3" />}
          {ws.isPaused ? "Run" : "Pause"}
        </button>
        <button
          onClick={handleReset}
          className="flex items-center gap-1.5 font-mono text-[10px] uppercase tracking-widest text-foreground transition-colors hover:text-primary"
        >
          <RotateCcw className="h-3 w-3" />
          Reset
        </button>
        <div className="h-4 w-px bg-border" />
        <CrisisInjector ws={ws} disabled={ws.isPaused || sim.mission_phase !== "active"} />
      </motion.div>
    </div>
  )
}

function ScoreRow({ label, value }: { label: string; value: number }) {
  const color = value >= 80 ? "text-primary" : value >= 50 ? "text-amber-alert" : "text-destructive"
  return (
    <div className="flex items-baseline justify-between">
      <span className="label-aerospace">{label}</span>
      <span className={`font-mono text-[10px] tabular-nums ${color}`}>{value}</span>
    </div>
  )
}
