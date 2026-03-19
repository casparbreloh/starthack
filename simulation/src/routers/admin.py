"""
Admin / simulation control router.

  POST /sim/advance            — advance N sols (core simulation loop step)
  POST /sim/reset              — reset simulation (supports difficulty + overrides)
  POST /admin/scenario/*       — hackathon crisis injection
  POST /agent/log_decision     — agent reasoning log
  POST /sessions               — create a new session
  GET  /sessions               — list active sessions
"""

from typing import Any

from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel, Field

from src.engine import AgentDecision, SimulationEngine
from src.enums import Difficulty, MissionPhase
from src.models.responses import (
    CreateSessionResponse,
    ListSessionsResponse,
    SimAdvanceResponse,
)
from src.session import SessionConfig
from src.state import session_manager

router = APIRouter()


def _engine(session_id: str | None) -> SimulationEngine:
    return session_manager.get_or_default(session_id).engine


# ──────────────────────────────────────────────────────────────────────────────
# Request schemas
# ──────────────────────────────────────────────────────────────────────────────


class AdvanceRequest(BaseModel):
    sols: int = Field(default=1, ge=1, le=450)


class ResetRequest(BaseModel):
    difficulty: Difficulty = Difficulty.NORMAL
    starting_reserves: dict[str, float] | None = None


class PathogenRequest(BaseModel):
    crop_id: str


class AgentDecisionRequest(BaseModel):
    sol: int
    decisions: list[dict[str, Any]]
    weather_forecast_used: dict[str, Any] | None = None
    risk_assessment: str = "nominal"


class CreateSessionRequest(BaseModel):
    seed: int | None = None
    difficulty: str = "normal"
    tick_delay_ms: int = 0
    mission_sols: int = Field(default=450, ge=1, le=450)
    starting_reserves: dict[str, float] = Field(default_factory=dict)
    autonomous_events_enabled: bool = True


# ──────────────────────────────────────────────────────────────────────────────
# Core simulation control
# ──────────────────────────────────────────────────────────────────────────────


@router.post("/sim/advance", response_model=SimAdvanceResponse)
def sim_advance(
    req: AdvanceRequest,
    session_id: str | None = Query(default=None),
):
    engine = _engine(session_id)
    if engine.mission_phase != MissionPhase.ACTIVE:
        raise HTTPException(
            400, f"Mission is {engine.mission_phase.value}, cannot advance"
        )

    events = engine.advance(req.sols)
    return {
        "new_sol": engine.current_sol,
        "mission_phase": engine.mission_phase.value,
        "events": events,
    }


@router.post("/sim/reset")
def sim_reset(
    req: ResetRequest,
    session_id: str | None = Query(default=None),
):
    engine = _engine(session_id)
    engine.reset(
        difficulty=req.difficulty,
        starting_reserves=req.starting_reserves,
    )
    return {
        "status": "ok",
        "current_sol": engine.current_sol,
        "difficulty": req.difficulty.value,
    }


# ──────────────────────────────────────────────────────────────────────────────
# Session management
# ──────────────────────────────────────────────────────────────────────────────


@router.post("/sessions", response_model=CreateSessionResponse)
def create_session(req: CreateSessionRequest):
    config = SessionConfig(
        seed=req.seed,
        difficulty=req.difficulty,
        tick_delay_ms=req.tick_delay_ms,
        mission_sols=req.mission_sols,
        starting_reserves=req.starting_reserves,
    )
    session = session_manager.create(config)
    return {
        "session_id": session.id,
        "config": {
            "seed": config.seed,
            "difficulty": config.difficulty,
            "tick_delay_ms": config.tick_delay_ms,
            "mission_sols": config.mission_sols,
            "starting_reserves": config.starting_reserves,
        },
    }


@router.get("/sessions", response_model=ListSessionsResponse)
def list_sessions():
    sessions = session_manager.list_sessions()
    return {
        "sessions": [
            {
                "id": s.id,
                "created_at": s.created_at.isoformat(),
                "current_sol": s.engine.current_sol,
            }
            for s in sessions
        ]
    }


# ──────────────────────────────────────────────────────────────────────────────
# Scenario injection
# ──────────────────────────────────────────────────────────────────────────────


@router.post("/admin/scenario/water_leak")
def scenario_water_leak(session_id: str | None = Query(default=None)):
    engine = _engine(session_id)
    engine.scenario_water_leak()
    return {
        "status": "ok",
        "scenario": "water_leak",
        "recycling_efficiency_pct": engine.water.state.recycling_efficiency_pct,
        "filter_health_pct": engine.water.state.filter_health_pct,
    }


@router.post("/admin/scenario/hvac_failure")
def scenario_hvac_failure(session_id: str | None = Query(default=None)):
    engine = _engine(session_id)
    engine.scenario_hvac_failure()
    return {
        "status": "ok",
        "scenario": "hvac_failure",
        "zones": {z_id: z.temp_c for z_id, z in engine.climate.state.items()},
    }


@router.post("/admin/scenario/pathogen")
def scenario_pathogen(
    req: PathogenRequest,
    session_id: str | None = Query(default=None),
):
    engine = _engine(session_id)
    try:
        # Trigger the pathogen scenario for the given crop; this mutates engine state.
        engine.scenario_pathogen(req.crop_id)
        # Retrieve the affected crop batch from the engine after injection.
        batch = engine.crops.batches[req.crop_id]
    except KeyError:
        raise HTTPException(404, f"Crop '{req.crop_id}' not found") from None
    return {
        "status": "ok",
        "scenario": "pathogen",
        "crop_id": req.crop_id,
        "health": batch.health,
    }


@router.post("/admin/scenario/dust_storm")
def scenario_dust_storm(
    duration_sols: int = 10,
    session_id: str | None = Query(default=None),
):
    engine = _engine(session_id)
    engine.scenario_dust_storm(duration_sols)
    return {"status": "ok", "scenario": "dust_storm", "duration_sols": duration_sols}


@router.post("/admin/scenario/energy_disruption")
def scenario_energy_disruption(session_id: str | None = Query(default=None)):
    engine = _engine(session_id)
    engine.scenario_energy_disruption()
    return {
        "status": "ok",
        "scenario": "energy_disruption",
        "battery_pct": engine.energy.battery_pct,
    }


# ──────────────────────────────────────────────────────────────────────────────
# Agent decision log
# ──────────────────────────────────────────────────────────────────────────────


@router.post("/agent/log_decision")
def agent_log_decision(
    req: AgentDecisionRequest,
    session_id: str | None = Query(default=None),
):
    engine = _engine(session_id)
    decision = AgentDecision(
        sol=req.sol,
        decisions=req.decisions,
        weather_forecast_used=req.weather_forecast_used,
        risk_assessment=req.risk_assessment,
    )
    engine.log_agent_decision(decision)
    return {"status": "ok", "sol": req.sol, "decisions_logged": len(req.decisions)}
