import type { EventsLog } from "../../../types/simulation.ts"
import Panel from "../Panel.tsx"
import StatusDot from "../StatusDot.tsx"

interface EventFeedPanelProps {
  events: EventsLog | null
}

function mapEventSeverity(s: string): "ok" | "warn" | "critical" | "info" | "inactive" {
  if (s === "critical" || s === "error") return "critical"
  if (s === "warning") return "warn"
  if (s === "success") return "ok"
  return "info"
}

export default function EventFeedPanel({ events }: EventFeedPanelProps) {
  if (!events) {
    return (
      <Panel title="Events">
        <p className="text-void-text-muted text-sm">Awaiting events…</p>
      </Panel>
    )
  }

  const sorted = [...events.events].sort((a, b) => b.sol - a.sol).slice(0, 8)

  return (
    <Panel title="Events" subtitle={`${events.events.length}`}>
      <div className="-mr-1 max-h-[140px] overflow-y-auto pr-1">
        {sorted.length === 0 ? (
          <p className="text-void-text-tertiary text-sm">No events</p>
        ) : (
          sorted.map((evt, i) => (
            <div
              key={`${evt.sol}-${evt.type}-${i}`}
              className="border-void-border-subtle flex items-start gap-1.5 border-b py-1 last:border-0"
            >
              <StatusDot severity={mapEventSeverity(evt.severity)} className="mt-[3px]" />
              <div className="min-w-0 flex-1">
                <p className="text-void-text-secondary text-sm leading-tight">{evt.message}</p>
                <span className="text-void-text-muted font-mono text-xs">
                  SOL {evt.sol}
                  {evt.zone ? ` · ${evt.zone}` : ""}
                </span>
              </div>
            </div>
          ))
        )}
      </div>
    </Panel>
  )
}
