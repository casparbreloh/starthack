import { AnimatePresence } from "framer-motion"
import { useState } from "react"

import { CrewDetailView } from "@/components/game/CrewDetailView"
import { GreenhouseDetailView } from "@/components/game/GreenhouseDetailView"
import { MarsOverview } from "@/components/game/MarsOverview"
import {
  useSimStatus,
  useWeather,
  useCrops,
  useCrewMembers,
  useCrewNutrition,
  useCrewHealth,
  useGreenhouseEnv,
  useNutrients,
} from "@/hooks/useGameData"

type ViewState = { type: "overview" } | { type: "greenhouse"; zoneId: string } | { type: "crew" }

export function GameView() {
  const [view, setView] = useState<ViewState>({ type: "overview" })

  const { data: sim } = useSimStatus()
  const { data: weather } = useWeather()
  const { data: crops } = useCrops()
  const { data: crew } = useCrewMembers()
  const { data: nutrition } = useCrewNutrition()
  const { data: health } = useCrewHealth()
  const { data: zones } = useGreenhouseEnv()
  const { data: nutrients } = useNutrients()

  if (!sim || !weather || !crops || !crew || !nutrition || !health) {
    return (
      <div className="flex flex-1 items-center justify-center">
        <span className="animate-pulse font-mono text-muted-foreground">
          INITIALIZING SYSTEMS...
        </span>
      </div>
    )
  }

  const goBack = () => setView({ type: "overview" })

  return (
    <div className="min-h-0 flex-1 overflow-hidden">
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
  )
}
