# Mars Greenhouse Agent — Architecture

## Concept

Autonomous AI agent manages a Martian greenhouse simulation for a 4-person crew over 450 sols. The agent makes daily decisions about crop management, energy allocation, water conservation, and crisis response — informed by weather predictions and the Syngenta knowledge base.

## System Architecture

```
┌─────────────┐     WebSocket (AG-UI)      ┌──────────────────┐
│   Frontend   │◄──────────────────────────►│   Agent (AWS     │
│   React/TS   │                            │   AgentCore)     │
│              │                            │                  │
│  - Crop field│                            │  - Reads state   │
│    visual    │     REST API (read-only)   │  - Decides       │
│  - Weather   │◄──────────────────────────►│  - Executes      │
│    dashboard │     (frontend polls sim)   │  - Logs          │
│  - Crew      │                            │                  │
│    health    │                            │  Syngenta KB     │
│  - Crisis    │                            │  (via AgentCore) │
│    injection │                            │                  │
│  - Agent feed│                            │  Weather Model   │
└──────────────┘                            │  (LSTM, 7-sol)   │
                                            └────────┬─────────┘
                                                     │
                                              REST API calls
                                                     │
                                                     ▼
                                            ┌──────────────────┐
                                            │   Simulation     │
                                            │   FastAPI        │
                                            │                  │
                                            │  State Engine    │
                                            │  (all subsystems)│
                                            │                  │
                                            │  Event Generator │
                                            │  (crises, random)│
                                            │                  │
                                            │  Scoring Engine  │
                                            └──────────────────┘
```

**Data flow:**
- Agent → Simulation: REST calls (read state, execute actions, advance time)
- Agent → Frontend: WebSocket via AG-UI protocol (real-time decision stream)
- Frontend → Simulation: REST calls (read-only state for dashboards + crisis injection)
- Frontend does NOT execute agent actions — only the agent does

---

## Simulation (FastAPI)

### Internal State Model

The simulation holds a single mutable `SimulationState` object that persists for the entire 450-sol session. All endpoints read from or mutate this state.

```python
@dataclass
class SimulationState:
    sol: int                    # current sol (1-450)
    config: SimConfig           # difficulty, weather source, area, zones
    weather: WeatherEngine      # generates/replays Mars weather per sol
    energy: EnergySystem        # solar gen, battery, allocation
    water: WaterSystem          # reservoir, recycling, irrigation
    greenhouse: Greenhouse      # zones with environment controls
    crops: list[CropBatch]      # all active crop batches
    nutrients: NutrientSystem   # per-zone nutrient solution state
    crew: CrewNutrition         # caloric/protein tracking + stored food
    events: EventLog            # all events (crises, harvests, alerts)
    active_crises: list[Crisis] # unresolved crises
    score: ScoringEngine        # running score calculation
    journal: list[DecisionEntry]  # agent's decision log
    rng: Random                 # seeded RNG for reproducibility
```

### Sol Advance Logic

When the agent calls `POST /sim/advance`, the simulation:

```
1. weather.tick(sol)          → generate next sol's weather from data/model
2. energy.tick(weather)       → calc solar generation from irradiance + dust
                              → calc heating cost from delta(external_temp, internal_temp)
                              → apply allocation percentages to available budget
                              → update battery (charge/discharge)
3. water.tick(energy)         → recycling rate depends on energy allocated to it
                              → filter degradation (slow linear decay)
                              → reservoir += recycled - consumed
4. greenhouse.tick(energy, weather) → each zone drifts toward external temp
                              → heating/cooling energy fights the drift
                              → humidity, CO2 evolve based on crop transpiration + controls
5. crops.tick(greenhouse, water, nutrients)
                              → each batch: growth_pct += growth_rate(temp, light, water, nutrients)
                              → stress accumulation if conditions outside optimal range
                              → health decay if stress sustained
                              → death if health < threshold
6. nutrients.tick(crops)      → nutrient consumption by crops
                              → pH/EC drift
7. crew.tick(crops)           → auto-harvest mature crops → add to food buffer
                              → consume from buffer + stored food → track kcal/protein
8. crises.tick(sol, rng)      → check random crisis probability
                              → check scheduled crises
                              → auto-resolve crises where conditions normalized
9. score.tick(all_systems)    → update running score
10. events.emit(...)          → log what happened this sol
```

### Physics Simplifications

All models are linear approximations — good enough for meaningful agent decisions, not scientifically accurate.

**Energy:**
```
solar_generation = panel_area * irradiance * efficiency * (1 - dust_opacity)
heating_cost = k * max(0, target_temp - external_temp) * greenhouse_volume
net_energy = solar_generation - heating_cost - lighting - pumps - recycling
battery += clamp(net_energy, -discharge_rate, charge_rate)
```

