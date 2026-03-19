import type { ReactNode } from "react"

export type Severity = "ok" | "warn" | "critical"

interface PanelProps {
  title: string
  subtitle?: string
  severity?: Severity
  children: ReactNode
}

const severityAccent: Record<Severity, string> = {
  ok: "var(--color-void-ok-dim)",
  warn: "var(--color-void-warn-dim)",
  critical: "var(--color-void-critical-dim)",
}

export default function Panel({ title, subtitle, severity, children }: PanelProps) {
  return (
    <section
      className="border-void-border bg-void-surface hover:border-void-surface-hover rounded-xl border transition-colors duration-300"
      style={severity ? { borderTopColor: severityAccent[severity], borderTopWidth: 2 } : undefined}
    >
      {/* Header */}
      <div className="flex items-baseline gap-3 px-5 pt-4 pb-2.5">
        <h3 className="text-void-text-secondary text-sm leading-none font-bold tracking-[0.06em] uppercase">
          {title}
        </h3>
        {subtitle && <p className="text-void-text-tertiary text-sm leading-none">{subtitle}</p>}
      </div>

      {/* Divider */}
      <div className="bg-void-border-subtle mx-5 h-px" />

      {/* Content */}
      <div className="px-5 pt-3 pb-4">{children}</div>
    </section>
  )
}
