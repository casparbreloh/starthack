import { useState, useEffect, useRef } from "react";
import { useQueryClient } from "@tanstack/react-query";
import { useSimStatus, useWeather, useEnergy, useWater, useCrops, useCrewMembers, useCrewNutrition, useCrewHealth, useGreenhouseEnv, useNutrients } from "@/hooks/useGameData";
import { MarsOverview } from "@/components/game/MarsOverview";
import { GreenhouseDetailView } from "@/components/game/GreenhouseDetailView";
import { CrewDetailView } from "@/components/game/CrewDetailView";
import { AnimatePresence } from "framer-motion";
import { api } from "@/lib/api";

// How often a sol advances (ms)
const TICK_INTERVAL_MS = 2000;

type ViewState = { type: "overview" } | { type: "greenhouse"; zoneId: string } | { type: "crew" };

export function GameView() {
  const [view, setView] = useState<ViewState>({ type: "overview" });
  const queryClient = useQueryClient();
  const advancingRef = useRef(false);

  // Auto-advance the simulation by 1 sol every TICK_INTERVAL_MS
  useEffect(() => {
    const tick = async () => {
      if (advancingRef.current) return;
      advancingRef.current = true;
      try {
        await api.advanceSol(1);
        await queryClient.invalidateQueries();
      } catch {
        // simulation not running — ignore silently
      } finally {
        advancingRef.current = false;
      }
    };

    const id = setInterval(tick, TICK_INTERVAL_MS);
    return () => clearInterval(id);
  }, [queryClient]);

  const { data: sim } = useSimStatus();
  const { data: weather } = useWeather();
  const { data: energy } = useEnergy();
  const { data: water } = useWater();
  const { data: crops } = useCrops();
  const { data: crew } = useCrewMembers();
  const { data: nutrition } = useCrewNutrition();
  const { data: health } = useCrewHealth();
  const { data: zones } = useGreenhouseEnv();
  const { data: nutrients } = useNutrients();

  if (!sim || !weather || !crops || !crew || !nutrition || !health) {
    return (
      <div className="flex-1 flex items-center justify-center">
        <span className="font-mono text-muted-foreground animate-pulse">INITIALIZING SYSTEMS...</span>
      </div>
    );
  }

  const goBack = () => setView({ type: "overview" });

  return (
    <div className="flex-1 min-h-0 overflow-hidden">
      <AnimatePresence mode="wait">
        {view.type === "overview" && (
          <MarsOverview
            key="overview"
            onSelectZone={(z) => setView({ type: "greenhouse", zoneId: z })}
            onSelectCrew={() => setView({ type: "crew" })}
            weather={weather}
            sim={sim}
          />
        )}
        {view.type === "greenhouse" && (
          <GreenhouseDetailView
            key={`gh-${view.zoneId}`}
            zoneId={view.zoneId}
            crops={crops}
            zone={zones?.find((z) => z.zone_id === view.zoneId)}
            nutrients={nutrients?.find((n) => n.zone_id === view.zoneId)}
            onBack={goBack}
          />
        )}
        {view.type === "crew" && (
          <CrewDetailView
            key="crew"
            members={crew}
            nutrition={nutrition}
            health={health}
            onBack={goBack}
          />
        )}
      </AnimatePresence>
    </div>
  );
}
