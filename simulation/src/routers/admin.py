"""
Admin / simulation control router.

  POST /sim/advance            — advance N sols (core simulation loop step)
  POST /sim/reset              — reset simulation (supports difficulty + overrides)
  POST /admin/tick             — legacy single-sol advance
  POST /admin/tick/bulk        — legacy multi-sol advance
  POST /admin/reset            — legacy alias for /sim/reset
  POST /admin/scenario/*       — hackathon crisis injection
  POST /agent/log_decision     — agent reasoning log
"""

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

from src.engine import AgentDecision
from src.enums import Difficulty
from src.state import engine

router = APIRouter()


# ──────────────────────────────────────────────────────────────────────────────
# Request schemas
# ──────────────────────────────────────────────────────────────────────────────


class AdvanceRequest(BaseModel):
    sols: int = Field(default=1, ge=1, le=450)


class ResetRequest(BaseModel):
    seed: int = 0
    difficulty: Difficulty = Difficulty.NORMAL
    starting_reserves: dict | None = None


class PathogenRequest(BaseModel):
    crop_id: str


class AgentDecisionRequest(BaseModel):
    sol: int
    decisions: list
    weather_forecast_used: dict | None = None
    risk_assessment: str = "nominal"


# ──────────────────────────────────────────────────────────────────────────────
# Core simulation control
# ──────────────────────────────────────────────────────────────────────────────


@router.post("/sim/advance")
def sim_advance(req: AdvanceRequest):
    from src.enums import MissionPhase

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
def sim_reset(req: ResetRequest):
    engine.reset(
        seed=req.seed,
        difficulty=req.difficulty,
        starting_reserves=req.starting_reserves,
    )
    return {
        "status": "ok",
        "current_sol": engine.current_sol,
        "difficulty": req.difficulty.value,
    }


# ──────────────────────────────────────────────────────────────────────────────
# Legacy /admin/* endpoints
# ──────────────────────────────────────────────────────────────────────────────


@router.post("/api/admin/tick")
def admin_tick():
    """Advance by exactly 1 sol (legacy)."""
    from src.enums import MissionPhase

    if engine.mission_phase != MissionPhase.ACTIVE:
        raise HTTPException(400, "Mission complete or failed")
    events = engine.advance(1)
    return {"current_day": engine.current_sol, "events": events}


@router.post("/api/admin/tick/bulk")
def admin_tick_bulk(days: int = 1):
    """Advance by N sols (legacy)."""
    from src.enums import MissionPhase

    if days < 1 or days > 450:
        raise HTTPException(400, "days must be 1–450")
    if engine.mission_phase != MissionPhase.ACTIVE:
        raise HTTPException(400, "Mission complete or failed")
    events = engine.advance(days)
    return {"current_day": engine.current_sol, "days_advanced": days, "events": events}


@router.post("/api/admin/reset")
def admin_reset():
    engine.reset()
    return {"status": "ok", "current_day": engine.current_sol}


# ──────────────────────────────────────────────────────────────────────────────
# Scenario injection
# ──────────────────────────────────────────────────────────────────────────────


@router.post("/api/admin/scenario/water_leak")
def scenario_water_leak():
    engine.scenario_water_leak()
    return {
        "status": "ok",
        "scenario": "water_leak",
        "recycling_efficiency_pct": engine.water.state.recycling_efficiency_pct,
        "filter_health_pct": engine.water.state.filter_health_pct,
    }


@router.post("/api/admin/scenario/hvac_failure")
def scenario_hvac_failure():
    engine.scenario_hvac_failure()
    return {
        "status": "ok",
        "scenario": "hvac_failure",
        "zones": {z_id: z.temp_c for z_id, z in engine.climate.state.items()},
    }


@router.post("/api/admin/scenario/pathogen")
def scenario_pathogen(req: PathogenRequest):
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


@router.post("/api/admin/scenario/dust_storm")
def scenario_dust_storm(duration_sols: int = 10):
    engine.scenario_dust_storm(duration_sols)
    return {"status": "ok", "scenario": "dust_storm", "duration_sols": duration_sols}


@router.post("/api/admin/scenario/energy_disruption")
def scenario_energy_disruption():
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
def agent_log_decision(req: AgentDecisionRequest):
    decision = AgentDecision(
        sol=req.sol,
        decisions=req.decisions,
        weather_forecast_used=req.weather_forecast_used,
        risk_assessment=req.risk_assessment,
    )
    engine.log_agent_decision(decision)
    engine.scoring.record_preventive_action()
    return {"status": "ok", "sol": req.sol, "decisions_logged": len(req.decisions)}