**Crop Growth:**
```
base_rate = 1.0 / growth_cycle_days  # fraction per sol
temp_factor = gaussian_penalty(actual_temp, optimal_min, optimal_max)  # 1.0 at optimal, drops off
light_factor = min(1.0, actual_par / required_par)
water_factor = min(1.0, actual_irrigation / required_irrigation)
stress_penalty = max(0, 1.0 - accumulated_stress * 0.1)

growth_pct += base_rate * temp_factor * light_factor * water_factor * stress_penalty
```

**Water:**
```
recycled = daily_consumption * recycling_efficiency * energy_factor
recycling_efficiency -= filter_degradation_rate  # slow linear decay per sol
reservoir += recycled - daily_crop_consumption - daily_crew_consumption
```

**Temperature Drift:**
```
# Zone temp drifts toward external temp, heating fights it
heat_loss = k_insulation * (zone_temp - external_temp)  # watts lost
heat_input = energy_allocated_to_heating                  # watts added
zone_temp += (heat_input - heat_loss) / thermal_mass * dt
```

### API Endpoints

#### Time Management
| Method | Path | Purpose |
|--------|------|---------|
| `GET` | `/sim/status` | Current sol, phase, speed, paused |
| `POST` | `/sim/advance` | Advance N sols, returns events |
| `POST` | `/sim/reset` | Reset to sol 0 with config overrides (seed, difficulty, reserves) |

#### State Reading (agent reads these every sol)
| Method | Path | Purpose |
|--------|------|---------|
| `GET` | `/weather/current` | Current sol weather (temps, pressure, irradiance, dust, season) |
| `GET` | `/weather/history?last_n_sols=N` | Historical weather array |
| `GET` | `/weather/forecast?horizon=7` | Sim-provided forecast with confidence per sol |
| `GET` | `/energy/status` | Solar gen, battery, consumption breakdown, surplus/deficit |
| `GET` | `/greenhouse/environment` | Per-zone: temp, humidity, CO2, PAR, photoperiod, area |
| `GET` | `/water/status` | Reservoir, recycling efficiency, daily consumption/production, filter health |
| `GET` | `/crops/status` | All batches: type, zone, planted_sol, growth_pct, health, stress, yield estimate |
| `GET` | `/nutrients/status` | Per-zone: pH, EC, N/P/K/Ca/Mg, dissolved O2, stock remaining |
| `GET` | `/crew/nutrition` | Today's intake vs target, stored food, fresh buffer, cumulative stats |
| `GET` | `/sensors/readings` | Raw sensor dump with status (ok/degraded/error/offline) |
| `GET` | `/events/log?since_sol=N` | Event history (crises, harvests, alerts) |
| `GET` | `/events/active_crises` | Currently unresolved crises |
| `GET` | `/score/current` | Running score (survival, nutrition, efficiency, crisis mgmt) |
| `GET` | `/score/final` | Available after sol 450 |

#### Agent Actions (mutations)
| Method | Path | Purpose |
|--------|------|---------|
| `POST` | `/energy/allocate` | Set % allocation: heating, lighting, water recycling, pumps, reserve |
| `POST` | `/greenhouse/set_environment` | Per-zone targets: temp, humidity, CO2, PAR, photoperiod |
| `POST` | `/water/set_irrigation` | Per-zone: liters/sol, frequency |
| `POST` | `/water/maintenance` | Trigger: clean_filters (restores efficiency, costs downtime) |
| `POST` | `/crops/plant` | Plant batch: type, zone, area, name → returns expected harvest sol |
| `POST` | `/crops/harvest` | Harvest batch → returns yield (kg, kcal, protein, vitamins) |
| `POST` | `/crops/remove` | Remove batch early (disease, reallocation) → returns freed area |
| `POST` | `/nutrients/adjust` | Per-zone: target pH, EC, N/P/K boosts |
| `POST` | `/agent/log_decision` | Log decisions + reasoning for current sol |

#### Crisis Injection (frontend only)
| Method | Path | Purpose |
|--------|------|---------|
| `POST` | `/crisis/inject` | Inject a crisis: type, severity, zone (optional), duration (optional) |

Crisis types: `water_recycling_decline`, `energy_disruption`, `pathogen_outbreak`, `temperature_failure`, `co2_imbalance`, `pipe_burst`

### Simulation Config (at reset)

```json
{
  "seed": 42,
  "difficulty": "normal",
  "weather_source": "historical",
  "greenhouse_area_m2": 50,
  "number_of_zones": 3,
  "initial_water_liters": 500,
  "initial_stored_food_kcal": 1200000,
  "battery_capacity_wh": 20000,
  "solar_panel_efficiency": 0.18,
  "crisis_frequency_per_sol": 0.022,
  "sensor_error_rate": 0.02,
  "filter_degradation_rate": 0.001,
  "scheduled_crises": []
}
```

