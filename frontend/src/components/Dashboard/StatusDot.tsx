type DotSeverity = "ok" | "warn" | "critical" | "info" | "inactive"

interface StatusDotProps {
  severity: DotSeverity
  active?: boolean
  className?: string
}

const dotColor: Record<DotSeverity, string> = {
  ok: "var(--color-void-ok)",
  warn: "var(--color-void-warn)",
  critical: "var(--color-void-critical)",
  info: "var(--color-void-accent-dim)",
  inactive: "var(--color-void-text-muted)",
}

const glowColor: Record<DotSeverity, string> = {
  ok: "0 0 5px var(--color-void-ok-dim)",
  warn: "0 0 5px var(--color-void-warn-dim)",
  critical: "0 0 5px var(--color-void-critical-dim)",
  info: "0 0 5px var(--color-void-accent-muted)",
  inactive: "none",
}

export default function StatusDot({ severity, active, className }: StatusDotProps) {
  return (
    <span
      className={`inline-block h-[7px] w-[7px] shrink-0 rounded-full ${className ?? ""}`}
      style={{
        background: dotColor[severity],
        boxShadow: active ? glowColor[severity] : "none",
      }}
    />
  )
}
