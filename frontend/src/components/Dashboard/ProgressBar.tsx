import type { Severity } from "./Panel.tsx"

interface ProgressBarProps {
  value: number
  severity?: Severity
  className?: string
}

const severityFill: Record<Severity, string> = {
  ok: "var(--color-void-ok)",
  warn: "var(--color-void-warn)",
  critical: "var(--color-void-critical)",
}

export default function ProgressBar({ value, severity, className }: ProgressBarProps) {
  const clamped = Math.max(0, Math.min(100, value))
  const fill = severity ? severityFill[severity] : "var(--color-void-accent-dim)"

  return (
    <div
      className={`h-[8px] w-full overflow-hidden rounded-full ${className ?? ""}`}
      style={{ background: "var(--color-void-border)" }}
    >
      <div
        className="h-full rounded-full transition-all duration-500 ease-out"
        style={{ width: `${clamped}%`, background: fill }}
      />
    </div>
  )
}
