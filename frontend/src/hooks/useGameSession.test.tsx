// @vitest-environment jsdom

import { act } from "react"
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest"

import * as orchestrator from "@/api/orchestrator"
import { renderHook } from "@/test/reactHarness"

import { useGameSession } from "./useGameSession"

vi.mock("@/api/orchestrator", () => ({
  startSession: vi.fn(),
  getSession: vi.fn(),
}))

describe("useGameSession", () => {
  beforeEach(() => {
    vi.useFakeTimers()
  })

  afterEach(() => {
    vi.useRealTimers()
    vi.clearAllMocks()
  })

  it("waits for ws_ready before exposing the websocket URL", async () => {
    vi.mocked(orchestrator.startSession).mockResolvedValue({
      session_id: "run-123",
      run_id: "run-123",
      status: "starting",
      ws_ready: false,
      started_at: "2026-03-20T00:00:00Z",
    })
    vi.mocked(orchestrator.getSession)
      .mockResolvedValueOnce({
        session_id: "run-123",
        run_id: "run-123",
        status: "starting",
        ws_ready: false,
        target_health_state: "initial",
        ready_reason: "Elb.InitialHealthChecking",
        started_at: "2026-03-20T00:00:02Z",
      })
      .mockResolvedValueOnce({
        session_id: "run-123",
        run_id: "run-123",
        status: "running",
        ws_url: "wss://example.cloudfront.net/ws/run-123",
        ws_ready: true,
        target_health_state: "healthy",
        started_at: "2026-03-20T00:00:04Z",
      })

    const { result, unmount } = await renderHook(() => useGameSession())

    await act(async () => {
      result.current?.startSession()
      await Promise.resolve()
    })

    expect(orchestrator.startSession).toHaveBeenCalledWith(
      expect.objectContaining({
        mode: "interactive",
      }),
    )
    expect(result.current?.wsUrl).toBeNull()

    await act(async () => {
      await vi.advanceTimersByTimeAsync(2_000)
    })

    expect(result.current?.wsUrl).toBeNull()
    expect(result.current?.isStarting).toBe(true)

    await act(async () => {
      await vi.advanceTimersByTimeAsync(2_000)
    })

    expect(result.current?.wsUrl).toBe("wss://example.cloudfront.net/ws/run-123")
    expect(result.current?.isStarting).toBe(false)

    await unmount()
  })
})
