import { useState } from 'react'
import { useSimulation } from './hooks/useSimulation'
import MetricsDashboard from './components/MetricsDashboard'
import GameView from './components/GameView'

type View = 'game' | 'metrics'

export default function App() {
  const [view, setView] = useState<View>('game')
  const data = useSimulation()
  const { running, toggleRunning } = data

  return (
    <div
      className="min-h-screen"
      style={{ background: '#020706', color: '#e5e7eb' }}
    >
      {/* Nav */}
      <nav
        className="sticky top-0 z-50 flex items-center gap-2 px-4 py-2"
        style={{
          background: 'rgba(2,7,6,0.95)',
          borderBottom: '1px solid #065f46',
          backdropFilter: 'blur(8px)',
        }}
      >
        <span className="text-green-400 font-mono font-bold text-sm tracking-widest mr-4">🌿 MARS GH</span>

        {(['game', 'metrics'] as const).map(v => (
          <button
            key={v}
            onClick={() => setView(v)}
            className="px-4 py-1.5 rounded-lg text-xs font-mono font-bold uppercase tracking-widest transition-all duration-200 cursor-pointer"
            style={{
              background: view === v ? 'rgba(21,128,61,0.3)' : 'transparent',
              border: `1px solid ${view === v ? '#15803d' : '#1f2937'}`,
              color: view === v ? '#4ade80' : '#6b7280',
              boxShadow: view === v ? '0 0 10px #15803d44' : 'none',
            }}
          >
            {v === 'game' ? '◉ Station View' : '≡ Metrics'}
          </button>
        ))}

        {/* Simulation controls */}
        <div className="ml-auto flex items-center gap-3">
          {data.status && (
            <span className="text-xs font-mono text-gray-500">
              SOL <span className="text-green-400 font-bold">{data.status.current_sol}</span>
              <span className="text-gray-600"> / {data.status.total_sols}</span>
            </span>
          )}

          <button
            onClick={toggleRunning}
            className="px-3 py-1 rounded text-xs font-mono font-bold uppercase tracking-widest transition-all duration-200 cursor-pointer"
            style={{
              background: running ? 'rgba(21,128,61,0.2)' : 'rgba(180,83,9,0.2)',
              border: `1px solid ${running ? '#15803d' : '#b45309'}`,
              color: running ? '#4ade80' : '#fbbf24',
              boxShadow: running ? '0 0 8px #15803d44' : '0 0 8px #b4530944',
            }}
          >
            {running ? '⏸ Pause' : '▶ Run'}
          </button>

          <div
            className={`w-2 h-2 rounded-full ${data.loading ? 'bg-yellow-400 animate-pulse' : data.error ? 'bg-red-500' : running ? 'bg-green-500 animate-pulse' : 'bg-gray-500'}`}
            style={{ boxShadow: data.error ? '0 0 6px #ef4444' : running ? '0 0 6px #22c55e' : 'none' }}
          />
          <span className="text-xs font-mono text-gray-600">
            {data.loading ? 'CONNECTING' : data.error ? 'OFFLINE' : running ? 'RUNNING' : 'PAUSED'}
          </span>
        </div>
      </nav>

      {/* View */}
      {view === 'game' ? (
        <GameView data={data} />
      ) : (
        <div style={{ background: '#030a06' }}>
          <MetricsDashboard data={data} />
        </div>
      )}
    </div>
  )
}
