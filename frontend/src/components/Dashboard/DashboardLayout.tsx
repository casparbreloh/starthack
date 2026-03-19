import type { ReactNode } from "react"

interface DashboardLayoutProps {
  topBar: ReactNode
  left: ReactNode
  center: ReactNode
  right: ReactNode
}

export default function DashboardLayout({ topBar, left, center, right }: DashboardLayoutProps) {
  return (
    <div className="flex h-screen flex-col">
      {/* Top bar */}
      {topBar}

      {/* Main grid */}
      <div className="mx-auto grid min-h-0 w-full max-w-[1800px] flex-1 grid-cols-1 gap-2.5 px-3 pb-3 xl:grid-cols-[420px_1fr_420px]">
        {/* Left column */}
        <div className="flex flex-col gap-2.5 overflow-y-auto">{left}</div>

        {/* Center zone — intentional negative space */}
        <div className="hidden items-center justify-center xl:flex">{center}</div>

        {/* Right column */}
        <div className="flex flex-col gap-2.5 overflow-y-auto">{right}</div>
      </div>
    </div>
  )
}
