import type {
  TrainingConfig,
  SessionInfo,
  SessionDetail,
  TrainingResult,
} from "@/types/orchestrator"

const BASE_URL = import.meta.env.VITE_ORCHESTRATOR_URL ?? "/api"

function num(v: unknown, fallback = 0): number {
  const n = Number(v)
  return Number.isFinite(n) ? n : fallback
}

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
  const raw = await request<SessionDetail>(`/sessions/${sessionId}`)
  return {
    ...raw,
    current_sol: raw.current_sol != null ? num(raw.current_sol) : undefined,
    final_score: raw.final_score != null ? num(raw.final_score) : undefined,
  }
}

export async function stopSession(sessionId: string): Promise<void> {
  return request<void>(`/sessions/${sessionId}`, {
    method: "DELETE",
  })
}

export async function getResults(sessionId: string): Promise<TrainingResult> {
  const raw = await request<TrainingResult>(`/sessions/${sessionId}/results`)
  const breakdown: Record<string, number> = {}
  for (const [k, v] of Object.entries(raw.score_breakdown ?? {})) {
    breakdown[k] = num(v)
  }
  return {
    ...raw,
    final_score: num(raw.final_score),
    total_crises: num(raw.total_crises),
    seed: num(raw.seed),
    score_breakdown: breakdown,
  }
}
