"""
Agent action router — all POST endpoints that the AI agent calls to interact
with the simulation.

  POST /energy/allocate
  POST /greenhouse/set_environment
  POST /water/set_irrigation
  POST /water/maintenance
  POST /crops/plant
  POST /crops/harvest
  POST /crops/remove
  POST /nutrients/adjust
"""

from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel, Field

from src.catalog import CROP_CATALOG
from src.constants import ZONE_AREAS_M2
from src.enums import CropType
from src.session import Session
from src.state import session_manager

router = APIRouter()


def _session(session_id: str | None) -> Session:
    return session_manager.get_or_default(session_id)


# ──────────────────────────────────────────────────────────────────────────────
# Request schemas
# ──────────────────────────────────────────────────────────────────────────────


class EnergyAllocateRequest(BaseModel):
    heating_pct: float = Field(default=47, ge=0, le=100)
    lighting_pct: float = Field(default=30, ge=0, le=100)
    water_recycling_pct: float = Field(default=12, ge=0, le=100)
    nutrient_pumps_pct: float = Field(default=5, ge=0, le=100)
    reserve_pct: float = Field(default=6, ge=0, le=100)


class SetEnvironmentRequest(BaseModel):
    zone_id: str
    target_temp_c: float | None = None
    target_humidity_pct: float | None = Field(default=None, ge=0, le=100)
    target_co2_ppm: float | None = Field(default=None, ge=350, le=5000)
    par_umol_m2s: float | None = Field(default=None, ge=0, le=2000)
    photoperiod_hours: float | None = Field(default=None, ge=0, le=24)


class SetIrrigationRequest(BaseModel):
    zone_id: str
    irrigation_liters_per_sol: float = Field(ge=0)


class WaterMaintenanceRequest(BaseModel):
    action: str = "clean_filters"


class PlantRequest(BaseModel):
    type: CropType
    zone_id: str
    area_m2: float = Field(gt=0, le=50)
    batch_name: str | None = None


class HarvestRequest(BaseModel):
    crop_id: str


class RemoveRequest(BaseModel):
    crop_id: str
    reason: str = ""


class NutrientAdjustRequest(BaseModel):
    zone_id: str
    target_ph: float | None = Field(default=None, ge=4.0, le=8.0)
    nitrogen_boost: bool = False
    potassium_boost: bool = False
    flush_solution: bool = (
        False  # dilute solution to remove accumulated salts (costs 10 L water)
    )


# ──────────────────────────────────────────────────────────────────────────────
# Energy
# ──────────────────────────────────────────────────────────────────────────────


@router.post("/energy/allocate")
async def energy_allocate(
    req: EnergyAllocateRequest,
    session_id: str | None = Query(default=None),
):
    session = _session(session_id)
    async with session.lock:
        session.engine.energy.allocate(req.model_dump())
        return {"status": "ok", "allocation": session.engine.energy.state.allocation}


# ──────────────────────────────────────────────────────────────────────────────
# Greenhouse Environment
# ──────────────────────────────────────────────────────────────────────────────


@router.post("/greenhouse/set_environment")
async def greenhouse_set_environment(
    req: SetEnvironmentRequest,
    session_id: str | None = Query(default=None),
):
    session = _session(session_id)
    engine = session.engine
    if req.zone_id not in engine.climate.state:
        raise HTTPException(
            404,
            f"Zone '{req.zone_id}' not found. Available: {list(engine.climate.state.keys())}",
        )

    async with session.lock:
        zone = engine.climate.set_zone(
            zone_id=req.zone_id,
            target_temp_c=req.target_temp_c,
            target_humidity_pct=req.target_humidity_pct,
            target_co2_ppm=req.target_co2_ppm,
            par_umol_m2s=req.par_umol_m2s,
            photoperiod_hours=req.photoperiod_hours,
        )
        engine.events.log(
            engine.current_sol,
            "action",
            "climate",
            f"Environment setpoints updated for zone {req.zone_id}",
            data=req.model_dump(exclude_none=True),
        )
    return {
        "status": "ok",
        "zone_id": zone.zone_id,
        "target_temp_c": zone.target_temp_c,
        "target_humidity_pct": zone.target_humidity_pct,
        "target_co2_ppm": zone.target_co2_ppm,
        "target_par": zone.target_par,
        "target_photoperiod_hours": zone.target_photoperiod_hours,
    }


# ──────────────────────────────────────────────────────────────────────────────
# Water
# ──────────────────────────────────────────────────────────────────────────────


@router.post("/water/set_irrigation")
async def water_set_irrigation(
    req: SetIrrigationRequest,
    session_id: str | None = Query(default=None),
):
    session = _session(session_id)
    if req.zone_id not in ZONE_AREAS_M2:
        raise HTTPException(404, f"Zone '{req.zone_id}' not found")
    async with session.lock:
        session.engine.water.set_irrigation(req.zone_id, req.irrigation_liters_per_sol)
        return {
            "status": "ok",
            "zone_id": req.zone_id,
            "irrigation_liters_per_sol": req.irrigation_liters_per_sol,
            "reservoir_liters": session.engine.water.state.reservoir_liters,
        }


