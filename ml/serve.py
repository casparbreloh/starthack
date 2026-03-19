"""ML Forecast Service — FastAPI sidecar for Mars weather prediction.

Exposes the LSTM weather prediction models as HTTP endpoints so the
agent doesn't need torch/sklearn/pandas as dependencies.

Run with: uv run uvicorn serve:app --reload --port 8090
"""

from __future__ import annotations

import logging

import pandas as pd
from fastapi import FastAPI

from mars_weather.predict import (
    predict_at_horizon_from_context,
    predict_from_context,
)

logger = logging.getLogger(__name__)

app = FastAPI(title="Mars Weather ML Service", version="0.1.0")


@app.get("/health")
def health() -> dict:
    """Health check endpoint."""
    return {"status": "ok"}


@app.post("/predict")
def predict(payload: dict) -> dict:
    """7-sol autoregressive forecast from simulation weather history.

    Expects JSON body:
        {
            "weather_history": [{"sol": 1, "min_temp": ..., ...}, ...],
            "n_sols": 7  // optional, default 7
        }

    Returns:
        {"forecast": [{"sol": N, "min_temp": ..., ...}, ...]}
        {"forecast": []} if history too short or prediction fails.
    """
    weather_history = payload.get("weather_history", [])
    n_sols = payload.get("n_sols", 7)

    if not weather_history:
        return {"forecast": []}

    df = pd.DataFrame(weather_history)
    result = predict_from_context(df, n_sols=n_sols)
    return {"forecast": result if result else []}


@app.post("/predict_at_horizon")
def predict_at_horizon(payload: dict) -> dict:
    """Single-shot prediction at a specific horizon.

    Expects JSON body:
        {
            "weather_history": [{"sol": 1, "min_temp": ..., ...}, ...],
            "horizon": 30  // optional, default 30
        }

    Returns:
        {"forecast": {"sol": N, "min_temp": ..., ...}}
        {"forecast": {}} if prediction fails.
    """
    weather_history = payload.get("weather_history", [])
    horizon = payload.get("horizon", 30)

    if not weather_history:
        return {"forecast": {}}

    df = pd.DataFrame(weather_history)
    result = predict_at_horizon_from_context(df, horizon=horizon)
    return {"forecast": result if result else {}}


@app.post("/seasonal_baseline")
def seasonal_baseline(payload: dict) -> dict:
    """Seasonal baseline forecast for long-term crop planning.

    Expects JSON body:
        {
            "current_sol": 100,
            "lookahead": 90  // optional, default 90
        }

    Returns:
        {"forecast": [{"sol": N, "min_temp": ..., ...}, ...]}
    """
    import os
    import pickle

    from mars_weather import MODEL_DIR

    current_sol = payload.get("current_sol", 0)
    lookahead = payload.get("lookahead", 90)

    seasonal_pkl = os.path.join(MODEL_DIR, "seasonal_baseline.pkl")
    try:
        with open(seasonal_pkl, "rb") as f:
            baseline = pickle.load(f)
    except Exception as exc:
        logger.warning("Failed to load seasonal_baseline.pkl: %s", exc)
        return {"forecast": []}

    try:
        prediction = baseline.predict(current_sol, lookahead=lookahead)
        if not prediction:
            return {"forecast": []}

        target_keys = list(prediction.keys())
        if not target_keys:
            return {"forecast": []}

        n_points = len(prediction[target_keys[0]])
        result = []
        for i in range(n_points):
            entry = {"sol": current_sol + i}
            for key in target_keys:
                vals = prediction[key]
                if i < len(vals):
                    entry[key] = vals[i]
            result.append(entry)

        return {"forecast": result}

    except Exception as exc:
        logger.warning("Seasonal baseline forecast failed: %s", exc)
        return {"forecast": []}
