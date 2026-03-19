"""Unit tests for SimClient — verifies all endpoint paths and request bodies.

Uses respx to mock httpx requests. Tests verify field names match
simulation Pydantic models exactly. [C-1, C-2, C-3, H-1, H-2, HIGH-3]
"""

from __future__ import annotations

import pytest
import respx
import httpx
import json


@pytest.fixture
def client():
    """Create a SimClient pointing at a mock URL."""
    from src.sim_client import SimClient
    return SimClient("http://testserver")


@respx.mock
def test_get_sim_status(client):
    """Test that get_sim_status() calls GET /sim/status."""
    respx.get("http://testserver/sim/status").mock(
        return_value=httpx.Response(200, json={"current_sol": 0, "mission_phase": "active"})
    )
    result = client.get_sim_status()
    assert result["current_sol"] == 0
    assert respx.calls[0].request.url.path == "/sim/status"


@respx.mock
def test_plant_crop_uses_type_key(client):
    """Test that plant_crop sends JSON key 'type' NOT 'crop_type'. [C-2]"""
    respx.post("http://testserver/crops/plant").mock(
        return_value=httpx.Response(200, json={"crop_id": "abc123"})
    )
    client.plant_crop(crop_type="potato", zone_id="A", area_m2=6.0)
    request = respx.calls[0].request
    body = json.loads(request.content)
    assert "type" in body, "plant_crop must send JSON key 'type', not 'crop_type'"
    assert body["type"] == "potato"
    assert "crop_type" not in body


@respx.mock
def test_set_irrigation_uses_correct_field_name(client):
    """Test that set_irrigation sends irrigation_liters_per_sol (NOT liters_per_sol). [C-1]"""
    respx.post("http://testserver/water/set_irrigation").mock(
        return_value=httpx.Response(200, json={"status": "ok"})
    )
    client.set_irrigation(zone_id="B", irrigation_liters_per_sol=5.0)
    request = respx.calls[0].request
    body = json.loads(request.content)
    assert "irrigation_liters_per_sol" in body, "Must use irrigation_liters_per_sol"
    assert body["irrigation_liters_per_sol"] == 5.0
    assert "liters_per_sol" not in body or body.get("liters_per_sol") is None


@respx.mock
def test_adjust_nutrients_uses_target_ec_ms_cm(client):
    """Test that adjust_nutrients sends target_ec_ms_cm (NOT target_ec). [C-3]"""
    respx.post("http://testserver/nutrients/adjust").mock(
        return_value=httpx.Response(200, json={"status": "ok"})
    )
    client.adjust_nutrients(zone_id="C", target_ec_ms_cm=2.5)
    request = respx.calls[0].request
    body = json.loads(request.content)
    assert "target_ec_ms_cm" in body, "Must use target_ec_ms_cm"
    assert body["target_ec_ms_cm"] == 2.5
    assert "target_ec" not in body or body.get("target_ec") is None


@respx.mock
def test_get_crop_catalog_uses_correct_path(client):
    """Test that get_crop_catalog() calls GET /crops/catalog. [H-1]"""
    respx.get("http://testserver/crops/catalog").mock(
        return_value=httpx.Response(200, json={"crops": []})
    )
    result = client.get_crop_catalog()
    assert result == {"crops": []}
    assert respx.calls[0].request.url.path == "/crops/catalog"


@respx.mock
def test_get_weather_history_uses_correct_path(client):
    """Test that get_weather_history() calls GET /weather/history. [H-2]"""
    respx.get("http://testserver/weather/history").mock(
        return_value=httpx.Response(200, json=[])
    )
    result = client.get_weather_history(last_n_sols=30)
    assert isinstance(result, list)
    assert respx.calls[0].request.url.path == "/weather/history"


