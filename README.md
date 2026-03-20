# Oasis — Autonomous Martian Greenhouse

## The Problem

NASA targets the late 2030s for crewed Mars missions. A 450-day surface stay means astronauts need fresh food — but there's no farmer on Mars. Growing crops in an alien environment with unpredictable dust storms, energy constraints, and equipment failures requires decisions faster and more consistently than any human crew can make while also running a mission.

## Our Solution

Oasis is an **autonomous AI agent** that manages a Martian greenhouse end-to-end: planting crops, allocating energy, conserving water, and responding to crises — all without human intervention.

The system runs a full 450-sol (Martian day) mission in a **real-time simulation** with a live dashboard where judges can watch the agent think, act, and adapt.

### How It Works

1. **Simulation engine** ticks through each sol, modeling weather, energy, water, crops, and crew nutrition with physics-based sub-models
2. **Interrupt detector** pauses the simulation when something critical happens — a dust storm, a pathogen outbreak, a dying crop batch, a depleting water reservoir
3. **AI agent** receives the full greenhouse state, reasons about priorities, and responds with concrete actions (adjust heating, plant a new batch, clean water filters, reallocate energy)
4. **Weather prediction model** (LSTM neural network trained on Mars data) gives the agent a 7-sol forecast so it can plan ahead rather than just react
5. **Specialist crisis agents** activate for domain-specific emergencies — water crisis, energy disruption, pathogen response, storm preparation, climate emergency, nutrition planning
6. **Live dashboard** shows everything in real-time: crop fields, weather, energy, water, crew health, agent reasoning, and score

### What Makes It Different

- **Proactive, not reactive** — the agent uses ML weather forecasts to pre-charge batteries before cold snaps, plant calorie-dense crops before winter, and stagger harvests for continuous food supply
- **Crisis injection** — judges can throw curveballs (dust storms, pipe bursts, pathogen outbreaks) at any time and watch the agent adapt in real-time
- **Learning across runs** — the agent writes a decision journal each mission and uses it as context in subsequent runs, accumulating strategic knowledge without any fine-tuning
- **Syngenta knowledge base** — the agent queries Syngenta's agricultural KB via AWS AgentCore for crop-specific advice (stress responses, nutrient ranges, best practices)

## Architecture

```
Frontend (React)  <──WebSocket──>  Simulation (FastAPI)  <──WebSocket──>  Agent (AWS AgentCore)
     │                                    │                                      │
  Live dashboard                   Physics engine                         LLM reasoning
  Crisis injection                 Self-ticking loop                      6 specialist agents
  Sim controls                     Interrupt detection                    Weather forecasts (LSTM)
                                                                          Syngenta KB queries
```

## Tech Stack

| Component | Technology |
|-----------|-----------|
| Agent | Python 3.13, AWS AgentCore, Claude |
| Simulation | Python 3.13, FastAPI, WebSocket |
| Frontend | React 19, TypeScript, Vite, Tailwind CSS |
| ML | PyTorch (LSTM), scikit-learn, pandas |

## Running It

```bash
make install   # install all dependencies
make dev       # start all services (simulation + agent + frontend + ML sidecar)
```

Open the dashboard, hit start, and watch the agent keep four astronauts alive for 450 sols on Mars.

Created at START Hack 2026
