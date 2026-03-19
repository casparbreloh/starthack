# ml/mars_weather/

## Purpose

Python package implementing the full ML pipeline: data loading, feature engineering, model definitions, training, evaluation, and prediction.

## Key Files

- `data.py` — Load CSV, clean, engineer features, split, normalize. Entry point: `prepare_dataset()`
- `model.py` — `LSTMPredictor` (2-layer LSTM, 64 hidden), `MarsWeatherDataset` (sliding window), `SeasonalBaseline`
- `train.py` — Training loop with early stopping (patience=10). Trains baseline + LSTM for h=1,7,30
- `predict.py` — `predict_next(n_sols)` (autoregressive h=1) and `predict_at_horizon(horizon)` (single-shot)
- `evaluate.py` — MAE/RMSE/R² metrics, anomaly detection (3σ residuals), model comparison

## Targets

`TARGETS = ["min_temp", "max_temp", "pressure", "min_gts_temp", "max_gts_temp"]`

## Feature Engineering (data.py)

- Cyclical solar longitude: sin/cos encoding of `ls`
- Lag features: t-1, t-2, t-3, t-7 for temp/pressure
- Rolling means: 7-sol and 30-sol windows
- Derived: diurnal_range, ground_air_diff, sol_in_year, mars_year, uv_index

## Dependencies

- Uses `from .data import ...` relative imports throughout
- Scalers (StandardScaler) saved as pickle, metadata as JSON
- `TARGETS` imported from `data.py`; `MODEL_DIR` defined locally in each module
