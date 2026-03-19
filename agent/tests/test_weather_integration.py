"""Unit tests for WeatherForecaster — verifies HTTP contract with ML sidecar.

Uses respx to mock httpx requests. Tests verify endpoint paths, payload
mapping via SIM_TO_LSTM_FIELDS, and error handling.
"""

from __future__ import annotations

import httpx
import pytest
import respx

from src.weather_integration import WeatherForecaster

ML_URL = "http://testserver"


@pytest.fixture
def forecaster():
    """Create a WeatherForecaster pointing at a mock URL."""
    return WeatherForecaster(service_url=ML_URL)


SAMPLE_SIM_HISTORY = [
    {"sol": 1, "min_temp_c": -70.0, "max_temp_c": -10.0, "pressure_pa": 800.0},
    {"sol": 2, "min_temp_c": -68.0, "max_temp_c": -12.0, "pressure_pa": 810.0},
]


@respx.mock
def test_get_7sol_forecast(forecaster):
    """Test 7-sol forecast calls POST /predict with mapped field names."""
    forecast_data = [{"sol": 3, "min_temp": -65.0, "max_temp": -8.0, "pressure": 805.0}]
    route = respx.post(f"{ML_URL}/predict").mock(
        return_value=httpx.Response(200, json={"forecast": forecast_data})
    )

    result = forecaster.get_7sol_forecast(SAMPLE_SIM_HISTORY)

    assert result == forecast_data
    assert route.called
    body = route.calls[0].request.read()
    import json

    payload = json.loads(body)
    assert payload["n_sols"] == 7
    # Verify field names were mapped from sim -> LSTM format
    rec = payload["weather_history"][0]
    assert "min_temp" in rec
    assert "max_temp" in rec
    assert "pressure" in rec
    assert "min_temp_c" not in rec
    # Ground temps should be set to None
    assert rec["min_gts_temp"] is None
    assert rec["max_gts_temp"] is None


@respx.mock
def test_get_30sol_forecast(forecaster):
    """Test 30-sol forecast calls POST /predict_at_horizon."""
    forecast_data = {"sol": 32, "min_temp": -60.0, "max_temp": -5.0, "pressure": 820.0}
    route = respx.post(f"{ML_URL}/predict_at_horizon").mock(
        return_value=httpx.Response(200, json={"forecast": forecast_data})
    )

    result = forecaster.get_30sol_forecast(SAMPLE_SIM_HISTORY)

    assert result == forecast_data
    assert route.called
    import json

    payload = json.loads(route.calls[0].request.read())
    assert payload["horizon"] == 30


@respx.mock
def test_get_seasonal_baseline(forecaster):
    """Test seasonal baseline calls POST /seasonal_baseline."""
    forecast_data = [{"sol": 100, "min_temp": -55.0}]
    route = respx.post(f"{ML_URL}/seasonal_baseline").mock(
        return_value=httpx.Response(200, json={"forecast": forecast_data})
    )

    result = forecaster.get_seasonal_baseline(current_sol=100, lookahead=30)

    assert result == forecast_data
    assert route.called
    import json

    payload = json.loads(route.calls[0].request.read())
    assert payload["current_sol"] == 100
    assert payload["lookahead"] == 30


@respx.mock
def test_get_7sol_forecast_http_error(forecaster):
    """Test graceful handling of HTTP errors."""
    respx.post(f"{ML_URL}/predict").mock(
        return_value=httpx.Response(500, json={"detail": "internal error"})
    )

    result = forecaster.get_7sol_forecast(SAMPLE_SIM_HISTORY)
    assert result == []


@respx.mock
def test_get_7sol_forecast_empty_history(forecaster):
    """Test empty history returns empty list without making HTTP call."""
    route = respx.post(f"{ML_URL}/predict")

    result = forecaster.get_7sol_forecast([])
    assert result == []
    assert not route.called


def test_context_manager():
    """Test WeatherForecaster can be used as a context manager."""
    with WeatherForecaster(service_url=ML_URL) as wf:
        assert wf is not None
