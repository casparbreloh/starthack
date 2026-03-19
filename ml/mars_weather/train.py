"""Training pipeline for Mars weather LSTM model."""

import os
import json
import pickle

import numpy as np
import torch
import torch.nn as nn
from torch.utils.data import DataLoader

from .data import prepare_dataset, TARGETS
from .model import LSTMPredictor, MarsWeatherDataset, SeasonalBaseline

MODEL_DIR = os.path.join(os.path.dirname(__file__), "..", "models")
SEQ_LEN = 30
BATCH_SIZE = 64
EPOCHS = 100
LR = 1e-3
PATIENCE = 10


def train_seasonal_baseline(train_df, target_scaler):
    """Train seasonal baseline on unscaled data."""
    df = train_df.copy()
    df[TARGETS] = target_scaler.inverse_transform(df[TARGETS])
    baseline = SeasonalBaseline(targets=TARGETS)
    baseline.fit(df)
    return baseline


def train_lstm(train_df, val_df, feature_cols, horizon=1):
    """Train LSTM model with early stopping."""
    device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
    print(f"Training on: {device}")

    train_ds = MarsWeatherDataset(train_df, feature_cols, TARGETS, SEQ_LEN, horizon)
    val_ds = MarsWeatherDataset(val_df, feature_cols, TARGETS, SEQ_LEN, horizon)

    train_loader = DataLoader(train_ds, batch_size=BATCH_SIZE, shuffle=True)
    val_loader = DataLoader(val_ds, batch_size=BATCH_SIZE, shuffle=False)

    model = LSTMPredictor(
        input_size=len(feature_cols),
        hidden_size=64,
        num_layers=2,
        output_size=len(TARGETS),
        dropout=0.2,
    ).to(device)

    optimizer = torch.optim.Adam(model.parameters(), lr=LR)
    criterion = nn.MSELoss()

    best_val_loss = float("inf")
    patience_counter = 0
    best_state = None

    for epoch in range(EPOCHS):
        # Train
        model.train()
        train_loss = 0
        for x, y in train_loader:
            x, y = x.to(device), y.to(device)
            pred = model(x)
            loss = criterion(pred, y)
            optimizer.zero_grad()
            loss.backward()
            optimizer.step()
            train_loss += loss.item() * x.size(0)
        train_loss /= len(train_ds)

        # Validate
        model.eval()
        val_loss = 0
        with torch.no_grad():
            for x, y in val_loader:
                x, y = x.to(device), y.to(device)
                pred = model(x)
                val_loss += criterion(pred, y).item() * x.size(0)
        val_loss /= len(val_ds)

        if (epoch + 1) % 10 == 0 or epoch == 0:
            print(f"  Epoch {epoch+1:3d} | Train Loss: {train_loss:.4f} | Val Loss: {val_loss:.4f}")

        # Early stopping (treat NaN as non-improvement)
        if not np.isnan(val_loss) and val_loss < best_val_loss:
            best_val_loss = val_loss
            patience_counter = 0
            best_state = {k: v.cpu().clone() for k, v in model.state_dict().items()}
        else:
            patience_counter += 1
            if patience_counter >= PATIENCE:
                print(f"  Early stopping at epoch {epoch+1}")
                break

    if best_state is None:
        raise RuntimeError("Training failed: no valid checkpoint (all val losses were NaN)")

    model.load_state_dict(best_state)
    return model, best_val_loss


def save_model(model, feature_cols, feature_scaler, target_scaler, horizon, model_dir=MODEL_DIR):
    """Save model checkpoint and metadata."""
    os.makedirs(model_dir, exist_ok=True)
    torch.save(model.state_dict(), os.path.join(model_dir, f"lstm_h{horizon}.pt"))

    metadata = {
        "feature_cols": feature_cols,
        "targets": TARGETS,
        "seq_len": SEQ_LEN,
        "horizon": horizon,
        "input_size": len(feature_cols),
        "hidden_size": 64,
        "num_layers": 2,
        "output_size": len(TARGETS),
    }
    with open(os.path.join(model_dir, f"lstm_h{horizon}_meta.json"), "w") as f:
        json.dump(metadata, f, indent=2)

    with open(os.path.join(model_dir, "feature_scaler.pkl"), "wb") as f:
        pickle.dump(feature_scaler, f)
    with open(os.path.join(model_dir, "target_scaler.pkl"), "wb") as f:
        pickle.dump(target_scaler, f)


def main():
    print("Loading and preparing data...")
    train_df, val_df, test_df, feature_scaler, target_scaler, feature_cols = prepare_dataset()
    print(f"Train: {len(train_df)} | Val: {len(val_df)} | Test: {len(test_df)}")
    print(f"Features: {len(feature_cols)}")

    # Train seasonal baseline (on unscaled targets)
    print("\n--- Seasonal Baseline ---")
    baseline = train_seasonal_baseline(train_df, target_scaler)
    # Evaluate baseline on val (compare in raw scale)
    val_raw = val_df.copy()
    val_raw[TARGETS] = target_scaler.inverse_transform(val_raw[TARGETS])
    preds = baseline.predict(val_raw["sol"].values)
    for target in TARGETS:
        actual = val_raw[target].values
        predicted = np.array(preds[target])
        mask = ~np.isnan(predicted) & ~np.isnan(actual)
        mae = np.mean(np.abs(actual[mask] - predicted[mask]))
        print(f"  {target}: MAE = {mae:.2f}")

    os.makedirs(MODEL_DIR, exist_ok=True)
    with open(os.path.join(MODEL_DIR, "seasonal_baseline.pkl"), "wb") as f:
        pickle.dump(baseline, f)

    # Train LSTM for different horizons
    for horizon in [1, 7, 30]:
        print(f"\n--- LSTM (horizon={horizon}) ---")
        model, val_loss = train_lstm(train_df, val_df, feature_cols, horizon=horizon)
        save_model(model, feature_cols, feature_scaler, target_scaler, horizon)
        print(f"  Best val loss: {val_loss:.4f}")

    print("\nTraining complete. Models saved to models/")


if __name__ == "__main__":
    main()
