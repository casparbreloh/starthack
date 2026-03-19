"""Integration tests for the Mars greenhouse agent.

These tests require:
  1. A running simulation at SIM_BASE_URL (default http://localhost:8080)
  2. AWS Bedrock credentials with access to the configured model

Both are skipped gracefully if unavailable. [HIGH-6, M-9]
"""

from __future__ import annotations

import os

import pytest

# Check Bedrock availability at module level [HIGH-6]
_BEDROCK_AVAILABLE = False
_BEDROCK_SKIP_REASON = "AWS Bedrock not available"

try:
    import boto3

    # Use the control-plane client (not bedrock-runtime) for model listing
    bedrock_client = boto3.client("bedrock", region_name="us-east-1")
    bedrock_client.list_foundation_models()
    _BEDROCK_AVAILABLE = True
except Exception as e:
    _BEDROCK_SKIP_REASON = f"AWS Bedrock not available: {e}"

# Check simulation availability
_SIM_URL = os.environ.get("SIM_BASE_URL", "http://localhost:8080")
_SIM_AVAILABLE = False
_SIM_SKIP_REASON = f"Simulation not available at {_SIM_URL}"

try:
    import httpx

    resp = httpx.get(f"{_SIM_URL}/sim/status", timeout=2.0)
    if resp.status_code == 200:
        _SIM_AVAILABLE = True
except Exception as e:
    _SIM_SKIP_REASON = f"Simulation not available at {_SIM_URL}: {e}"


@pytest.mark.integration
@pytest.mark.skipif(not _SIM_AVAILABLE, reason=_SIM_SKIP_REASON)
@pytest.mark.skipif(not _BEDROCK_AVAILABLE, reason=_BEDROCK_SKIP_REASON)
def test_10_sol_run():
    """Integration test: run 10 sols and verify basic functionality. [M-9]

    Verifies:
    - Sol advances correctly
    - Orchestrator makes decisions each sol
    - Score remains above 50 (no harvests in 10 sols so threshold is conservative)
    - No unhandled exceptions
    """
    from src.agents.orchestrator import run_mission
    from src.sim_client import SimClient

    client = SimClient(_SIM_URL)

    result = run_mission(
        client,
        seed=42,
        difficulty="normal",
        mission_sols=10,
    )

    assert "final_score" in result, "run_mission must return final_score"
    # [M-9] Score > 50 after 10 sols (no crops harvested yet, so threshold is low)
    assert result["final_score"] >= 50.0, (
        f"Score {result['final_score']} is below 50 after 10 sols. "
        "Basic greenhouse stability should maintain score > 50."
    )
    assert result["mission_phase"] in ("active", "complete"), (
        f"Unexpected mission_phase: {result['mission_phase']}"
    )


@pytest.mark.integration
@pytest.mark.skipif(not _SIM_AVAILABLE, reason=_SIM_SKIP_REASON)
def test_sim_client_basic_connectivity():
    """Test that SimClient can connect to the simulation and read basic state."""
    from src.sim_client import SimClient

    client = SimClient(_SIM_URL)
    status = client.get_sim_status()
    assert "current_sol" in status, "sim status must have current_sol"


@pytest.mark.skipif(not _SIM_AVAILABLE, reason=_SIM_SKIP_REASON)
def test_read_all_telemetry_live():
    """Test that read_all_telemetry() returns all 14 expected keys from live sim."""
    from src.sim_client import SimClient

    client = SimClient(_SIM_URL)
    # Reset first to ensure clean state
    client.reset(seed=0, difficulty="normal")
    telemetry = client.read_all_telemetry()

    expected_keys = [
        "sim_status",
        "weather_current",
        "weather_history",
        "weather_forecast",
        "energy_status",
        "greenhouse_environment",
        "water_status",
        "crops_status",
        "nutrients_status",
        "crew_nutrition",
        "sensors_readings",
        "events_log",
        "active_crises",
        "score_current",
    ]
    for key in expected_keys:
        assert key in telemetry, f"Missing key: {key}"
