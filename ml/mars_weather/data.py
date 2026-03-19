"""Data loading, cleaning, and feature engineering for Mars weather prediction."""

import os
import numpy as np
import pandas as pd
from sklearn.preprocessing import StandardScaler

DATA_PATH = os.path.join(os.path.dirname(__file__), "..", "mars_weather_data.csv")

TARGETS = ["min_temp", "max_temp", "pressure", "min_gts_temp", "max_gts_temp"]

DROP_COLS = [
    "abs_humidity", "wind_speed", "wind_direction",  # 0% data
    "pressure_string",  # redundant
    "atmo_opacity",  # constant "Sunny"
    "id", "terrestrial_date", "sunrise", "sunset", "season",
]

UV_MAP = {"Low": 0, "Moderate": 1, "High": 2, "Very_High": 3}

LAG_COLS = ["min_temp", "max_temp", "pressure"]
LAG_STEPS = [1, 2, 3, 7]
ROLLING_WINDOWS = [7, 30]

TRAIN_SOL = 4000
VAL_SOL = 4400


def load_raw(path: str = DATA_PATH) -> pd.DataFrame:
    """Load raw CSV and parse types."""
    df = pd.read_csv(path)
    df["sol"] = pd.to_numeric(df["sol"], errors="coerce")
    df = df.dropna(subset=["sol"])
    df["sol"] = df["sol"].astype(int)
    df = df.sort_values("sol").reset_index(drop=True)

    numeric_cols = ["ls", "min_temp", "max_temp", "pressure", "min_gts_temp", "max_gts_temp"]
    for col in numeric_cols:
        df[col] = pd.to_numeric(df[col], errors="coerce")

    return df


def engineer_features(df: pd.DataFrame) -> pd.DataFrame:
    """Add engineered features to the dataframe."""
    df = df.copy()

    # Drop useless columns
    df = df.drop(columns=[c for c in DROP_COLS if c in df.columns], errors="ignore")

    # Cyclical solar longitude encoding
    ls_rad = np.deg2rad(df["ls"].fillna(0))
    df["ls_sin"] = np.sin(ls_rad)
    df["ls_cos"] = np.cos(ls_rad)

    # Diurnal range
    df["diurnal_range"] = df["max_temp"] - df["min_temp"]

    # Ground-air differentials
    df["ground_air_max_diff"] = df["max_gts_temp"] - df["max_temp"]
    df["ground_air_min_diff"] = df["min_gts_temp"] - df["min_temp"]

    # Martian year position
    df["sol_in_year"] = df["sol"] % 668
    df["mars_year"] = df["sol"] // 668

    # UV encoding
    if "local_uv_irradiance_index" in df.columns:
        df["uv_index"] = df["local_uv_irradiance_index"].map(UV_MAP).fillna(1)
        df = df.drop(columns=["local_uv_irradiance_index"])

    # Lag features
    for col in LAG_COLS:
        for lag in LAG_STEPS:
            df[f"{col}_lag{lag}"] = df[col].shift(lag)

    # Rolling means
    for col in LAG_COLS:
        for window in ROLLING_WINDOWS:
            df[f"{col}_roll{window}"] = df[col].rolling(window, min_periods=1).mean()

    # Drop ls (replaced by sin/cos)
    df = df.drop(columns=["ls"], errors="ignore")

    return df


def prepare_dataset(path: str = DATA_PATH):
    """Full pipeline: load, clean, engineer, split, normalize.

    Returns:
        train_df, val_df, test_df: DataFrames with features and targets
        scaler: fitted StandardScaler (fit on train only)
        feature_cols: list of feature column names
    """
    df = load_raw(path)
    df = engineer_features(df)

    # Drop rows with NaN in targets (from lag features at the start)
    max_lag = max(LAG_STEPS)
    df = df.iloc[max_lag:].reset_index(drop=True)

    # Interpolate remaining NaN in features
    df = df.interpolate(method="linear", limit_direction="both")
    df = df.ffill().bfill()

    # Split by sol
    train_df = df[df["sol"] <= TRAIN_SOL].copy()
    val_df = df[(df["sol"] > TRAIN_SOL) & (df["sol"] <= VAL_SOL)].copy()
    test_df = df[df["sol"] > VAL_SOL].copy()

    # Identify feature columns (everything except sol and targets)
    feature_cols = [c for c in df.columns if c not in TARGETS and c != "sol"]

    # Normalize features
    feature_scaler = StandardScaler()
    train_df[feature_cols] = feature_scaler.fit_transform(train_df[feature_cols])
    val_df[feature_cols] = feature_scaler.transform(val_df[feature_cols])
    test_df[feature_cols] = feature_scaler.transform(test_df[feature_cols])

    # Normalize targets
    target_scaler = StandardScaler()
    train_df[TARGETS] = target_scaler.fit_transform(train_df[TARGETS])
    val_df[TARGETS] = target_scaler.transform(val_df[TARGETS])
    test_df[TARGETS] = target_scaler.transform(test_df[TARGETS])

    return train_df, val_df, test_df, feature_scaler, target_scaler, feature_cols


if __name__ == "__main__":
    train, val, test, feat_scaler, tgt_scaler, feats = prepare_dataset()
    print(f"Features: {len(feats)}")
    print(f"Train: {len(train)} | Val: {len(val)} | Test: {len(test)}")
    print(f"Feature columns: {feats}")
    print(f"\nTrain target stats:")
    print(train[TARGETS].describe())
