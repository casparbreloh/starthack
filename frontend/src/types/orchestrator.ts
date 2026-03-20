// ── Orchestrator API types (Training Suite) ──────────────────────────

export interface TrainingConfig {
  seed?: number
  difficulty?: string
  mission_sols?: number
  scenario_preset?: string
}

export interface SessionInfo {
  session_id: string
  run_id: string
  status: "starting" | "running" | "completed" | "failed" | "stopped"
  task_arn?: string
  ws_url?: string
  started_at: string
}

export interface SessionDetail extends SessionInfo {
  current_sol?: number
  final_score?: number
  results_url?: string
}

export interface TrainingResult {
  run_id: string
  final_score: number
  mission_phase: string
  total_crises: number
  score_breakdown: Record<string, number>
  completed_at: string
  seed: number
  difficulty: string
}

export type SessionStatus = SessionInfo["status"]
