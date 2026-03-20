# ml/

## Purpose

Mars weather prediction ML pipeline + HTTP sidecar service. Trains LSTM models on 4,586 sols of Curiosity rover data to forecast surface conditions (temperature, pressure, ground temperature) at horizons of 1, 7, and 30 sols. Serves predictions via FastAPI so the agent doesn't need torch/sklearn/pandas.

## Structure

- `serve.py` — FastAPI sidecar service (port 8090) exposing `/predict`, `/predict_at_horizon`, `/seasonal_baseline`
- `mars_weather/` — Python package with all pipeline code
- `models/` — Trained artifacts (.pt weights, .pkl scalers, _meta.json, seasonal_baseline.pkl)
- `mars_weather_data.csv` — Source data (4,586 sols, 2012–2026)

## Running

```bash
uv run uvicorn serve:app --reload --port 8090  # Start ML sidecar service
uv run python -m mars_weather.train            # Train all models
uv run python -m mars_weather.evaluate         # Evaluate on test set
uv run python -m mars_weather.predict          # Run predictions
```

## Sidecar Service (serve.py)

- Pydantic request/response models for all endpoints
- Models and scalers loaded once at startup via `lifespan` handler (not per-request)
- Seasonal baseline pickle cached in `_model_cache`
- Agent communicates via `agent/src/weather_integration.py` (httpx client)

## Key Design Decisions

- Temporal split: sols 1–4000 (train), 4000–4400 (val), 4400+ (test)
- Features and targets normalized separately with StandardScaler
- Forward-fill + train-set means for imputation (no bfill to prevent leakage)
- Autoregressive prediction uses h=1 model only; single-shot uses h=7/h=30
- 668-sol Martian year cycle is the dominant predictable signal

## Performance (test set)

- min_temp MAE: 2.18°C | max_temp MAE: 3.49°C | pressure MAE: 7.70 Pa
- LSTM beats seasonal baseline on all targets
