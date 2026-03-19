"""Prediction API for Mars weather forecasting."""

import json
import os
import pickle

import numpy as np
import pandas as pd
import torch

from . import MODEL_DIR
from .data import load_raw, engineer_features, TARGETS
from .model import LSTMPredictor


def load_model_and_scalers(horizon=1, model_dir=MODEL_DIR):
    """Load trained LSTM model, metadata, and scalers."""
    with open(os.path.join(model_dir, f"lstm_h{horizon}_meta.json")) as f:
        meta = json.load(f)

    device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
    model = LSTMPredictor(
        input_size=meta["input_size"],
        hidden_size=meta["hidden_size"],
        num_layers=meta["num_layers"],
        output_size=meta["output_size"],
    )
    model.load_state_dict(torch.load(
        os.path.join(model_dir, f"lstm_h{horizon}.pt"),
        weights_only=True,
        map_location=device,
    ))
    model.to(device)
    model.eval()

    with open(os.path.join(model_dir, "feature_scaler.pkl"), "rb") as f:
        feature_scaler = pickle.load(f)
    with open(os.path.join(model_dir, "target_scaler.pkl"), "rb") as f:
        target_scaler = pickle.load(f)

    return model, meta, feature_scaler, target_scaler, device


def predict_next(n_sols=7, model_dir=MODEL_DIR):
    """Predict the next n_sols of Mars weather using the h=1 model autoregressively.

    Always uses the horizon=1 model and steps forward one sol at a time,
    updating features from each prediction for the next step.

    Args:
        n_sols: Number of sols to forecast
        model_dir: Path to saved models

    Returns:
        DataFrame with columns: sol, min_temp, max_temp, pressure, min_gts_temp, max_gts_temp
    """
    model, meta, feature_scaler, target_scaler, device = load_model_and_scalers(1, model_dir)
    feature_cols = meta["feature_cols"]
    seq_len = meta["seq_len"]

    # Load and prepare all available data (unscaled)
    df = load_raw()
    df = engineer_features(df)
    df = df.dropna(subset=TARGETS).reset_index(drop=True)

    # Keep unscaled copy for building future feature rows
    df_raw = df.copy()

    # Normalize features using training scaler
    df_scaled = df.copy()
    df_scaled[feature_cols] = feature_scaler.transform(df[feature_cols])

    last_sol = int(df["sol"].iloc[-1])
    predictions = []

    # Use sliding window for autoregressive prediction
    context = df_scaled[feature_cols].values[-seq_len:].astype(np.float32)
    # Track recent raw target values for rebuilding lag/rolling features
    recent_raw = df_raw[["sol"] + TARGETS].tail(max(30, seq_len)).copy()

    for step in range(n_sols):
        x = torch.tensor(context, device=device).unsqueeze(0)
        with torch.no_grad():
            pred_scaled = model(x).detach().cpu().numpy()[0]

        # Inverse-transform to original scale
        pred = target_scaler.inverse_transform(pred_scaled.reshape(1, -1))[0]

        pred_sol = last_sol + step + 1
        pred_dict = {"sol": pred_sol}
        for i, target in enumerate(TARGETS):
            pred_dict[target] = round(float(pred[i]), 1)
        predictions.append(pred_dict)

        # Reconstruct features for the new row
        # Compute lag/rolling features BEFORE appending current prediction
        # so that lag1 = previous sol (not current)
        sol = pred_sol
        ls_approx = (sol % 668) / 668 * 360  # approximate solar longitude
        ls_rad = np.deg2rad(ls_approx)
        new_features = {}
        new_features["ls_sin"] = np.sin(ls_rad)
        new_features["ls_cos"] = np.cos(ls_rad)
        new_features["diurnal_range"] = pred[1] - pred[0]
        new_features["ground_air_max_diff"] = pred[4] - pred[1]
        new_features["ground_air_min_diff"] = pred[3] - pred[0]
        new_features["sol_in_year"] = sol % 668
        new_features["mars_year"] = sol // 668
        new_features["uv_index"] = 1.0  # default moderate

        # Lag features from recent_raw (before appending current prediction)
        for col in ["min_temp", "max_temp", "pressure"]:
            vals = recent_raw[col].values
            for lag in [1, 2, 3, 7]:
                new_features[f"{col}_lag{lag}"] = vals[-lag] if len(vals) >= lag else vals[-1]
            for window in [7, 30]:
                w = min(window, len(vals))
                new_features[f"{col}_roll{window}"] = np.mean(vals[-w:])

        # NOW append current prediction for future lag computation
        new_raw = pd.DataFrame([{
            "sol": pred_sol,
            "min_temp": pred[0], "max_temp": pred[1], "pressure": pred[2],
            "min_gts_temp": pred[3], "max_gts_temp": pred[4],
        }])
        recent_raw = pd.concat([recent_raw, new_raw], ignore_index=True)

        # Build feature vector in correct column order and scale
        new_row_df = pd.DataFrame([[new_features.get(c, 0.0) for c in feature_cols]], columns=feature_cols)
        new_row_scaled = feature_scaler.transform(new_row_df).astype(np.float32)
        context = np.vstack([context[1:], new_row_scaled])

    return pd.DataFrame(predictions)


