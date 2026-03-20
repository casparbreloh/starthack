import { useState } from "react"
import { BrowserRouter, Route, Routes } from "react-router-dom"

import { ErrorBoundary } from "@/components/ErrorBoundary"
import TrainingSuite from "@/components/TrainingSuite/TrainingSuite"
import { Toaster as Sonner } from "@/components/ui/sonner"
import { Toaster } from "@/components/ui/toaster"
import { TooltipProvider } from "@/components/ui/tooltip"
import { GameDataProvider, useOrchestratorState } from "@/hooks/useGameData"
import { isOrchestratorMode } from "@/hooks/useGameSession"

import Index from "./pages/Index.tsx"
import NotFound from "./pages/NotFound.tsx"

type View = "game" | "training"

function ViewSwitcher({ view, onSwitch }: { view: View; onSwitch: () => void }) {
  return (
    <button
      onClick={onSwitch}
      className="fixed right-4 top-3 z-50 flex items-center gap-2 rounded-md border border-border bg-card px-3 py-1.5 text-xs font-medium text-foreground shadow-md transition-colors hover:bg-secondary"
    >
      {view === "game" ? "Switch to Training" : "Switch to Game View"}
    </button>
  )
}

function TrainingView({ onSwitch }: { onSwitch: () => void }) {
  return (
    <div className="h-screen overflow-hidden bg-background">
      <ViewSwitcher view="training" onSwitch={onSwitch} />
      <TrainingSuite />
    </div>
  )
}

// ── Orchestrator loading gate ────────────────────────────────────────────────

function OrchestratorGate({ children }: { children: React.ReactNode }) {
  const orch = useOrchestratorState()

  // Not in orchestrator mode — render immediately
  if (!orch) return <>{children}</>

  // Session is ready (ws connected) — render the game
  if (orch.wsUrl) return <>{children}</>

  // Error state
  if (orch.error) {
    return (
      <div className="flex h-screen flex-col items-center justify-center gap-4 bg-background">
        <p className="font-mono text-sm text-destructive">{orch.error}</p>
        <button
          type="button"
          onClick={() => orch.startSession()}
          className="rounded border border-primary/30 bg-primary/10 px-6 py-2 font-mono text-sm font-semibold text-primary transition-colors hover:bg-primary/20"
        >
          Retry
        </button>
      </div>
    )
  }

  // Starting — show spinner
  if (orch.isStarting) {
    return (
      <div className="flex h-screen flex-col items-center justify-center gap-3 bg-background">
        <div className="h-8 w-8 animate-spin rounded-full border-2 border-muted-foreground border-t-primary" />
        <p className="font-mono text-sm text-muted-foreground">
          Starting simulation{orch.status === "starting" ? " container" : ""}...
        </p>
        <p className="font-mono text-xs text-muted-foreground/60">This may take 30-60 seconds</p>
      </div>
    )
  }

  // Idle — waiting for the user to start a session
  return (
    <div className="flex h-screen flex-col items-center justify-center gap-4 bg-background">
      <h1 className="font-mono text-lg font-bold tracking-[0.2em] text-foreground">OASIS</h1>
      <p className="font-mono text-sm text-muted-foreground">Launch a simulation to begin</p>
      <button
        type="button"
        onClick={() => orch.startSession()}
        className="rounded border border-primary/30 bg-primary/10 px-6 py-2 font-mono text-sm font-semibold text-primary transition-colors hover:bg-primary/20"
      >
        Start Simulation
      </button>
    </div>
  )
}

// ── App ──────────────────────────────────────────────────────────────────────

const App = () => {
  const [view, setView] = useState<View>(isOrchestratorMode() ? "game" : "game")
  const toggle = () => setView((v) => (v === "game" ? "training" : "game"))

  return (
    <ErrorBoundary>
      <GameDataProvider>
        {view === "training" ? (
          <TrainingView onSwitch={toggle} />
        ) : (
          <TooltipProvider>
            <Toaster />
            <Sonner />
            <ViewSwitcher view="game" onSwitch={toggle} />
            <OrchestratorGate>
              <BrowserRouter>
                <Routes>
                  <Route path="/" element={<Index />} />
                  <Route path="*" element={<NotFound />} />
                </Routes>
              </BrowserRouter>
            </OrchestratorGate>
          </TooltipProvider>
        )}
      </GameDataProvider>
    </ErrorBoundary>
  )
}

export default App
