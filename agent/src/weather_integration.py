"""LSTM weather model integration for the Mars greenhouse agent.

Wraps the pre-trained LSTM models to provide weather forecasts based on
simulation weather history. Maps simulation field names to LSTM field names.

The LSTM models were trained on Curiosity rover data (4,586 sols). By feeding
simulation weather history as context, the forecasts reflect the simulation's
actual weather trajectory, not static Curiosity data. [ARCH-1, R5-C2]
"""

from __future__ import annotations

import logging
import os
import pickle
import sys

# [R9-M2] sys.path manipulation at MODULE LEVEL (before any mars_weather import)
# so that top-level imports of mars_weather work correctly.
_ML_DIR = os.path.join(os.path.dirname(__file__), "..", "..", "ml")
_ML_DIR = os.path.abspath(_ML_DIR)
if _ML_DIR not in sys.path:
    sys.path.insert(0, _ML_DIR)

from mars_weather.predict import (  # noqa: E402  # type: ignore[import-not-found]
    predict_at_horizon_from_context,
    predict_from_context,
)

from .config import ML_MODELS_DIR  # noqa: E402

try:
    import pandas as pd
except ImportError:
    pd = None  # type: ignore[assignment]

logger = logging.getLogger(__name__)

# [R5-H3] Field name mapping: simulation fields -> LSTM field names
# Only renames divergent fields; all other columns pass through unchanged.
# [R9-M1] Note: min_gts_temp and max_gts_temp are NOT in simulation weather
# output — they are ground temperature values from the LSTM training data only.
# They are set to NaN in the context DataFrame; predict_from_context() imputes them.
SIM_TO_LSTM_FIELDS: dict[str, str] = {
    "min_temp_c": "min_temp",
    "max_temp_c": "max_temp",
    "pressure_pa": "pressure",
}