def predict_at_horizon(horizon=7, model_dir=MODEL_DIR):
    """Single-shot prediction at a specific horizon using the matching model.

    Uses the h=7 or h=30 model to predict exactly t+horizon from current data.
    No autoregressive stepping — just one prediction at the trained offset.

    Args:
        horizon: How many sols ahead to predict (1, 7, or 30)
        model_dir: Path to saved models

    Returns:
        dict with sol and predicted targets
    """
    model, meta, feature_scaler, target_scaler, device = load_model_and_scalers(horizon, model_dir)
    feature_cols = meta["feature_cols"]
    seq_len = meta["seq_len"]

    df = load_raw()
    df = engineer_features(df)
    df = df.dropna(subset=TARGETS).reset_index(drop=True)

    df_scaled = df.copy()
    df_scaled[feature_cols] = feature_scaler.transform(df[feature_cols])

    context = df_scaled[feature_cols].values[-seq_len:].astype(np.float32)
    x = torch.tensor(context, device=device).unsqueeze(0)

    with torch.no_grad():
        pred_scaled = model(x).detach().cpu().numpy()[0]

    pred = target_scaler.inverse_transform(pred_scaled.reshape(1, -1))[0]
    last_sol = int(df["sol"].iloc[-1])

    result = {"sol": last_sol + horizon}
    for i, target in enumerate(TARGETS):
        result[target] = round(float(pred[i]), 1)
    return result


if __name__ == "__main__":
    print("Mars Weather Forecast — Next 7 sols (autoregressive, h=1)")
    print("=" * 60)
    forecast = predict_next(n_sols=7)
    print(forecast.to_string(index=False))

    print("\nSingle-shot predictions at specific horizons:")
    print("=" * 60)
    for h in [1, 7, 30]:
        p = predict_at_horizon(horizon=h)
        print(f"  t+{h:2d} (sol {p['sol']}): "
              f"temp=[{p['min_temp']}, {p['max_temp']}]°C  "
              f"P={p['pressure']} Pa  "
              f"ground=[{p['min_gts_temp']}, {p['max_gts_temp']}]°C")


# =============================================================================
# Context-based prediction functions for agent use [R5-C2, R7-C2, R9-H1, R9-H2]
# These accept simulation weather history instead of loading the CSV.
# =============================================================================


def _impute_context_df(df):
    """Impute NaN values in a context DataFrame before calling engineer_features().

    This is necessary because engineer_features() does NOT do imputation —
    that only happens in prepare_dataset() which is not called here. [R7-C2]

    Ground temp offsets are approximate Curiosity training data differentials.
    """
    import pandas as _pd

    # [R10-H1] Ground temps: proxy offsets (do NOT use NaN — causes NaN diffs)
    if "min_gts_temp" not in df.columns or df["min_gts_temp"].isna().all():
        df["min_gts_temp"] = df["min_temp"] - 5.0  # ground colder at night
    if "max_gts_temp" not in df.columns or df["max_gts_temp"].isna().all():
        df["max_gts_temp"] = df["max_temp"] + 10.0  # ground warmer during day

    # [R9-H1] UV index: string "Moderate" (NOT integer 1) — engineer_features()
    # calls .map(UV_MAP) which expects string keys {"Low":0, "Moderate":1, ...}
    if "local_uv_irradiance_index" not in df.columns:
        df["local_uv_irradiance_index"] = "Moderate"

    # Forward-fill remaining NaN
    df = df.ffill()
    # Backfill remaining NaN with column means (numeric columns only)
    for col in df.select_dtypes(include="number").columns:
        if df[col].isna().any():
            col_mean = df[col].mean()
            if not _pd.isna(col_mean):
                df[col] = df[col].fillna(col_mean)

    return df


