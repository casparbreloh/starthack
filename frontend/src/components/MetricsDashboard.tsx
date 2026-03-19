import type { SimulationControls } from "../hooks/useSimulation.ts"
import type { SimStatus, ScoreData } from "../types/simulation.ts"
import GreenhouseMap from "./Dashboard/center/GreenhouseMap.tsx"
import DashboardLayout from "./Dashboard/DashboardLayout.tsx"
import CrewHealthPanel from "./Dashboard/left/CrewHealthPanel.tsx"
import CrewNutritionPanel from "./Dashboard/left/CrewNutritionPanel.tsx"
import CrewSurvivalPanel from "./Dashboard/left/CrewSurvivalPanel.tsx"
import CrisesPanel from "./Dashboard/left/CrisesPanel.tsx"
import EnergyPanel from "./Dashboard/right/EnergyPanel.tsx"
import EventFeedPanel from "./Dashboard/right/EventFeedPanel.tsx"
import WaterPanel from "./Dashboard/right/WaterPanel.tsx"

interface MetricsDashboardProps {
  data: SimulationControls
}

export default function MetricsDashboard({ data }: MetricsDashboardProps) {
  return (
    <DashboardLayout
      topBar={
        <TopBar
          status={data.status}
          score={data.score}
          running={data.running}
          toggleRunning={data.toggleRunning}
          loading={data.loading}
          error={data.error}
        />
      }
      left={
        <>
          <CrewSurvivalPanel crewHealth={data.crewHealth} />
          <CrewNutritionPanel crew={data.crew} />
          <CrewHealthPanel crewMembers={data.crewMembers} />
          <CrisesPanel crises={data.crises} />
        </>
      }
      center={<GreenhouseMap crops={data.crops} />}
      right={
        <>
          <WaterPanel water={data.water} />
          <EnergyPanel energy={data.energy} />
          <EventFeedPanel events={data.events} />
        </>
      }
    />
  )
}

/* -- Top bar: SOL + score + sim controls -- */

function TopBar({
  status,
  score,
  running,
  toggleRunning,
  loading,
  error,
}: {
  status: SimStatus | null
  score: ScoreData | null
  running: boolean
  toggleRunning: () => void
  loading: boolean
  error: string | null
}) {
  return (
    <div className="border-void-border-subtle relative flex items-center border-b px-4 py-5">
      {/* Left: phase + score */}
      <div className="flex items-center gap-4">
        {status?.mission_phase && (
          <span className="text-void-text-muted text-sm font-semibold tracking-[0.15em] uppercase">
            {status.mission_phase}
          </span>
        )}
        {score && (
          <span className="text-void-text-secondary font-mono text-sm font-semibold">
            Score <span className="text-void-text-primary">{score.scores.overall_score}</span>
          </span>
        )}
      </div>

      {/* Center: SOL title */}
      <div className="pointer-events-none absolute inset-x-0 flex justify-center">
        <div className="flex items-baseline gap-2">
          <span className="text-void-text-primary font-mono text-5xl leading-none font-extralight tracking-tight">
            {status?.current_sol ?? "\u2014"}
          </span>
          <span className="text-void-text-tertiary font-mono text-base leading-none">
            / 450 SOL
          </span>
        </div>
      </div>

      {/* Right: sim controls */}
      <div className="ml-auto flex items-center gap-3">
        <button
          onClick={toggleRunning}
          className="text-void-text-tertiary hover:text-void-text-secondary cursor-pointer font-mono text-sm font-semibold tracking-[0.15em] uppercase transition-colors"
        >
          {running ? "Pause" : "Run"}
        </button>
        <span
          className={`inline-block h-1.5 w-1.5 rounded-full ${loading ? "animate-pulse bg-yellow-500/60" : error ? "bg-red-500/60" : running ? "animate-pulse bg-green-500/40" : "bg-void-text-muted"}`}
        />
      </div>
    </div>
  )
}