Difficulty presets override individual values (easy/normal/hard).

---

## Agent (AWS AgentCore)

### Core Loop (per sol)

```python
async def run_sol(sim_client, kb_client, journal, weather_model):
    # 1. Read all state
    state = await sim_client.read_all_state()

    # 2. Weather prediction (our LSTM model, not sim forecast)
    forecast_7d = weather_model.predict(state.weather_history)
    seasonal_outlook = weather_model.seasonal_baseline(state.sol)

    # 3. Energy budget projection
    energy_forecast = project_energy(forecast_7d, state.energy, state.greenhouse)

    # 4. Decide (single LLM call with structured output)
    decisions = await decide(
        current_state=state,
        energy_forecast=energy_forecast,
        forecast_7d=forecast_7d,
        seasonal_outlook=seasonal_outlook,
        journal_recent=journal.last_n(30),       # last 30 sols of decisions
        lessons_learned=journal.cross_session(),  # summaries from prev runs
        kb_context=await kb_client.query(state),  # Syngenta knowledge base
    )

    # 5. Execute actions
    for action in decisions.actions:
        await sim_client.execute(action)

    # 6. Log reasoning
    journal.append(decisions)
    await sim_client.log_decision(decisions)

    # 7. Advance
    events = await sim_client.advance(sols=1)

    # 8. React to events (immediate crisis response if needed)
    if any(e.type == "crisis" for e in events):
        crisis_response = await decide_crisis(state, events, journal)
        for action in crisis_response.actions:
            await sim_client.execute(action)
        journal.append(crisis_response)
```

### Decision Architecture

The agent is a single LLM call (not separate sub-agents) that receives structured state and returns structured actions. The prompt includes:

1. **System prompt**: Priority hierarchy, crop knowledge, response protocols
2. **Current state**: All simulation readings (compact JSON)
3. **Forecasts**: 7-day weather + energy projection + seasonal outlook
4. **Decision journal**: Last 30 sols of own decisions + outcomes
5. **Lessons learned**: Cross-session summaries (if not first run)
6. **KB context**: Relevant Syngenta knowledge base snippets (retrieved via AgentCore)

Output is structured JSON:

```json
{
  "reasoning": "Energy deficit predicted for sols 143-146 (cold snap). Pre-charging battery. Reducing lettuce zone photoperiod to conserve. Planting potato batch 5 ahead of schedule for winter caloric buffer.",
  "actions": [
    { "endpoint": "energy/allocate", "params": { "heating_pct": 55, "lighting_pct": 25, "water_recycling_pct": 12, "nutrient_pumps_pct": 5, "reserve_pct": 3 } },
    { "endpoint": "greenhouse/set_environment", "params": { "zone_id": "A", "photoperiod_hours": 12 } },
    { "endpoint": "crops/plant", "params": { "type": "potato", "zone_id": "B", "area_m2": 6.0, "batch_name": "potato_batch_5" } }
  ],
  "risk_assessment": "moderate",
  "priorities_this_sol": ["energy_conservation", "winter_preparation"]
}
```

### Weather Model Integration

Pre-built LSTM model, runs locally (not via LLM).

| Horizon | Method | Accuracy | Used For |
|---------|--------|----------|----------|
| 1-sol | LSTM | MAE ~2-3°C temp, ~9 Pa pressure | Daily operational decisions |
| 7-sol | LSTM | MAE ~4°C temp, ~11 Pa pressure | Weekly resource planning |
| Seasonal | Baseline (668-sol cycle) | High (periodic) | Crop cycle planning, planting schedules |

The model also acts as a **sensor sanity checker**: readings deviating >3σ from forecast are flagged as probable sensor errors.

### Syngenta KB Integration

AgentCore provides a knowledge base query endpoint. The agent queries it for:
- Crop-specific stress responses ("what happens to lettuce above 25°C?")
- Optimal nutrient ranges per crop type
- Crisis response protocols
- General agricultural best practices

Queries are contextual — the agent formulates queries based on current state (e.g., if water is low, query water conservation strategies).

### Decision Journal

**In-session (per sol):**
```json
{
  "sol": 142,
  "reasoning": "...",
  "actions": [...],
  "state_snapshot": { "energy_surplus": false, "water_days_remaining": 105, "nutrition_pct": 95.4 },
  "outcome_next_sol": { "events": [...], "score_delta": +0.5 }
}
```

The agent receives the last 30 entries as context, so it can see what worked and what didn't.

