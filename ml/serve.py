"""ML Forecast Service — FastAPI sidecar for Mars weather prediction.

Exposes the LSTM weather prediction models as HTTP endpoints so the
agent doesn't need torch/sklearn/pandas as dependencies.

Models are loaded as ONNX sessions at startup (no PyTorch dependency at
serve time). ONNX Runtime provides faster cold-start and smaller memory
footprint compared to loading full PyTorch models.

Run with: uv run uvicorn serve:app --reload --port 8090
"""

from __future__ import annotations

import logging
import os
import pickle
from contextlib import asynccontextmanager
from typing import Any

import pandas as pd
from fastapi import FastAPI
from pydantic import BaseModel

from mars_weather import MODEL_DIR
from mars_weather.predict import (
    load_model_onnx,
    predict_at_horizon_from_context,
    predict_from_context,
)

logger = logging.getLogger(__name__)


# -- Request/response models --


class PredictRequest(BaseModel):
    weather_history: list[dict[str, Any]]
    n_sols: int = 7


class HorizonRequest(BaseModel):
    weather_history: list[dict[str, Any]]
    horizon: int = 30


class SeasonalRequest(BaseModel):
    current_sol: int
    lookahead: int = 90


class ForecastListResponse(BaseModel):
    forecast: list[dict[str, Any]]


class ForecastDictResponse(BaseModel):
    forecast: dict[str, Any]


# -- Model cache populated at startup --

_model_cache: dict[str, Any] = {}


def _load_all_models() -> None:
    """Load all ONNX sessions, scalers, and seasonal baseline into cache."""
    for horizon in (1, 7, 30):
        try:
            session, meta, feat_scaler, tgt_scaler = load_model_onnx(horizon=horizon)
            _model_cache[f"h{horizon}"] = {
                "session": session,
                "meta": meta,
                "feature_scaler": feat_scaler,
                "target_scaler": tgt_scaler,
            }
            logger.info("Loaded ONNX session h=%d", horizon)
        except Exception as exc:
            logger.warning("Failed to load ONNX h=%d: %s", horizon, exc)

    seasonal_pkl = os.path.join(MODEL_DIR, "seasonal_baseline.pkl")
    try:
        with open(seasonal_pkl, "rb") as f:
            _model_cache["seasonal"] = pickle.load(f)
        logger.info("Loaded seasonal baseline")
    except Exception as exc:
        logger.warning("Failed to load seasonal_baseline.pkl: %s", exc)


@asynccontextmanager
async def lifespan(app: FastAPI):  # type: ignore[no-untyped-def]
    """Load models on startup."""
    _load_all_models()
    yield


app = FastAPI(title="Mars Weather ML Service", version="0.1.0", lifespan=lifespan)


@app.get("/health")
def health() -> dict:
    """Health check endpoint."""
    return {"status": "ok"}


@app.post("/predict")
def predict(req: PredictRequest) -> ForecastListResponse:
    """7-sol autoregressive forecast from simulation weather history."""
    if not req.weather_history:
        return ForecastListResponse(forecast=[])

    df = pd.DataFrame(req.weather_history)
    result = predict_from_context(df, n_sols=req.n_sols)
    return ForecastListResponse(forecast=result if result else [])


@app.post("/predict_at_horizon")
def predict_at_horizon(req: HorizonRequest) -> ForecastDictResponse:
    """Single-shot prediction at a specific horizon."""
    if not req.weather_history:
        return ForecastDictResponse(forecast={})

    df = pd.DataFrame(req.weather_history)
    result = predict_at_horizon_from_context(df, horizon=req.horizon)
    return ForecastDictResponse(forecast=result if result else {})


@app.post("/seasonal_baseline")
def seasonal_baseline(req: SeasonalRequest) -> ForecastListResponse:
    """Seasonal baseline forecast for long-term crop planning."""
    baseline = _model_cache.get("seasonal")
    if baseline is None:
        logger.warning("Seasonal baseline not loaded")
        return ForecastListResponse(forecast=[])

    try:
        prediction = baseline.predict(req.current_sol, lookahead=req.lookahead)
        if not prediction:
            return ForecastListResponse(forecast=[])

        target_keys = list(prediction.keys())
        if not target_keys:
            return ForecastListResponse(forecast=[])

        n_points = len(prediction[target_keys[0]])
        result: list[dict[str, Any]] = []
        for i in range(n_points):
            entry: dict[str, Any] = {"sol": req.current_sol + i}
            for key in target_keys:
                vals = prediction[key]
                if i < len(vals):
                    entry[key] = vals[i]
            result.append(entry)

        return ForecastListResponse(forecast=result)

    except Exception as exc:
        logger.warning("Seasonal baseline forecast failed: %s", exc)
        return ForecastListResponse(forecast=[])
