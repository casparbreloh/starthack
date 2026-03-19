import { motion } from "framer-motion";
import marsLandscape from "@/assets/mars-landscape.png";
import type { WeatherCurrent, SimStatus } from "@/types/game";
import { Thermometer, Sun, CloudFog, Gauge, AlertTriangle, CheckCircle } from "lucide-react";
import { useActiveCrises, useScore } from "@/hooks/useGameData";

interface MarsOverviewProps {
  onSelectZone: (zone: string) => void;
  onSelectCrew: () => void;
  weather: WeatherCurrent;
  sim: SimStatus;
}

const HOTSPOTS = [
  { id: "zone_a", label: "ZONE A", x: "12%", y: "48%", w: "22%", h: "32%" },
  { id: "zone_b", label: "ZONE B", x: "70%", y: "50%", w: "20%", h: "30%" },
  { id: "zone_c", label: "ZONE C", x: "30%", y: "32%", w: "10%", h: "10%" },
  { id: "crew", label: "HABITAT", x: "50%", y: "35%", w: "16%", h: "16%" },
];

export function MarsOverview({ onSelectZone, onSelectCrew, weather, sim }: MarsOverviewProps) {
  const { data: crises = [] } = useActiveCrises();
  const { data: score } = useScore();

  return (
    <div className="relative w-full h-full overflow-hidden">
      {/* Background image */}
      <img
        src={marsLandscape}
        alt="Mars landscape with greenhouse domes"
        className="w-full h-full object-cover"
        draggable={false}
      />

      {/* Dark overlay for readability */}
      <div className="absolute inset-0 bg-gradient-to-t from-background/80 via-background/20 to-background/40" />

      {/* Clickable hotspots */}
      {HOTSPOTS.map((spot) => (
        <motion.button
          key={spot.id}
          onClick={() => spot.id === "crew" ? onSelectCrew() : onSelectZone(spot.id)}
          className="absolute group cursor-pointer"
          style={{ left: spot.x, top: spot.y, width: spot.w, height: spot.h }}
          whileHover={{ scale: 1.02 }}
          whileTap={{ scale: 0.98 }}
        >
          {/* Label */}
          <motion.div
            initial={{ opacity: 0, y: 8 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ delay: 0.2 }}
            className="absolute bottom-0 left-1/2 -translate-x-1/2 translate-y-1/2 bg-card/90 backdrop-blur-sm border border-border rounded-sm px-3 py-1.5 opacity-0 group-hover:opacity-100 transition-opacity duration-200"
          >
            <span className="label-aerospace text-primary whitespace-nowrap">{spot.label}</span>
          </motion.div>
        </motion.button>
      ))}

      {/* Top-left: Mission info */}
      <motion.div
        initial={{ opacity: 0, y: -10 }}
        animate={{ opacity: 1, y: 0 }}
        className="absolute top-4 left-4 bg-card/80 backdrop-blur-sm border border-border rounded-sm px-4 py-3"
      >
        <div className="flex items-center gap-3 mb-2">
          <span className="font-mono text-lg tracking-[0.2em] text-foreground">A R E S I A</span>
        </div>
        <div className="flex items-center gap-4">
          <div className="flex items-center gap-1.5">
            <span className="label-aerospace">SOL</span>
            <span className="font-mono text-sm tabular-nums text-foreground">{sim.current_sol}</span>
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
        className="absolute top-14 right-4 bg-card/80 backdrop-blur-sm border border-border rounded-sm px-4 py-3"
      >
        <span className="label-aerospace block mb-2">MARS WEATHER</span>
        <div className="flex flex-col gap-1.5">
          <div className="flex items-center gap-2">
            <Thermometer className="w-3.5 h-3.5 text-muted-foreground" />
            <span className="font-mono text-xs tabular-nums text-foreground">{weather.temp_max_c}°C</span>
          </div>
          <div className="flex items-center gap-2">
            <Gauge className="w-3.5 h-3.5 text-muted-foreground" />
            <span className="font-mono text-xs tabular-nums text-foreground">{weather.pressure_mbar} mbar</span>
          </div>
          <div className="flex items-center gap-2">
            <Sun className="w-3.5 h-3.5 text-muted-foreground" />
            <span className="font-mono text-xs tabular-nums text-foreground">{weather.solar_irradiance_w_m2} W/m²</span>
          </div>
          <div className="flex items-center gap-2">
            <CloudFog className="w-3.5 h-3.5 text-muted-foreground" />
            <span className={`font-mono text-xs tabular-nums ${weather.dust_opacity >= 1 ? "text-amber-alert" : "text-foreground"}`}>
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
        className="absolute bottom-4 right-4 bg-card/80 backdrop-blur-sm border border-border rounded-sm px-4 py-3 z-20 w-64"
      >
        <div className="flex items-center justify-between mb-2">
          <span className="label-aerospace text-primary">CRISIS DASHBOARD</span>
          {score && (
            <span className="font-mono text-[10px] tabular-nums text-muted-foreground">SCORE {score.overall_score}</span>
          )}
        </div>
        {crises.length === 0 ? (
          <div className="flex items-center gap-2">
            <CheckCircle className="w-3.5 h-3.5 text-primary" />
            <span className="font-mono text-[10px] text-primary">ALL SYSTEMS NOMINAL</span>
          </div>
        ) : (
          <div className="flex flex-col gap-1.5">
            {crises.map((c, i) => (
              <div key={i} className="flex items-start gap-2">
                <AlertTriangle className={`w-3.5 h-3.5 mt-px flex-shrink-0 ${c.severity === "critical" ? "text-destructive animate-pulse" : "text-amber-alert"}`} />
                <div className="flex flex-col">
                  <span className={`font-mono text-[10px] font-bold ${c.severity === "critical" ? "text-destructive" : "text-amber-alert"}`}>
                    {c.type.toUpperCase().replace(/_/g, " ")}
                  </span>
                  <span className="font-mono text-[9px] text-muted-foreground">{c.threshold_breach}</span>
                </div>
              </div>
            ))}
          </div>
        )}
        {score && (
          <>
            <div className="h-px bg-border my-2" />
            <div className="grid grid-cols-2 gap-x-4 gap-y-1">
              <ScoreRow label="SURVIVAL" value={score.survival} />
              <ScoreRow label="NUTRITION" value={score.nutrition} />
              <ScoreRow label="RESOURCES" value={score.resource_efficiency} />
              <ScoreRow label="CRISIS MGT." value={score.crisis_management} />
            </div>
          </>
        )}
      </motion.div>

      {/* Bottom: Status bar */}
      <motion.div
        initial={{ opacity: 0, y: -10 }}
        animate={{ opacity: 1, y: 0 }}
        transition={{ delay: 0.2 }}
        className="absolute top-4 inset-x-0 mx-auto w-fit bg-card/80 backdrop-blur-sm border border-border rounded-sm px-6 py-2 flex items-center gap-6"
      >
        <span className="label-aerospace text-primary">● ONLINE</span>
      </motion.div>
    </div>
  );
}

function ScoreRow({ label, value }: { label: string; value: number }) {
  const color = value >= 80 ? "text-primary" : value >= 50 ? "text-amber-alert" : "text-destructive";
  return (
    <div className="flex justify-between items-baseline">
      <span className="label-aerospace">{label}</span>
      <span className={`font-mono text-[10px] tabular-nums ${color}`}>{value}</span>
    </div>
  );
}
