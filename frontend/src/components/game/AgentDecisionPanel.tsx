import { useState } from "react"
import { motion, AnimatePresence } from "framer-motion"
import { ChevronDown, Bot } from "lucide-react"
import type { AgentDecision } from "@/types/game"

interface AgentDecisionPanelProps {
  decision: AgentDecision | undefined
}

export function AgentDecisionPanel({ decision }: AgentDecisionPanelProps) {
  const [open, setOpen] = useState(false)

  const summary = decision?.summary || ""

  return (
    <motion.div
      initial={{ opacity: 0, x: -20 }}
      animate={{ opacity: 1, x: 0 }}
      transition={{ delay: 0.25 }}
      className="w-64 rounded-sm border border-border bg-card/80 backdrop-blur-sm"
    >
      {/* Header / Toggle button */}
      <button
        onClick={() => setOpen((v) => !v)}
        className="flex w-full items-center justify-between px-4 py-3 transition-colors hover:bg-card/60"
      >
        <div className="flex items-center gap-2">
          <Bot className="h-3.5 w-3.5 text-muted-foreground" />
          <span className="label-aerospace text-primary">AI AGENT</span>
        </div>
        <ChevronDown
          className={`h-3 w-3 text-muted-foreground transition-transform duration-200 ${open ? "rotate-180" : ""}`}
        />
      </button>

      {/* Expanded detail */}
      <AnimatePresence>
        {open && (
          <motion.div
            initial={{ height: 0, opacity: 0 }}
            animate={{ height: "auto", opacity: 1 }}
            exit={{ height: 0, opacity: 0 }}
            transition={{ duration: 0.2 }}
            className="overflow-hidden border-t border-border"
          >
            <div className="px-4 py-3">
              {decision ? (
                <>
                  <span className="block mb-2 font-mono text-xs tracking-widest text-primary">
                    DECISION FOR SOL {decision.sol}:
                  </span>
                  <p className="font-mono text-xs leading-relaxed text-foreground">
                    {summary || "No summary available."}
                  </p>
                </>
              ) : (
                <p className="font-mono text-xs text-muted-foreground">
                  AWAITING FIRST AGENT CONSULTATION…
                </p>
              )}
            </div>
          </motion.div>
        )}
      </AnimatePresence>
    </motion.div>
  )
}