@router.post("/water/maintenance")
async def water_maintenance(
    req: WaterMaintenanceRequest,
    session_id: str | None = Query(default=None),
):
    session = _session(session_id)
    async with session.lock:
        engine = session.engine
        result = engine.water.maintenance(req.action)
        if result.get("result") == "success":
            engine.scoring.record_preventive_action()
            engine.events.log(
                engine.current_sol,
                "action",
                "water",
                f"Water maintenance performed: {req.action}",
                data=result,
            )
    return result


# ──────────────────────────────────────────────────────────────────────────────
# Crops
# ──────────────────────────────────────────────────────────────────────────────


@router.post("/crops/plant")
async def crops_plant(
    req: PlantRequest,
    session_id: str | None = Query(default=None),
):
    session = _session(session_id)
    engine = session.engine
    # Validate zone
    if req.zone_id not in engine.climate.state:
        raise HTTPException(404, f"Zone '{req.zone_id}' not found")

    async with session.lock:
        # Check available area
        available = max(
            0.0, ZONE_AREAS_M2[req.zone_id] - engine.crops.zone_used_area(req.zone_id)
        )
        if req.area_m2 > available + 0.01:
            raise HTTPException(
                400,
                f"Not enough area in zone {req.zone_id}: requested {req.area_m2} m², "
                f"available {available:.1f} m²",
            )

        try:
            batch = engine.crops.plant(
                current_sol=engine.current_sol,
                crop_type=req.type,
                zone_id=req.zone_id,
                area_m2=req.area_m2,
                batch_name=req.batch_name,
            )
        except ValueError as e:
            raise HTTPException(400, str(e)) from e

        growth_days = CROP_CATALOG[req.type]["growth_days"]
        engine.events.log(
            engine.current_sol,
            "action",
            "crop",
            f"Planted {req.type.value} ({req.area_m2} m²) in zone {req.zone_id} as '{batch.crop_id}'",
        )
    return {
        "status": "ok",
        "crop_id": batch.crop_id,
        "planted_sol": batch.planted_sol,
        "expected_harvest_sol": batch.planted_sol + growth_days,
        "area_m2": batch.area_m2,
        "seeds_remaining": {
            k.value: v for k, v in engine.crops.seeds_remaining.items()
        },
    }


@router.post("/crops/harvest")
async def crops_harvest(
    req: HarvestRequest,
    session_id: str | None = Query(default=None),
):
    session = _session(session_id)
    engine = session.engine
    async with session.lock:
        try:
            result = engine.crops.harvest(req.crop_id)
        except KeyError as e:
            raise HTTPException(404, str(e)) from e

        # Add yield to crew stores
        engine.crew.add_harvest(
            kcal=result["calories_kcal"],
            protein_g=result["protein_g"],
            has_micronutrients=result["provides_micronutrients"],
        )
        engine.scoring.record_harvest(result["yield_kg"])
        engine.events.log(
            engine.current_sol,
            "harvest",
            "crop",
            f"Harvested '{req.crop_id}': {result['yield_kg']} kg, {result['calories_kcal']:.0f} kcal",
            data=result,
        )
    return result


@router.post("/crops/remove")
async def crops_remove(
    req: RemoveRequest,
    session_id: str | None = Query(default=None),
):
    session = _session(session_id)
    engine = session.engine
    async with session.lock:
        try:
            result = engine.crops.remove(req.crop_id, req.reason)
        except KeyError as e:
            raise HTTPException(404, str(e)) from e

        engine.scoring.record_crop_removed(result["waste_kg"])
        engine.events.log(
            engine.current_sol,
            "action",
            "crop",
            f"Removed crop '{req.crop_id}' (reason: {req.reason or 'unspecified'}). "
            f"Waste: {result['waste_kg']} kg",
        )
    return result


# ──────────────────────────────────────────────────────────────────────────────
# Nutrients
# ──────────────────────────────────────────────────────────────────────────────


@router.post("/nutrients/adjust")
async def nutrients_adjust(
    req: NutrientAdjustRequest,
    session_id: str | None = Query(default=None),
):
    session = _session(session_id)
    engine = session.engine
    if req.zone_id not in engine.nutrients.state:
        raise HTTPException(404, f"Zone '{req.zone_id}' not found")

    async with session.lock:
        engine.nutrients.adjust(
            zone_id=req.zone_id,
            target_ph=req.target_ph,
            nitrogen_boost=req.nitrogen_boost,
            potassium_boost=req.potassium_boost,
            flush_solution=req.flush_solution,
        )
        # Flush costs 10 L of water from the reservoir
        if req.flush_solution:
            engine.water.state.reservoir_liters = max(
                0.0, engine.water.state.reservoir_liters - 10.0
            )
        z = engine.nutrients.state[req.zone_id]
    return {
        "status": "ok",
        "zone_id": req.zone_id,
        "solution_ph": z.solution_ph,
        "solution_ec_ms_cm": z.solution_ec_ms_cm,
        "base_salt_ppm": z.base_salt_ppm,
        "nitrogen_ppm": z.nitrogen_ppm,
        "potassium_ppm": z.potassium_ppm,
        "stock_remaining_pct": engine.nutrients.stock_remaining_pct,
    }
