"""Prediction API for Mars weather forecasting."""

import json
import os
import pickle

import numpy as np
import pandas as pd
import torch

from mars_weather.data import load_raw, engineer_features, TARGETS, DROP_COLS
from mars_weather.model import LSTMPredictor

MODEL_DIR = os.path.join(os.path.dirname(__file__), "..", "models")


def load_model_and_scalers(horizon=1, model_dir=MODEL_DIR):
    """Load trained LSTM model, metadata, and scalers."""
    with open(os.path.join(model_dir, f"lstm_h{horizon}_meta.json")) as f:
        meta = json.load(f)

    model = LSTMPredictor(
        input_size=meta["input_size"],
        hidden_size=meta["hidden_size"],
        num_layers=meta["num_layers"],
        output_size=meta["output_size"],
    )
    model.load_state_dict(torch.load(os.path.join(model_dir, f"lstm_h{horizon}.pt"), weights_only=True))
    model.eval()

    with open(os.path.join(model_dir, "feature_scaler.pkl"), "rb") as f:
        feature_scaler = pickle.load(f)
    with open(os.path.join(model_dir, "target_scaler.pkl"), "rb") as f:
        target_scaler = pickle.load(f)

    return model, meta, feature_scaler, target_scaler


def predict_next(n_sols=7, horizon=1, model_dir=MODEL_DIR):
    """Predict the next n_sols of Mars weather.

    Uses the most recent data as context and autoregressively predicts forward.

    Args:
        n_sols: Number of sols to forecast
        horizon: Which trained model horizon to use (1, 7, or 30)
        model_dir: Path to saved models

    Returns:
        DataFrame with columns: sol, min_temp, max_temp, pressure, min_gts_temp, max_gts_temp
    """
    model, meta, feature_scaler, target_scaler = load_model_and_scalers(horizon, model_dir)
    feature_cols = meta["feature_cols"]
    seq_len = meta["seq_len"]

    # Load and prepare all available data
    df = load_raw()
    df = engineer_features(df)
    df = df.dropna(subset=TARGETS).reset_index(drop=True)

    # Normalize features using training scaler
    df_scaled = df.copy()
    df_scaled[feature_cols] = feature_scaler.transform(df[feature_cols])

    last_sol = int(df["sol"].iloc[-1])
    predictions = []

    # Use sliding window for autoregressive prediction
    context = df_scaled[feature_cols].values[-seq_len:].astype(np.float32)

    for step in range(n_sols):
        x = torch.tensor(context).unsqueeze(0)  # (1, seq_len, features)
        with torch.no_grad():
            pred_scaled = model(x).numpy()[0]  # (5,) = normalized targets

        # Inverse-transform to original scale
        pred = target_scaler.inverse_transform(pred_scaled.reshape(1, -1))[0]

        pred_sol = last_sol + step + 1
        pred_dict = {"sol": pred_sol}
        for i, target in enumerate(TARGETS):
            pred_dict[target] = round(float(pred[i]), 1)
        predictions.append(pred_dict)

        # For autoregressive: shift context window and append prediction
        new_row = context[-1].copy()
        context = np.vstack([context[1:], new_row])

    return pd.DataFrame(predictions)


if __name__ == "__main__":
    print("Mars Weather Forecast — Next 7 sols")
    print("=" * 60)
    forecast = predict_next(n_sols=7, horizon=1)
    print(forecast.to_string(index=False))
    print("\nMars Weather Forecast — Next 30 sols")
    print("=" * 60)
    forecast30 = predict_next(n_sols=30, horizon=1)
    print(forecast30.to_string(index=False))
