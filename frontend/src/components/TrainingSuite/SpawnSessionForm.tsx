import { useCallback, useState } from "react"

import type { TrainingConfig } from "@/types/orchestrator"

const DIFFICULTY_OPTIONS = ["easy", "normal", "hard", "extreme"]

interface SpawnSessionFormProps {
  onSubmit: (config: TrainingConfig) => void
  onCancel: () => void
}

export default function SpawnSessionForm({ onSubmit, onCancel }: SpawnSessionFormProps) {
  const [difficulty, setDifficulty] = useState("normal")
  const [seed, setSeed] = useState("")
  const [missionSols, setMissionSols] = useState("450")

  const handleSubmit = useCallback(
    (e: React.FormEvent) => {
      e.preventDefault()
      const config: TrainingConfig = {
        difficulty,
        mission_sols: Number(missionSols) || 450,
      }
      if (seed.trim() !== "") {
        config.seed = Number(seed)
      }
      onSubmit(config)
    },
    [difficulty, seed, missionSols, onSubmit],
  )

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/60 backdrop-blur-sm">
      <form onSubmit={handleSubmit} className="surface-card w-full max-w-md space-y-5 p-6">
        <h2 className="font-mono text-sm font-bold uppercase tracking-[0.15em] text-foreground">
          New Training Session
        </h2>

        {/* Difficulty */}
        <div className="space-y-1.5">
          <label htmlFor="difficulty" className="label-aerospace block">
            Difficulty
          </label>
          <select
            id="difficulty"
            value={difficulty}
            onChange={(e) => setDifficulty(e.target.value)}
            className="w-full rounded border border-border bg-secondary px-3 py-2 font-mono text-sm text-foreground outline-none focus:border-ring"
          >
            {DIFFICULTY_OPTIONS.map((opt) => (
              <option key={opt} value={opt}>
                {opt.charAt(0).toUpperCase() + opt.slice(1)}
              </option>
            ))}
          </select>
        </div>

        {/* Seed */}
        <div className="space-y-1.5">
          <label htmlFor="seed" className="label-aerospace block">
            Seed (optional)
          </label>
          <input
            id="seed"
            type="number"
            value={seed}
            onChange={(e) => setSeed(e.target.value)}
            placeholder="Random"
            className="w-full rounded border border-border bg-secondary px-3 py-2 font-mono text-sm text-foreground outline-none placeholder:text-muted-foreground focus:border-ring"
          />
        </div>

        {/* Mission SOLs */}
        <div className="space-y-1.5">
          <label htmlFor="mission-sols" className="label-aerospace block">
            Mission SOLs
          </label>
          <input
            id="mission-sols"
            type="number"
            value={missionSols}
            onChange={(e) => setMissionSols(e.target.value)}
            min={1}
            max={1000}
            className="w-full rounded border border-border bg-secondary px-3 py-2 font-mono text-sm text-foreground outline-none focus:border-ring"
          />
        </div>

        {/* Actions */}
        <div className="flex gap-3 pt-1">
          <button
            type="submit"
            className="flex-1 rounded border border-primary/30 bg-primary/10 px-4 py-2 font-mono text-sm font-semibold text-primary transition-colors hover:bg-primary/20"
          >
            Start Training
          </button>
          <button
            type="button"
            onClick={onCancel}
            className="rounded border border-border px-4 py-2 font-mono text-sm text-muted-foreground transition-colors hover:bg-secondary"
          >
            Cancel
          </button>
        </div>
      </form>
    </div>
  )
}
