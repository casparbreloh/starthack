# ml/

## Purpose

Mars weather prediction ML pipeline. Trains LSTM models on 4,586 sols of Curiosity rover data to forecast surface conditions (temperature, pressure, ground temperature) at horizons of 1, 7, and 30 sols.

## Structure

- `mars_weather/` — Python package with all pipeline code
- `models/` — Trained artifacts (not committed to git)
- `mars_weather_data.csv` — Source data (4,586 sols, 2012–2026)
- `requirements.txt` — Pinned dependencies (pandas, torch, scikit-learn, etc.)

## Running

Requires the venv at `../.venv/`:

```bash
../.venv/bin/python -m mars_weather.train     # Train all models
../.venv/bin/python -m mars_weather.evaluate  # Evaluate on test set
../.venv/bin/python -m mars_weather.predict   # Run predictions
```

## Key Design Decisions

- Temporal split: sols 1–4000 (train), 4000–4400 (val), 4400+ (test)
- Features and targets normalized separately with StandardScaler
- Forward-fill + train-set means for imputation (no bfill to prevent leakage)
- Autoregressive prediction uses h=1 model only; single-shot uses h=7/h=30
- 668-sol Martian year cycle is the dominant predictable signal

## Performance (test set)

- min_temp MAE: 2.18°C | max_temp MAE: 3.49°C | pressure MAE: 7.70 Pa
- LSTM beats seasonal baseline on all targets
