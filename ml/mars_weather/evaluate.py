"""Evaluation metrics, anomaly detection, and model comparison."""

import json
import os
import pickle

import numpy as np
import pandas as pd
import torch
from sklearn.metrics import mean_absolute_error, mean_squared_error, r2_score
from torch.utils.data import DataLoader

from . import MODEL_DIR
from .data import prepare_dataset, TARGETS
from .model import LSTMPredictor, MarsWeatherDataset, SeasonalBaseline

SEQ_LEN = 30


def evaluate_baseline(baseline, df):
    """Evaluate seasonal baseline on a dataset."""
    preds = baseline.predict(df["sol"].values)
    metrics = {}
    for target in TARGETS:
        actual = df[target].values
        predicted = np.array(preds[target])
        mask = ~np.isnan(predicted) & ~np.isnan(actual)
        if mask.sum() == 0:
            continue
        metrics[target] = {
            "mae": mean_absolute_error(actual[mask], predicted[mask]),
            "rmse": np.sqrt(mean_squared_error(actual[mask], predicted[mask])),
            "r2": r2_score(actual[mask], predicted[mask]),
        }
    return metrics


def evaluate_lstm(model, df, feature_cols, target_scaler, horizon=1):
    """Evaluate LSTM model on a dataset. Returns metrics in original scale."""
    device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
    model = model.to(device)
    model.eval()

    ds = MarsWeatherDataset(df, feature_cols, TARGETS, SEQ_LEN, horizon)
    loader = DataLoader(ds, batch_size=128, shuffle=False)

    all_preds, all_actuals = [], []
    with torch.no_grad():
        for x, y in loader:
            x = x.to(device)
            pred = model(x).cpu().numpy()
            all_preds.append(pred)
            all_actuals.append(y.numpy())

    preds = np.vstack(all_preds)
    actuals = np.vstack(all_actuals)

    # Inverse-transform to original scale
    preds = target_scaler.inverse_transform(preds)
    actuals = target_scaler.inverse_transform(actuals)

    metrics = {}
    for i, target in enumerate(TARGETS):
        metrics[target] = {
            "mae": mean_absolute_error(actuals[:, i], preds[:, i]),
            "rmse": np.sqrt(mean_squared_error(actuals[:, i], preds[:, i])),
            "r2": r2_score(actuals[:, i], preds[:, i]),
        }
    return metrics, preds, actuals


def detect_anomalies(actuals, preds, threshold_sigma=3):
    """Flag predictions where residual exceeds threshold."""
    residuals = actuals - preds
    anomalies = {}
    for i, target in enumerate(TARGETS):
        r = residuals[:, i]
        mean_r, std_r = np.mean(r), np.std(r)
        mask = np.abs(r - mean_r) > threshold_sigma * std_r
        anomalies[target] = {
            "count": int(mask.sum()),
            "indices": np.where(mask)[0].tolist(),
            "residual_mean": float(mean_r),
            "residual_std": float(std_r),
        }
    return anomalies


def load_lstm(horizon=1, model_dir=MODEL_DIR):
    """Load a saved LSTM model."""
    device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
    with open(os.path.join(model_dir, f"lstm_h{horizon}_meta.json")) as f:
        meta = json.load(f)

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
    return model, meta


def main():
    print("Loading data...")
    train_df, val_df, test_df, feature_scaler, target_scaler, feature_cols = prepare_dataset()

    # Load baseline
    with open(os.path.join(MODEL_DIR, "seasonal_baseline.pkl"), "rb") as f:
        baseline = pickle.load(f)

    print("\n" + "=" * 70)
    print("EVALUATION ON TEST SET")
    print("=" * 70)

    # Baseline (needs unscaled targets)
    test_raw = test_df.copy()
    test_raw[TARGETS] = target_scaler.inverse_transform(test_raw[TARGETS])
    print("\n--- Seasonal Baseline ---")
    baseline_metrics = evaluate_baseline(baseline, test_raw)
    for target, m in baseline_metrics.items():
        print(f"  {target:15s}: MAE={m['mae']:6.2f}  RMSE={m['rmse']:6.2f}  R²={m['r2']:.3f}")

    # LSTM for each horizon
    for horizon in [1, 7, 30]:
        model_path = os.path.join(MODEL_DIR, f"lstm_h{horizon}.pt")
        if not os.path.exists(model_path):
            print(f"\nSkipping LSTM h={horizon} (not trained)")
            continue

        print(f"\n--- LSTM (horizon={horizon}) ---")
        model, meta = load_lstm(horizon)
        metrics, preds, actuals = evaluate_lstm(model, test_df, feature_cols, target_scaler, horizon)

        for target, m in metrics.items():
            print(f"  {target:15s}: MAE={m['mae']:6.2f}  RMSE={m['rmse']:6.2f}  R²={m['r2']:.3f}")

        # Anomaly detection
        anomalies = detect_anomalies(actuals, preds)
        print(f"\n  Anomalies detected (>3σ residual):")
        for target, a in anomalies.items():
            print(f"    {target}: {a['count']} anomalous predictions")

    # Comparison summary
    print("\n" + "=" * 70)
    print("COMPARISON: Baseline vs LSTM (h=1) on test set")
    print("=" * 70)
    model, meta = load_lstm(1)
    lstm_metrics, _, _ = evaluate_lstm(model, test_df, feature_cols, target_scaler, 1)
    print(f"  {'Target':15s} | {'Baseline MAE':>12s} | {'LSTM MAE':>10s} | {'Improvement':>11s}")
    print(f"  {'-'*15} | {'-'*12} | {'-'*10} | {'-'*11}")
    for target in TARGETS:
        b_mae = baseline_metrics.get(target, {}).get("mae", float("nan"))
        l_mae = lstm_metrics[target]["mae"]
        imp = (b_mae - l_mae) / b_mae * 100 if b_mae > 0 else 0
        print(f"  {target:15s} | {b_mae:12.2f} | {l_mae:10.2f} | {imp:+10.1f}%")


if __name__ == "__main__":
    main()