def predict_from_context(weather_history, n_sols=7, model_dir=MODEL_DIR):
    """Predict the next n_sols using simulation weather history as context.

    Accepts a DataFrame of recent weather readings from the simulation
    instead of loading the CSV. This means LSTM predictions reflect the
    simulation's actual weather trajectory, not static Curiosity data. [R5-C2]

    Field name mapping (min_temp_c -> min_temp etc.) should be done by the
    caller (WeatherForecaster._sim_history_to_lstm_df) before calling this.

    Args:
        weather_history: pd.DataFrame with LSTM-compatible column names.
                         Required: sol, min_temp, max_temp, pressure.
                         min_gts_temp and max_gts_temp may be absent/NaN.
        n_sols: Number of sols to forecast (default 7)
        model_dir: Path to saved model artifacts

    Returns:
        list[dict]: Each dict has keys: sol, min_temp, max_temp, pressure,
                    min_gts_temp, max_gts_temp. [R5-C1]
        Returns empty list if history is too short (<seq_len) or fails. [R8-C1]
    """
    try:
        # [R9-H2] Step 1: Load model and scalers FIRST (provides seq_len)
        model, meta, feature_scaler, target_scaler, device = load_model_and_scalers(1, model_dir)
        feature_cols = meta["feature_cols"]
        seq_len = meta["seq_len"]

        df = weather_history.copy()

        # Step 2: NaN imputation BEFORE engineer_features() [R7-C2]
        df = _impute_context_df(df)

        # Step 3: Engineer features
        df = engineer_features(df)
        df = df.dropna(subset=TARGETS).reset_index(drop=True)

        # [R8-C1, R9-H2] Step 4: Check if enough history for LSTM seq_len
        if len(df) < seq_len:
            return []

        # Keep unscaled copy for lag/rolling feature reconstruction
        df_raw = df.copy()

        # Normalize features using training scaler
        df_scaled = df.copy()
        df_scaled[feature_cols] = feature_scaler.transform(df[feature_cols])

        last_sol = int(df["sol"].iloc[-1])

        # Autoregressive prediction loop (mirrors predict_next logic)
        context = df_scaled[feature_cols].values[-seq_len:].astype(np.float32)
        recent_raw = df_raw[["sol"] + TARGETS].tail(max(30, seq_len)).copy()

        predictions = []
        for step in range(n_sols):
            x = torch.tensor(context, device=device).unsqueeze(0)
            with torch.no_grad():
                pred_scaled = model(x).detach().cpu().numpy()[0]

            pred = target_scaler.inverse_transform(pred_scaled.reshape(1, -1))[0]

            pred_sol = last_sol + step + 1
            pred_dict = {"sol": pred_sol}
            for i, target in enumerate(TARGETS):
                pred_dict[target] = round(float(pred[i]), 1)
            predictions.append(pred_dict)

            # Reconstruct features for the new row
            sol = pred_sol
            ls_approx = (sol % 668) / 668 * 360
            ls_rad = np.deg2rad(ls_approx)
            new_features = {}
            new_features["ls_sin"] = np.sin(ls_rad)
            new_features["ls_cos"] = np.cos(ls_rad)
            new_features["diurnal_range"] = pred[1] - pred[0]
            new_features["ground_air_max_diff"] = pred[4] - pred[1]
            new_features["ground_air_min_diff"] = pred[3] - pred[0]
            new_features["sol_in_year"] = sol % 668
            new_features["mars_year"] = sol // 668
            new_features["uv_index"] = 1.0  # default moderate

            for col in ["min_temp", "max_temp", "pressure"]:
                vals = recent_raw[col].values
                for lag in [1, 2, 3, 7]:
                    new_features[f"{col}_lag{lag}"] = vals[-lag] if len(vals) >= lag else vals[-1]
                for window in [7, 30]:
                    w = min(window, len(vals))
                    new_features[f"{col}_roll{window}"] = np.mean(vals[-w:])

            new_raw = pd.DataFrame([{
                "sol": pred_sol,
                "min_temp": pred[0], "max_temp": pred[1], "pressure": pred[2],
                "min_gts_temp": pred[3], "max_gts_temp": pred[4],
            }])
            recent_raw = pd.concat([recent_raw, new_raw], ignore_index=True)

            new_row_df = pd.DataFrame(
                [[new_features.get(c, 0.0) for c in feature_cols]],
                columns=feature_cols,
            )
            new_row_scaled = feature_scaler.transform(new_row_df).astype(np.float32)
            context = np.vstack([context[1:], new_row_scaled])

        return predictions

    except Exception:
        return []


def predict_at_horizon_from_context(weather_history, horizon=7, model_dir=MODEL_DIR):
    """Single-shot prediction at a specific horizon from simulation weather history.

    Same as predict_at_horizon() but accepts external DataFrame instead of CSV.

    Args:
        weather_history: pd.DataFrame with simulation weather history,
                         mapped to LSTM-compatible column names.
        horizon: How many sols ahead to predict (1, 7, or 30)
        model_dir: Path to saved model artifacts

    Returns:
        dict with sol and predicted target values. Empty dict on failure.
    """
    try:
        model, meta, feature_scaler, target_scaler, device = load_model_and_scalers(
            horizon, model_dir
        )
        feature_cols = meta["feature_cols"]
        seq_len = meta["seq_len"]

        df = weather_history.copy()
        df = _impute_context_df(df)
        df = engineer_features(df)
        df = df.dropna(subset=TARGETS).reset_index(drop=True)

        if len(df) < seq_len:
            return {}

        df_scaled = df.copy()
        df_scaled[feature_cols] = feature_scaler.transform(df[feature_cols])

        context = df_scaled[feature_cols].values[-seq_len:].astype(np.float32)
        x = torch.tensor(context, device=device).unsqueeze(0)

        with torch.no_grad():
            pred_scaled = model(x).detach().cpu().numpy()[0]

        pred = target_scaler.inverse_transform(pred_scaled.reshape(1, -1))[0]
        last_sol = int(df["sol"].iloc[-1])

        result = {"sol": last_sol + horizon}
        for i, target in enumerate(TARGETS):
            result[target] = round(float(pred[i]), 1)
        return result

    except Exception:
        return {}