@respx.mock
def test_read_all_telemetry_calls_exactly_14_endpoints(client):
    """Test that read_all_telemetry() calls exactly 14 GET endpoints. [HIGH-3]"""
    # Mock all expected endpoints
    endpoints = [
        "/sim/status",
        "/weather/current",
        "/weather/history",
        "/weather/forecast",
        "/energy/status",
        "/greenhouse/environment",
        "/water/status",
        "/crops/status",
        "/nutrients/status",
        "/crew/nutrition",
        "/sensors/readings",
        "/events/log",
        "/events/active_crises",
        "/score/current",
    ]
    for endpoint in endpoints:
        respx.get(f"http://testserver{endpoint}").mock(
            return_value=httpx.Response(200, json={})
        )

    # Make sure score/final is NOT called
    respx.get("http://testserver/score/final").mock(
        return_value=httpx.Response(400, json={"error": "mission not complete"})
    )
    respx.get("http://testserver/crops/catalog").mock(
        return_value=httpx.Response(200, json={})
    )

    result = client.read_all_telemetry()

    # Verify exactly the 14 expected endpoints were called
    called_paths = [call.request.url.path for call in respx.calls]
    for endpoint in endpoints:
        assert endpoint in called_paths, f"Expected {endpoint} to be called"

    # Verify score/final was NOT called
    assert "/score/final" not in called_paths, "read_all_telemetry must NOT call /score/final"
    # Verify crop catalog was NOT called
    assert "/crops/catalog" not in called_paths, "read_all_telemetry must NOT call /crops/catalog"

    # Verify returned dict has all 14 keys
    expected_keys = [
        "sim_status", "weather_current", "weather_history", "weather_forecast",
        "energy_status", "greenhouse_environment", "water_status", "crops_status",
        "nutrients_status", "crew_nutrition", "sensors_readings", "events_log",
        "active_crises", "score_current",
    ]
    for key in expected_keys:
        assert key in result, f"Missing key: {key}"


@respx.mock
def test_advance_sends_sols_to_correct_endpoint(client):
    """Test that advance() sends sols to POST /sim/advance. [CRITICAL-4/5]"""
    respx.post("http://testserver/sim/advance").mock(
        return_value=httpx.Response(200, json={"new_sol": 1, "mission_phase": "active", "events": []})
    )
    result = client.advance(sols=1)
    request = respx.calls[0].request
    body = json.loads(request.content)
    assert body["sols"] == 1
    assert result["new_sol"] == 1


@respx.mock
def test_reset_sends_to_correct_endpoint(client):
    """Test that reset() sends seed and difficulty to POST /sim/reset. [CRITICAL-4/5]"""
    respx.post("http://testserver/sim/reset").mock(
        return_value=httpx.Response(200, json={"status": "reset"})
    )
    client.reset(seed=42, difficulty="hard")
    request = respx.calls[0].request
    body = json.loads(request.content)
    assert body["seed"] == 42
    assert body["difficulty"] == "hard"


@respx.mock
def test_log_decision_sends_to_correct_endpoint(client):
    """Test that log_decision() sends to POST /agent/log_decision. [CRITICAL-4/5]"""
    respx.post("http://testserver/agent/log_decision").mock(
        return_value=httpx.Response(200, json={"status": "logged"})
    )
    client.log_decision(sol=5, decisions=["plant potato zone_A 6m2"])
    request = respx.calls[0].request
    assert request.url.path == "/agent/log_decision"
    body = json.loads(request.content)
    assert body["sol"] == 5
    assert "decisions" in body


@respx.mock
def test_http_error_handling(client):
    """Test that HTTP errors are raised via raise_for_status."""
    respx.get("http://testserver/sim/status").mock(
        return_value=httpx.Response(500, json={"error": "internal server error"})
    )
    with pytest.raises(httpx.HTTPStatusError):
        client.get_sim_status()


@respx.mock
def test_allocate_energy_sends_correct_body(client):
    """Test that allocate_energy sends all percentage fields."""
    respx.post("http://testserver/energy/allocate").mock(
        return_value=httpx.Response(200, json={"status": "ok"})
    )
    client.allocate_energy(
        heating_pct=47.0,
        lighting_pct=30.0,
        water_recycling_pct=12.0,
        nutrient_pumps_pct=5.0,
        reserve_pct=6.0,
    )
    request = respx.calls[0].request
    body = json.loads(request.content)
    assert body["heating_pct"] == 47.0
    assert body["lighting_pct"] == 30.0
    assert body["water_recycling_pct"] == 12.0
    assert body["nutrient_pumps_pct"] == 5.0
    assert body["reserve_pct"] == 6.0


@respx.mock
def test_harvest_crop_sends_crop_id(client):
    """Test that harvest_crop sends crop_id to POST /crops/harvest."""
    respx.post("http://testserver/crops/harvest").mock(
        return_value=httpx.Response(200, json={"yield_kg": 5.0})
    )
    client.harvest_crop(crop_id="crop-abc-123")
    request = respx.calls[0].request
    body = json.loads(request.content)
    assert body["crop_id"] == "crop-abc-123"
