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

  POST /api/action/plant        ← legacy convenience aliases
  POST /api/action/harvest
  POST /api/action/water
  POST /api/action/fertilize
  POST /api/action/set_environment
"""

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

from src.constants import ZONE_AREAS_M2
from src.enums import CropType
from src.state import engine

router = APIRouter()


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
    irrigation_frequency: str | None = "continuous"


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
    target_ec_ms_cm: float | None = Field(default=None, ge=0.1, le=5.0)
    nitrogen_boost: bool = False
    potassium_boost: bool = False


# ── Legacy API action schemas ──────────────────────────────────────────────


class LegacyPlantRequest(BaseModel):
    bed_id: int
    crop_type: CropType


class LegacyHarvestRequest(BaseModel):
    bed_id: int | None = None
    crop_id: str | None = None


class LegacyWaterRequest(BaseModel):
    bed_id: int | None = None
    zone_id: str | None = None
    amount_liters: float = Field(gt=0)


class LegacyFertilizeRequest(BaseModel):
    bed_id: int | None = None
    zone_id: str | None = None
    amount_nitrogen: float = Field(gt=0)


class LegacySetEnvironmentRequest(BaseModel):
    temperature: float | None = None
    co2_ppm: float | None = None
    humidity: float | None = None
    light_par: float | None = None


# ──────────────────────────────────────────────────────────────────────────────
# Energy
# ──────────────────────────────────────────────────────────────────────────────


@router.post("/energy/allocate")
def energy_allocate(req: EnergyAllocateRequest):
    engine.energy.allocate(req.model_dump())
    engine.scoring.record_preventive_action()
    return {"status": "ok", "allocation": engine.energy.state.allocation}


# ──────────────────────────────────────────────────────────────────────────────
# Greenhouse Environment
# ──────────────────────────────────────────────────────────────────────────────


@router.post("/greenhouse/set_environment")
def greenhouse_set_environment(req: SetEnvironmentRequest):
    if req.zone_id not in engine.climate.state:
        raise HTTPException(
            404,
            f"Zone '{req.zone_id}' not found. Available: {list(engine.climate.state.keys())}",
        )

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
def water_set_irrigation(req: SetIrrigationRequest):
    if req.zone_id not in ZONE_AREAS_M2:
        raise HTTPException(404, f"Zone '{req.zone_id}' not found")
    engine.water.set_irrigation(req.zone_id, req.irrigation_liters_per_sol)
    return {
        "status": "ok",
        "zone_id": req.zone_id,
        "irrigation_liters_per_sol": req.irrigation_liters_per_sol,
        "reservoir_liters": engine.water.state.reservoir_liters,
    }


@router.post("/water/maintenance")
def water_maintenance(req: WaterMaintenanceRequest):
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
def crops_plant(req: PlantRequest):
    # Validate zone
    if req.zone_id not in engine.climate.state:
        raise HTTPException(404, f"Zone '{req.zone_id}' not found")

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

    from src.catalog import CROP_CATALOG

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
def crops_harvest(req: HarvestRequest):
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
def crops_remove(req: RemoveRequest):
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
def nutrients_adjust(req: NutrientAdjustRequest):
    if req.zone_id not in engine.nutrients.state:
        raise HTTPException(404, f"Zone '{req.zone_id}' not found")

    engine.nutrients.adjust(
        zone_id=req.zone_id,
        target_ph=req.target_ph,
        target_ec_ms_cm=req.target_ec_ms_cm,
        nitrogen_boost=req.nitrogen_boost,
        potassium_boost=req.potassium_boost,
    )
    z = engine.nutrients.state[req.zone_id]
    return {
        "status": "ok",
        "zone_id": req.zone_id,
        "solution_ph": z.solution_ph,
        "nitrogen_ppm": z.nitrogen_ppm,
        "potassium_ppm": z.potassium_ppm,
        "stock_remaining_pct": engine.nutrients.stock_remaining_pct,
    }


# ──────────────────────────────────────────────────────────────────────────────
# Legacy /api/action/* endpoints (backwards-compatible with original spec)
# ──────────────────────────────────────────────────────────────────────────────


def _bed_id_to_zone(bed_id: int) -> str:
    """Map legacy integer bed_id (0–9) to zone letter."""
    zones = sorted(ZONE_AREAS_M2.keys())
    idx = bed_id % len(zones)
    return zones[idx]


@router.post("/api/action/plant")
def legacy_plant(req: LegacyPlantRequest):
    zone_id = _bed_id_to_zone(req.bed_id)
    area_m2 = 3.0  # default area per bed
    available = max(0.0, ZONE_AREAS_M2[zone_id] - engine.crops.zone_used_area(zone_id))
    area_m2 = min(area_m2, available)
    if area_m2 <= 0:
        raise HTTPException(
            400, f"No space available in zone {zone_id} for bed {req.bed_id}"
        )
    try:
        batch = engine.crops.plant(
            current_sol=engine.current_sol,
            crop_type=req.crop_type,
            zone_id=zone_id,
            area_m2=area_m2,
            batch_name=f"bed{req.bed_id}_{req.crop_type.value}",
        )
    except ValueError as e:
        raise HTTPException(400, str(e)) from e
    from src.catalog import CROP_CATALOG

    return {
        "status": "ok",
        "bed_id": req.bed_id,
        "crop_id": batch.crop_id,
        "expected_harvest_sol": batch.planted_sol
        + CROP_CATALOG[req.crop_type]["growth_days"],
    }


@router.post("/api/action/harvest")
def legacy_harvest(req: LegacyHarvestRequest):
    if req.crop_id:
        crop_id = req.crop_id
    elif req.bed_id is not None:
        # Find crop in that bed
        prefix = f"bed{req.bed_id}_"
        matches = [cid for cid in engine.crops.batches if cid.startswith(prefix)]
        if not matches:
            raise HTTPException(404, f"No crop found in bed {req.bed_id}")
        crop_id = matches[0]
    else:
        raise HTTPException(400, "Provide either crop_id or bed_id")

    try:
        result = engine.crops.harvest(crop_id)
    except KeyError as e:
        raise HTTPException(404, str(e)) from e

    engine.crew.add_harvest(
        result["calories_kcal"], result["protein_g"], result["provides_micronutrients"]
    )
    engine.scoring.record_harvest(result["yield_kg"])
    return result


@router.post("/api/action/water")
def legacy_water(req: LegacyWaterRequest):
    if req.zone_id:
        zone_id = req.zone_id
    elif req.bed_id is not None:
        zone_id = _bed_id_to_zone(req.bed_id)
    else:
        raise HTTPException(400, "Provide zone_id or bed_id")

    if zone_id not in ZONE_AREAS_M2:
        raise HTTPException(404, f"Zone '{zone_id}' not found")

    # Immediately add water to reservoir (clamped to capacity) / distribute to zone irrigation
    engine.water.state.reservoir_liters = min(
        engine.water.state.reservoir_capacity_liters,
        engine.water.state.reservoir_liters + req.amount_liters,
    )
    engine.water.set_irrigation(zone_id, req.amount_liters)
    return {
        "status": "ok",
        "zone_id": zone_id,
        "irrigation_set_liters_per_sol": req.amount_liters,
    }


@router.post("/api/action/fertilize")
def legacy_fertilize(req: LegacyFertilizeRequest):
    if req.zone_id:
        zone_id = req.zone_id
    elif req.bed_id is not None:
        zone_id = _bed_id_to_zone(req.bed_id)
    else:
        raise HTTPException(400, "Provide zone_id or bed_id")

    engine.nutrients.adjust(zone_id=zone_id, nitrogen_boost=True)
    z = engine.nutrients.state[zone_id]
    return {"status": "ok", "zone_id": zone_id, "nitrogen_ppm": z.nitrogen_ppm}


@router.post("/api/action/set_environment")
def legacy_set_environment(req: LegacySetEnvironmentRequest):
    """Apply the same environment settings to ALL zones."""
    for zone_id in engine.climate.state:
        engine.climate.set_zone(
            zone_id=zone_id,
            target_temp_c=req.temperature,
            target_co2_ppm=req.co2_ppm,
            target_humidity_pct=req.humidity,
            par_umol_m2s=req.light_par,
        )
    return {"status": "ok", "applied_to_zones": list(engine.climate.state.keys())}
