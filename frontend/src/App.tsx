import MetricsDashboard from "./components/MetricsDashboard"
import { useSimulation } from "./hooks/useSimulation"

export default function App() {
  const data = useSimulation()
  return (
    <div className="bg-void-bg h-screen overflow-hidden">
      <MetricsDashboard data={data} />
    </div>
  )
}
