# simulation/src/models/

## Purpose

Sub-models implementing the greenhouse simulation physics/biology. Each model follows the PCSE (WOFOST) two-phase tick pattern.

## Key Files

- `weather.py` — Mars surface weather generation (temperature, pressure, dust, UV, solar irradiance)
- `energy.py` — Solar panel generation, battery storage, consumption allocation
- `climate.py` — Greenhouse internal climate (temperature, humidity, CO2) with PI-control damping
- `water.py` — Water cycle: irrigation, recycling, transpiration, filter degradation
- `nutrients.py` — Nutrient solution management (pH, EC, NPK per zone)
- `crops.py` — Crop growth, stress, yield modeling (5 crop types: potato, soybean, lettuce, radish, herbs)
- `crew.py` — Crew health, nutrition, hydration, radiation with survival consequences
- `events.py` — Crisis event generation, lifecycle, and auto-detection thresholds
- `autonomous_events.py` — Probabilistic autonomous events (biofouling, mechanical failures, sensor errors)
- `scoring.py` — Mission score: survival (35%), nutrition (30%), efficiency (20%), crisis_mgmt (15%)
- `responses.py` — Pydantic response models defining the API contract (used for OpenAPI codegen)

## Conventions

- Every sub-model implements `calc_rates()` then `integrate()`
- Engine calls models in fixed order: Weather → Energy → Climate → Water → Nutrients → Crops → Crew → Events → Scoring
- `responses.py` is the single source of truth for API response shapes — changes here trigger frontend type regeneration via `make codegen`