class WeatherForecaster:
    """LSTM-based weather forecaster for the Mars greenhouse agent.

    Feeds simulation weather history to pre-trained LSTM models to provide:
    - 7-sol autoregressive forecast
    - 30-sol single-shot forecast
    - 668-sol seasonal baseline outlook
    - Sensor sanity checking (3-sigma deviation detection)
    """

    def __init__(self, model_dir: str = ML_MODELS_DIR) -> None:
        """Initialize the WeatherForecaster.

        Args:
            model_dir: Path to trained model artifacts directory.
        """
        self.model_dir = model_dir

        # [R8-H5] Load seasonal baseline with graceful failure
        seasonal_pkl = os.path.join(model_dir, "seasonal_baseline.pkl")
        try:
            with open(seasonal_pkl, "rb") as f:
                self.seasonal_baseline = pickle.load(f)
            logger.info("Loaded seasonal baseline from %s", seasonal_pkl)
        except FileNotFoundError:
            logger.warning(
                "seasonal_baseline.pkl not found at %s. "
                "Seasonal forecasting will be unavailable.",
                seasonal_pkl,
            )
            self.seasonal_baseline = None
        except Exception as exc:
            logger.warning("Failed to load seasonal_baseline.pkl: %s", exc)
            self.seasonal_baseline = None

    def _sim_history_to_lstm_df(self, weather_history: list[dict]):
        """Convert simulation weather history to LSTM-compatible DataFrame.

        Maps simulation field names to LSTM field names via SIM_TO_LSTM_FIELDS.
        All other columns (ls, sol, dust_opacity, solar_irradiance_wm2, etc.)
        pass through unchanged. [R9-M1]

        Sets min_gts_temp and max_gts_temp to NaN since simulation does not
        provide ground temperature sensors — predict_from_context() handles
        imputation with proxy offsets. [R10-H1]

        Args:
            weather_history: List of dicts from SimClient.get_weather_history()

        Returns:
            pd.DataFrame with LSTM-compatible column names.
        """
        if not weather_history:
            return pd.DataFrame()  # type: ignore[union-attr]

        df = pd.DataFrame(weather_history)  # type: ignore[union-attr]

        # Rename divergent fields
        df = df.rename(columns=SIM_TO_LSTM_FIELDS)

        # Set ground temperature columns to NaN (not in simulation weather output)
        # predict_from_context() will impute with: min_temp-5.0, max_temp+10.0
        df["min_gts_temp"] = float("nan")
        df["max_gts_temp"] = float("nan")

        return df

    def get_7sol_forecast(self, weather_history: list[dict]) -> list[dict]:
        """Get 7-sol autoregressive forecast from simulation weather history.

        Args:
            weather_history: List of weather dicts from SimClient.get_weather_history()

        Returns:
            List of up to 7 forecast dicts with sol and target fields.
            Empty list if history is too short (<30 sols) or forecast fails. [R8-C1]
        """
        try:
            df = self._sim_history_to_lstm_df(weather_history)
            if df.empty:
                return []
            result = predict_from_context(df, n_sols=7, model_dir=self.model_dir)
            return result if result else []
        except Exception as exc:
            logger.warning("7-sol LSTM forecast failed: %s", exc)
            return []

    def get_30sol_forecast(self, weather_history: list[dict]) -> dict:
        """Get 30-sol single-shot forecast from simulation weather history.

        Args:
            weather_history: List of weather dicts from SimClient.get_weather_history()

        Returns:
            Single forecast dict with sol and target fields.
            Empty dict if forecast fails.
        """
        try:
            df = self._sim_history_to_lstm_df(weather_history)
            if df.empty:
                return {}
            result = predict_at_horizon_from_context(
                df, horizon=30, model_dir=self.model_dir
            )
            return result if result else {}
        except Exception as exc:
            logger.warning("30-sol LSTM forecast failed: %s", exc)
            return {}

    def get_seasonal_baseline(
        self, current_sol: int, lookahead: int = 90
    ) -> list[dict]:
        """Get seasonal baseline forecast for long-term crop planning.

        Uses the 668-sol Martian year seasonal model for crop cycle timing
        and winter preparation guidance.

        Args:
            current_sol: Current simulation sol number
            lookahead: Number of sols to look ahead for seasonal guidance (default 90)

        Returns:
            List of dicts with sol and predicted target values.
            Empty list if seasonal baseline is unavailable. [R8-H5]
        """
        # [R8-H5] Return empty list if baseline not loaded
        if self.seasonal_baseline is None:
            return []

        try:
            # [R5-H1] SeasonalBaseline.predict() returns {target: [values]} dict
            # Transpose to list of dicts format
            prediction = self.seasonal_baseline.predict(
                current_sol, lookahead=lookahead
            )
            if not prediction:
                return []

            # Get the target keys and their value lists
            target_keys = list(prediction.keys())
            if not target_keys:
                return []

            n_points = len(prediction[target_keys[0]])
            result = []
            for i in range(n_points):
                entry = {"sol": current_sol + i}
                for key in target_keys:
                    vals = prediction[key]
                    if i < len(vals):
                        entry[key] = vals[i]
                result.append(entry)

            return result

        except Exception as exc:
            logger.warning("Seasonal baseline forecast failed: %s", exc)
            return []

    def check_sensor_sanity(
        self,
        current_readings: dict,
        forecast: list[dict],
    ) -> list[dict]:
        """Check if current sensor readings deviate from LSTM 1-sol prediction.

        Uses model-grounded thresholds from test-set evaluation:
        - temp_std=3.5°C (based on max_temp MAE 3.49°C)
        - pressure_std=8.0 Pa (based on pressure MAE 7.70 Pa)

        Args:
            current_readings: Current weather dict from SimClient.get_weather_current()
            forecast: 7-sol LSTM forecast list from get_7sol_forecast()

        Returns:
            List of anomaly dicts, each with keys: field, measured, predicted, deviation.
            Empty list if no anomalies or no forecast available. [R5-H3]
        """
        if not forecast or not current_readings:
            return []

        try:
            # Compare against the 1-sol prediction (first entry in forecast)
            predicted = forecast[0]

            # [R5-H3] Map simulation field names to LSTM field names for comparison
            checks = [
                ("min_temp_c", "min_temp", 3.5),
                ("max_temp_c", "max_temp", 3.5),
                ("pressure_pa", "pressure", 8.0),
            ]

            anomalies = []
            for sim_field, lstm_field, std_threshold in checks:
                measured = current_readings.get(sim_field)
                predicted_val = predicted.get(lstm_field)

                if measured is None or predicted_val is None:
                    continue

                deviation = abs(measured - predicted_val)
                if deviation > 3 * std_threshold:
                    anomalies.append(
                        {
                            "field": sim_field,
                            "measured": measured,
                            "predicted": predicted_val,
                            "deviation": round(deviation, 2),
                            "sigma": round(deviation / std_threshold, 1),
                        }
                    )

            return anomalies

        except Exception as exc:
            logger.warning("Sensor sanity check failed: %s", exc)
            return []

    def get_full_context(
        self,
        current_sol: int,
        weather_history: list[dict],
        current_weather: dict | None = None,
    ) -> dict:
        """Get full LSTM weather context for injection into orchestrator prompt.

        [R9-H4] Method body:
        1. Get 7-sol autoregressive forecast
        2. Get 30-sol single-shot forecast
        3. Get seasonal baseline outlook
        4. Run sensor sanity check if current_weather and forecast_7sol both available

        Args:
            current_sol: Current simulation sol number
            weather_history: List of weather dicts from SimClient.get_weather_history()
            current_weather: Optional current weather dict for sanity checking

        Returns:
            Dict with keys:
            - forecast_7sol: list[dict] — may be empty for first ~30 sols [R8-C1]
            - forecast_30sol: dict — may be empty for first ~30 sols
            - seasonal_outlook: list[dict] — 668-sol seasonal guidance
            - sensor_anomalies: list[dict] — any flagged sensor deviations
        """
        forecast_7sol = self.get_7sol_forecast(weather_history)
        forecast_30sol = self.get_30sol_forecast(weather_history)
        seasonal_outlook = self.get_seasonal_baseline(current_sol)

        if current_weather and forecast_7sol:
            sensor_anomalies = self.check_sensor_sanity(current_weather, forecast_7sol)
        else:
            sensor_anomalies = []

        return {
            "forecast_7sol": forecast_7sol,
            "forecast_30sol": forecast_30sol,
            "seasonal_outlook": seasonal_outlook,
            "sensor_anomalies": sensor_anomalies,
        }
