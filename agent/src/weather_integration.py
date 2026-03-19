"""LSTM weather model integration for the Mars greenhouse agent.

Calls the ML forecast sidecar service via HTTP to get weather predictions.
This avoids bundling torch/sklearn/pandas in the agent image.

The LSTM models were trained on Curiosity rover data (4,586 sols). By feeding
simulation weather history as context, the forecasts reflect the simulation's
actual weather trajectory, not static Curiosity data. [ARCH-1, R5-C2]
"""

from __future__ import annotations

import logging

import httpx

from .config import ML_SERVICE_URL

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

    Calls the ML forecast service to provide:
    - 7-sol autoregressive forecast
    - 30-sol single-shot forecast
    - 668-sol seasonal baseline outlook
    - Sensor sanity checking (3-sigma deviation detection)
    """

    def __init__(self, service_url: str = ML_SERVICE_URL) -> None:
        self._client = httpx.Client(base_url=service_url, timeout=30.0)

    def _sim_history_to_lstm_records(self, weather_history: list[dict]) -> list[dict]:
        """Convert simulation weather history to LSTM-compatible records.

        Maps simulation field names to LSTM field names via SIM_TO_LSTM_FIELDS.
        Sets min_gts_temp and max_gts_temp to None since simulation does not
        provide ground temperature sensors — the ML service handles imputation.
        """
        if not weather_history:
            return []

        records = []
        for row in weather_history:
            mapped = {}
            for key, value in row.items():
                mapped_key = SIM_TO_LSTM_FIELDS.get(key, key)
                mapped[mapped_key] = value
            mapped["min_gts_temp"] = None
            mapped["max_gts_temp"] = None
            records.append(mapped)

        return records

    def get_7sol_forecast(self, weather_history: list[dict]) -> list[dict]:
        """Get 7-sol autoregressive forecast from simulation weather history.

        Returns:
            List of up to 7 forecast dicts. Empty list on failure.
        """
        try:
            records = self._sim_history_to_lstm_records(weather_history)
            if not records:
                return []
            resp = self._client.post(
                "/predict",
                json={"weather_history": records, "n_sols": 7},
            )
            resp.raise_for_status()
            return resp.json().get("forecast", [])
        except Exception as exc:
            logger.warning("7-sol LSTM forecast failed: %s", exc)
            return []

    def get_30sol_forecast(self, weather_history: list[dict]) -> dict:
        """Get 30-sol single-shot forecast from simulation weather history.

        Returns:
            Single forecast dict. Empty dict on failure.
        """
        try:
            records = self._sim_history_to_lstm_records(weather_history)
            if not records:
                return {}
            resp = self._client.post(
                "/predict_at_horizon",
                json={"weather_history": records, "horizon": 30},
            )
            resp.raise_for_status()
            return resp.json().get("forecast", {})
        except Exception as exc:
            logger.warning("30-sol LSTM forecast failed: %s", exc)
            return {}

    def get_seasonal_baseline(
        self, current_sol: int, lookahead: int = 90
    ) -> list[dict]:
        """Get seasonal baseline forecast for long-term crop planning.

        Returns:
            List of dicts with sol and predicted target values.
            Empty list if unavailable.
        """
        try:
            resp = self._client.post(
                "/seasonal_baseline",
                json={"current_sol": current_sol, "lookahead": lookahead},
            )
            resp.raise_for_status()
            return resp.json().get("forecast", [])
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
