"""Configuration for the Mars greenhouse agent system."""

import os
from pathlib import Path

# -- Directory layout --
_SRC_DIR = Path(__file__).parent  # agent/src/
_AGENT_DIR = _SRC_DIR.parent  # agent/

# -- Environment variables (with defaults) --
SIM_BASE_URL: str = os.environ.get("SIM_BASE_URL", "http://localhost:8080")
MODEL_ID: str = os.environ.get(
    "MODEL_ID",
    "us.anthropic.claude-sonnet-4-6",
)
AGENT_TEMPERATURE: float = float(os.environ.get("AGENT_TEMPERATURE", "0.3"))
AGENTCORE_GATEWAY_URL: str = os.environ.get(
    "AGENTCORE_GATEWAY_URL",
    "https://kb-start-hack-gateway-buyjtibfpg.gateway.bedrock-agentcore.us-east-2.amazonaws.com/mcp",
)
ML_SERVICE_URL: str = os.environ.get("ML_SERVICE_URL", "http://localhost:8090")

# -- Zone constants --
ZONE_IDS: list[str] = ["A", "B", "C"]
ZONE_AREAS: dict[str, float] = {"A": 12.0, "B": 18.0, "C": 20.0}

# -- Mission constants --
MISSION_SOLS: int = 450
VALID_DIFFICULTIES: list[str] = ["easy", "normal", "hard"]

# -- Energy projection constants --
SOLAR_PANEL_AREA_M2: int = 80
SOLAR_PANEL_EFFICIENCY: float = 0.18
EFFECTIVE_SOLAR_HOURS_PER_SOL: int = 8

# -- Path constants --
SESSION_LOGS_DIR: str = str(_AGENT_DIR / "session_logs")
