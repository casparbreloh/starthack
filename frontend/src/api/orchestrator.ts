import type {
  TrainingConfig,
  SessionInfo,
  SessionDetail,
  TrainingResult,
} from "@/types/orchestrator"

const BASE_URL = import.meta.env.VITE_ORCHESTRATOR_URL ?? "/api"

class OrchestratorError extends Error {
  constructor(
    message: string,
    public status: number,
  ) {
    super(message)
    this.name = "OrchestratorError"
  }
}

async function request<T>(path: string, options?: RequestInit): Promise<T> {
  const response = await fetch(`${BASE_URL}${path}`, {
    headers: { "Content-Type": "application/json" },
    ...options,
  })

  if (!response.ok) {
    const body = await response.text().catch(() => "Unknown error")
    throw new OrchestratorError(body, response.status)
  }

  // Handle 204 No Content
  if (response.status === 204) {
    return undefined as T
  }

  return response.json() as Promise<T>
}

export async function startSession(config: TrainingConfig): Promise<SessionInfo> {
  return request<SessionInfo>("/sessions", {
    method: "POST",
    body: JSON.stringify(config),
  })
}

export async function listSessions(): Promise<SessionInfo[]> {
  return request<SessionInfo[]>("/sessions")
}

export async function getSession(sessionId: string): Promise<SessionDetail> {
  return request<SessionDetail>(`/sessions/${sessionId}`)
}

export async function stopSession(sessionId: string): Promise<void> {
  return request<void>(`/sessions/${sessionId}`, {
    method: "DELETE",
  })
}

export async function getResults(sessionId: string): Promise<TrainingResult> {
  return request<TrainingResult>(`/sessions/${sessionId}/results`)
}
