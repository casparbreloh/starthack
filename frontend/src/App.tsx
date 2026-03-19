import { useState } from "react"
import { BrowserRouter, Route, Routes } from "react-router-dom"

import { Toaster as Sonner } from "@/components/ui/sonner"
import { Toaster } from "@/components/ui/toaster"
import { TooltipProvider } from "@/components/ui/tooltip"
import { GameDataProvider } from "@/hooks/useGameData"

import MetricsDashboard from "./components/MetricsDashboard"
import { useSimulation } from "./hooks/useSimulation"
import Index from "./pages/Index.tsx"
import NotFound from "./pages/NotFound.tsx"

type View = "game" | "dashboard"

function ViewSwitcher({ view, onSwitch }: { view: View; onSwitch: () => void }) {
  return (
    <button
      onClick={onSwitch}
      className="fixed right-4 top-3 z-50 flex items-center gap-2 rounded-md border border-border bg-card px-3 py-1.5 text-xs font-medium text-foreground shadow-md transition-colors hover:bg-secondary"
    >
      {view === "game" ? "Switch to Dashboard" : "Switch to Game View"}
    </button>
  )
}

function DashboardView({ onSwitch }: { onSwitch: () => void }) {
  const data = useSimulation()
  return (
    <div className="bg-void-bg h-screen overflow-hidden">
      <ViewSwitcher view="dashboard" onSwitch={onSwitch} />
      <MetricsDashboard data={data} />
    </div>
  )
}

const App = () => {
  const [view, setView] = useState<View>("game")
  const toggle = () => setView((v) => (v === "game" ? "dashboard" : "game"))

  return (
    <GameDataProvider>
      {view === "dashboard" ? (
        <DashboardView onSwitch={toggle} />
      ) : (
        <TooltipProvider>
          <Toaster />
          <Sonner />
          <ViewSwitcher view="game" onSwitch={toggle} />
          <BrowserRouter>
            <Routes>
              <Route path="/" element={<Index />} />
              <Route path="*" element={<NotFound />} />
            </Routes>
          </BrowserRouter>
        </TooltipProvider>
      )}
    </GameDataProvider>
  )
}

export default App
