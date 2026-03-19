interface MetricRowProps {
  label: string
  value: string | number | null
  unit?: string
  sublabel?: string
  dimValue?: boolean
}

export default function MetricRow({ label, value, unit, sublabel, dimValue }: MetricRowProps) {
  return (
    <div className="flex items-baseline justify-between gap-3 py-[4px]">
      <div className="min-w-0 shrink">
        <span className="text-void-text-secondary text-sm font-medium leading-none">{label}</span>
        {sublabel && (
          <span className="text-void-text-tertiary ml-1.5 text-xs leading-none">{sublabel}</span>
        )}
      </div>
      <div className="shrink-0 text-right font-mono text-[15px] font-semibold leading-none">
        {value === null ? (
          <span className="text-void-text-muted">—</span>
        ) : (
          <>
            <span className={dimValue ? "text-void-text-tertiary" : "text-void-text-primary"}>
              {typeof value === "number" ? formatNum(value) : value}
            </span>
            {unit && (
              <span className="text-void-text-tertiary ml-0.5 text-xs font-medium">{unit}</span>
            )}
          </>
        )}
      </div>
    </div>
  )
}

function formatNum(n: number): string {
  if (Number.isInteger(n) && Math.abs(n) < 10000) return String(n)
  if (Math.abs(n) >= 10000) return n.toLocaleString("en-US", { maximumFractionDigits: 0 })
  return n.toFixed(1)
}
