import { useState } from "react";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { BrowserRouter, Route, Routes } from "react-router-dom";
import { Toaster as Sonner } from "@/components/ui/sonner";
import { Toaster } from "@/components/ui/toaster";
import { TooltipProvider } from "@/components/ui/tooltip";
import Index from "./pages/Index.tsx";
import NotFound from "./pages/NotFound.tsx";
import MetricsDashboard from "./components/MetricsDashboard";
import { useSimulation } from "./hooks/useSimulation";

const queryClient = new QueryClient();

type View = "game" | "dashboard";

function ViewSwitcher({ view, onSwitch }: { view: View; onSwitch: () => void }) {
  return (
    <button
      onClick={onSwitch}
      className="fixed top-3 right-4 z-50 flex items-center gap-2 rounded-md border border-border bg-card px-3 py-1.5 text-xs font-medium text-foreground shadow-md transition-colors hover:bg-secondary"
    >
      {view === "game" ? "Switch to Dashboard" : "Switch to Game View"}
    </button>
  );
}

function DashboardView({ onSwitch }: { onSwitch: () => void }) {
  const data = useSimulation();
  return (
    <div className="bg-void-bg h-screen overflow-hidden">
      <ViewSwitcher view="dashboard" onSwitch={onSwitch} />
      <MetricsDashboard data={data} />
    </div>
  );
}

const App = () => {
  const [view, setView] = useState<View>("game");
  const toggle = () => setView((v) => (v === "game" ? "dashboard" : "game"));

  if (view === "dashboard") {
    return <DashboardView onSwitch={toggle} />;
  }

  return (
    <QueryClientProvider client={queryClient}>
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
    </QueryClientProvider>
  );
};

export default App;
