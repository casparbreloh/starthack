import { AnimatePresence, motion } from "framer-motion"
import { ChevronDown, Shield, Skull, Swords } from "lucide-react"
import { useState } from "react"

interface DifficultySelectorProps {
  current: string
  onSelect: (difficulty: string) => void
}

const DIFFICULTIES = [
  { id: "easy", label: "EASY", icon: Shield, color: "text-primary" },
  { id: "normal", label: "NORMAL", icon: Swords, color: "text-amber-alert" },
  { id: "hard", label: "HARD", icon: Skull, color: "text-destructive" },
] as const

export function DifficultySelector({ current, onSelect }: DifficultySelectorProps) {
  const [open, setOpen] = useState(false)
  const active = DIFFICULTIES.find((d) => d.id === current) ?? DIFFICULTIES[1]

  return (
    <div className="relative">
      <button
        onClick={() => setOpen(!open)}
        className="flex items-center gap-1.5 font-mono text-[10px] uppercase tracking-widest text-foreground transition-colors hover:text-primary"
      >
        <active.icon className={`h-3 w-3 ${active.color}`} />
        {active.label}
        <ChevronDown
          className={`h-3 w-3 text-muted-foreground transition-transform ${open ? "rotate-180" : ""}`}
        />
      </button>

      <AnimatePresence>
        {open && (
          <motion.div
            initial={{ opacity: 0, y: -4 }}
            animate={{ opacity: 1, y: 0 }}
            exit={{ opacity: 0, y: -4 }}
            className="absolute left-0 top-full mt-2 flex flex-col gap-0.5 rounded-sm border border-border bg-card p-1.5"
          >
            {DIFFICULTIES.map((d) => (
              <button
                key={d.id}
                onClick={() => {
                  onSelect(d.id)
                  setOpen(false)
                }}
                className={`flex items-center gap-2 rounded-sm px-3 py-1.5 text-left transition-colors hover:bg-muted ${d.id === current ? "bg-muted" : ""}`}
              >
                <d.icon className={`h-3 w-3 ${d.color}`} />
                <span className={`font-mono text-[10px] font-bold tracking-widest ${d.color}`}>
                  {d.label}
                </span>
              </button>
            ))}
          </motion.div>
        )}
      </AnimatePresence>
    </div>
  )
}
