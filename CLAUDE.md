@AGENTS.md

## Project

Mars Greenhouse Agent System — Syngenta START Hack challenge. Autonomous AI agents manage a Martian greenhouse simulation for a 450-day crew mission (4 astronauts).

## Stack

- **Agent**: Python 3.12+, deployed on AWS AgentCore
- **Simulation**: Python 3.12+, FastAPI, uvicorn
- **Frontend**: React 19, TypeScript 5.9, Vite 8, Tailwind CSS 4
- **ML**: PyTorch 2.10, scikit-learn 1.8, pandas 3.0
- **Package managers**: `uv` (Python), `pnpm` (frontend)

## ML Pipeline

- **Train**: `cd ml && ../.venv/bin/python -m mars_weather.train`
- **Evaluate**: `cd ml && ../.venv/bin/python -m mars_weather.evaluate`
- **Predict**: `cd ml && ../.venv/bin/python -m mars_weather.predict`

## Where to Look

- Weather prediction logic → `ml/mars_weather/`
- Challenge requirements → `docs/CHALLENGE.MD`
- Crop/nutrition/stress data → `docs/mcp-data/`
- Trained model artifacts → `ml/models/`

## Conventions

- Python: snake_case, relative imports within packages
- TypeScript: strict mode, bundler module resolution
- Temporal train/val/test splits (no data leakage)
- Models saved with metadata JSON + pickle scalers
