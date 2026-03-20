// @vitest-environment jsdom

import { act } from "react"
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest"

import { renderHook } from "@/test/reactHarness"

import { useWebSocket } from "./useWebSocket"

class MockWebSocket {
  static CONNECTING = 0
  static OPEN = 1
  static CLOSING = 2
  static CLOSED = 3
  static instances: MockWebSocket[] = []

  readonly sent: Array<Record<string, unknown>> = []
  readonly url: string
  readyState = MockWebSocket.CONNECTING
  onopen: ((event: Event) => void) | null = null
  onmessage: ((event: MessageEvent<string>) => void) | null = null
  onclose: ((event: CloseEvent) => void) | null = null
  onerror: ((event: Event) => void) | null = null

  constructor(url: string) {
    this.url = url
    MockWebSocket.instances.push(this)
  }

  send(data: string) {
    this.sent.push(JSON.parse(data) as Record<string, unknown>)
  }

  close() {
    this.readyState = MockWebSocket.CLOSED
    this.onclose?.(new CloseEvent("close"))
  }

  open() {
    this.readyState = MockWebSocket.OPEN
    this.onopen?.(new Event("open"))
  }

  message(data: unknown) {
    this.onmessage?.({
      data: JSON.stringify(data),
    } as MessageEvent<string>)
  }
}

describe("useWebSocket", () => {
  beforeEach(() => {
    vi.useFakeTimers()
    MockWebSocket.instances = []
    vi.stubGlobal("WebSocket", MockWebSocket as unknown as typeof WebSocket)
  })

  afterEach(() => {
    vi.unstubAllGlobals()
    vi.useRealTimers()
  })

  it("joins the orchestrated bootstrap session and never falls back to create_session", async () => {
    const { result, unmount } = await renderHook(() =>
      useWebSocket({
        url: "wss://example.cloudfront.net/ws/run-123",
        bootstrapSessionId: "run-123",
      }),
    )

    const socket = MockWebSocket.instances[0]
    expect(socket.url).toBe("wss://example.cloudfront.net/ws/run-123")

    await act(async () => {
      socket.open()
    })

    expect(socket.sent.map((msg) => msg.type)).toEqual(["register", "join_session"])
    expect(socket.sent[1]).toEqual({
      type: "join_session",
      payload: { session_id: "run-123" },
    })

    await act(async () => {
      socket.message({
        type: "error",
        payload: {
          message: "Bootstrap session missing",
          code: "bootstrap_session_only",
        },
      })
    })

    expect(socket.sent.map((msg) => msg.type)).not.toContain("create_session")
    expect(result.current?.error).toBeNull()

    await unmount()
  })
})
