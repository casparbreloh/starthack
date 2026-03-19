import { motion } from "framer-motion"

// Simple sparkline showing a mock yield trend
const MOCK_YIELD_DATA = [12, 15, 14, 18, 22, 20, 25, 28, 26, 30, 32, 35]

export function YieldTrend() {
  const max = Math.max(...MOCK_YIELD_DATA)
  const min = Math.min(...MOCK_YIELD_DATA)
  const range = max - min || 1

  const points = MOCK_YIELD_DATA.map((d, i) => {
    const x = (i / (MOCK_YIELD_DATA.length - 1)) * 140
    const y = 50 - ((d - min) / range) * 40
    return `${x},${y}`
  }).join(" ")

  return (
    <div className="flex flex-col gap-2">
      <span className="label-aerospace">YIELD TREND</span>
      <svg className="h-14 w-full" viewBox="0 0 140 55" preserveAspectRatio="none">
        <defs>
          <linearGradient id="yieldGrad" x1="0" y1="0" x2="0" y2="1">
            <stop offset="0%" stopColor="hsl(142,70%,45%)" stopOpacity="0.3" />
            <stop offset="100%" stopColor="hsl(142,70%,45%)" stopOpacity="0" />
          </linearGradient>
        </defs>
        <polygon points={`0,55 ${points} 140,55`} fill="url(#yieldGrad)" />
        <motion.polyline
          points={points}
          fill="none"
          stroke="hsl(142,70%,45%)"
          strokeWidth="1.5"
          vectorEffect="non-scaling-stroke"
          initial={{ pathLength: 0 }}
          animate={{ pathLength: 1 }}
          transition={{ duration: 1.2 }}
        />
      </svg>
      <div className="flex justify-between">
        <span className="label-aerospace">S260</span>
        <span className="label-aerospace">S340</span>
      </div>
    </div>
  )
}