**Cross-session (end of 450-sol run):**
```json
{
  "run_id": "run_003",
  "final_score": 88,
  "total_crises": 7,
  "crises_resolved": 6,
  "avg_daily_kcal": 11450,
  "key_learnings": [
    "Planting potatoes before sol 100 is critical for winter caloric buffer",
    "Filter maintenance every 60 sols prevents water crises",
    "Reducing photoperiod to 12h during energy deficit is sustainable for 5+ sols without crop damage"
  ],
  "worst_decision": "Delayed lettuce harvest on sol 87 — led to bolting and waste",
  "best_decision": "Pre-charged battery before sol 200 cold snap — avoided crop freeze"
}
```

Loaded as context at the start of the next run.

---

## Frontend (React/TypeScript)

### Panels

- **Crop field visualization** — grid of greenhouse zones with crop icons, growth bars, health color coding. Aesthetic, not interactive.
- **Weather dashboard** — current Mars weather + 7-day forecast chart (temp, irradiance, dust)
- **Energy panel** — solar generation, battery level, allocation pie chart
- **Water panel** — reservoir level, recycling efficiency, days until critical
- **Crew nutrition panel** — daily kcal/protein vs target, stored food remaining
- **Score panel** — running score breakdown
- **Agent feed** — real-time stream of agent decisions + reasoning (via AG-UI WebSocket)
- **Crisis injection buttons** — trigger predefined scenarios, each calls `POST /crisis/inject`
- **Simulation controls** — start/pause/reset, speed slider

### Data Sources

- All dashboard data: polls simulation REST endpoints (1-2s interval or on sol advance)
- Agent feed: WebSocket subscription via AG-UI protocol from AgentCore
- Crisis injection: direct POST to simulation

---

## Learning Mechanism

### Within a Session

The decision journal gives the agent a sliding window of its own history. It can observe:
- "I reduced irrigation 3 sols ago → crop health dropped → I should restore it"
- "I planted potatoes on sol 95 → they're on track for sol 215 harvest → good timing"

This is not ML — it's context-window reasoning over structured logs.

### Across Sessions

After each 450-sol run, the agent writes a structured summary. On the next run, all previous summaries are injected into the system prompt. Over multiple runs, the agent accumulates strategic knowledge:
- Run 1: "I didn't plant enough potatoes early — caloric crisis at sol 200"
- Run 2: "Planted potatoes early, but forgot to stagger — all harvested at once, then food gap"
- Run 3: "Staggered potatoes every 30 sols, maintained rolling harvest — stable caloric output"

This is stored as a JSON array, appended after each run. No fine-tuning, no embeddings — just growing context.

---

## Priority Hierarchy

1. **Human safety** — crew must survive. If CO2 > 5000ppm or food runs out, mission fails.
2. **System stability** — keep infrastructure running. A dead battery or empty reservoir cascades into everything.
3. **Crop survival** — don't lose what's growing. A dead potato batch set back 120 sols = unrecoverable.
4. **Yield optimization** — maximize output only after the above are secured.

---

## Crisis Response Protocols

Each crisis type has a tiered response:

| Crisis | Immediate | Medium-term | Strategic |
|--------|-----------|-------------|-----------|
| Water recycling decline (<85%) | Reduce irrigation, prioritize potatoes+legumes | Clean filters (costs 4h downtime) | Shift crop mix to low-water |
| Energy disruption | Cut non-essential lighting, maintain heating | Shorten photoperiod (16→12→8h) | Shift to potatoes (tolerate low light) |
| Pathogen outbreak | Isolate zone, reduce humidity | Remove contaminated material, sterilize | Validate zone before replanting |
| Temperature failure (heat) | Increase ventilation, reduce light intensity | Cool nutrient solution | Adjust setpoints |
| Temperature failure (cold) | Activate backup heating, reduce ventilated volume | Cluster crops | Gradual recovery (1-2°C/hour max) |
| CO2 imbalance (low) | Increase enrichment from Mars atmo | Validate sensors | Monitor photosynthesis rate |
| CO2 imbalance (high >1500ppm) | Ventilate system | Check containment | Crew safety alert at >5000ppm |

---

## Crop Strategy

| Crop | Area % | Cycle | kcal/100g | Role | When to Increase |
|------|--------|-------|-----------|------|-----------------|
| Potato | 40-50% | 70-120d | 77 | Caloric backbone | Caloric deficit, winter approaching |
| Beans/Peas | 20-30% | 50-70d | 80-120 | Protein source | Protein deficit |
| Lettuce | 15-20% | 30-45d | 15 | Micronutrients | Micronutrient gap, energy surplus |
| Radish | 5-10% | 21-30d | 16 | Fast buffer | Emergency gap-fill |
| Herbs | 5% | short | minimal | Morale | Stable periods |

Planting is staggered (potatoes every 30 sols) for continuous harvest. Seasonal adjustment: more potatoes before winter (Month 3-4) when energy is scarce.
