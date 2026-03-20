// @vitest-environment jsdom

import type { ReactNode } from "react"
import { act } from "react"
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest"

import { renderElement } from "@/test/reactHarness"

const mockUseOrchestratorState = vi.fn()
const mockUseWebSocketControls = vi.fn()

vi.mock("@/hooks/useGameData", () => ({
  GameDataProvider: ({ children }: { children: ReactNode }) => children,
  useOrchestratorState: () => mockUseOrchestratorState(),
  useWebSocketControls: () => mockUseWebSocketControls(),
}))

const startSession = vi.fn()

describe("OrchestratorGate", () => {
  beforeEach(() => {
    mockUseOrchestratorState.mockReset()
    mockUseWebSocketControls.mockReset()
    startSession.mockReset()
  })

  afterEach(() => {
    vi.clearAllMocks()
  })

  it("shows a connection loading state until the first tick arrives", async () => {
    const { OrchestratorGate } = await import("./App")

    mockUseOrchestratorState.mockReturnValue({
      wsUrl: "wss://example.cloudfront.net/ws/run-123",
      sessionId: "run-123",
      status: "running",
      isStarting: false,
      error: null,
      startSession,
    })
    mockUseWebSocketControls.mockReturnValue({
      lastState: null,
      error: null,
    })

    const { container, unmount } = await renderElement(
      <OrchestratorGate>
        <div>ready</div>
      </OrchestratorGate>,
    )

    expect(container.textContent).toContain("Connecting to simulation...")
    expect(container.textContent).not.toContain("ready")

    await unmount()
  })

  it("shows websocket failures instead of hanging on the initializing screen", async () => {
    const { OrchestratorGate } = await import("./App")

    mockUseOrchestratorState.mockReturnValue({
      wsUrl: "wss://example.cloudfront.net/ws/run-123",
      sessionId: "run-123",
      status: "running",
      isStarting: false,
      error: null,
      startSession,
    })
    mockUseWebSocketControls.mockReturnValue({
      lastState: null,
      error: "Unable to connect to the simulation.",
    })

    const { container, unmount } = await renderElement(
      <OrchestratorGate>
        <div>ready</div>
      </OrchestratorGate>,
    )

    expect(container.textContent).toContain("Unable to connect to the simulation.")
    expect(container.textContent).not.toContain("ready")

    await act(async () => {
      const button = container.querySelector("button")
      button?.dispatchEvent(new MouseEvent("click", { bubbles: true }))
    })
    expect(startSession).toHaveBeenCalledOnce()

    await unmount()
  })
})
