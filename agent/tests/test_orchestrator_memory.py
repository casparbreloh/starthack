"""Unit tests for orchestrator construction."""

from __future__ import annotations

from unittest.mock import MagicMock, patch


def _make_snapshot() -> dict:
    return {
        "sim_status": {"current_sol": 0},
        "active_crises": {"crises": []},
        "weather_history": [],
        "weather_current": {},
        "energy_status": {},
        "score_current": {"scores": {"overall_score": 50.0}},
        "water_status": {},
        "greenhouse_environment": {"zones": []},
        "crops_status": {"crops": []},
        "crew_nutrition": {"days_of_food_remaining": 0},
        "nutrients_status": {"nutrient_stock_remaining_pct": 100},
    }


def test_create_orchestrator_without_session_manager():
    """create_orchestrator() omits session_manager when not provided."""
    mock_agent_cls = MagicMock()
    mock_agent_instance = MagicMock()
    mock_agent_cls.return_value = mock_agent_instance
    telemetry_tools = {
        "read_all_telemetry": MagicMock(),
        "get_crop_catalog": MagicMock(),
    }
    action_tools = {"allocate_energy": MagicMock(), "set_irrigation": MagicMock()}

    with (
        patch("src.agents.orchestrator.Agent", mock_agent_cls),
        patch("src.agents.orchestrator.BedrockModel", MagicMock()),
        patch(
            "src.agents.orchestrator.create_telemetry_tools",
            return_value=telemetry_tools,
        ),
        patch(
            "src.agents.orchestrator.create_action_tools",
            return_value=action_tools,
        ),
    ):
        from src.agents.orchestrator import create_orchestrator

        agent = create_orchestrator(_make_snapshot())

    assert agent is mock_agent_instance
    call_kwargs = mock_agent_cls.call_args.kwargs
    assert "session_manager" not in call_kwargs
    assert telemetry_tools["read_all_telemetry"] in call_kwargs["tools"]
    assert action_tools["allocate_energy"] in call_kwargs["tools"]


def test_create_orchestrator_with_session_manager():
    """create_orchestrator() forwards session_manager to Agent."""
    mock_agent_cls = MagicMock()
    mock_agent_cls.return_value = MagicMock()
    mock_session_manager = MagicMock()

    with (
        patch("src.agents.orchestrator.Agent", mock_agent_cls),
        patch("src.agents.orchestrator.BedrockModel", MagicMock()),
        patch(
            "src.agents.orchestrator.create_telemetry_tools",
            return_value={
                "read_all_telemetry": MagicMock(),
                "get_crop_catalog": MagicMock(),
            },
        ),
        patch(
            "src.agents.orchestrator.create_action_tools",
            return_value={"allocate_energy": MagicMock()},
        ),
    ):
        from src.agents.orchestrator import create_orchestrator

        create_orchestrator(_make_snapshot(), session_manager=mock_session_manager)

    call_kwargs = mock_agent_cls.call_args.kwargs
    assert call_kwargs["session_manager"] is mock_session_manager


def test_create_orchestrator_extra_tools_included():
    """create_orchestrator() includes extra_tools in the Agent tool list."""
    mock_agent_cls = MagicMock()
    mock_agent_cls.return_value = MagicMock()
    mock_extra_tool = MagicMock()
    mock_extra_tool.__name__ = "strategic_memory"

    with (
        patch("src.agents.orchestrator.Agent", mock_agent_cls),
        patch("src.agents.orchestrator.BedrockModel", MagicMock()),
        patch(
            "src.agents.orchestrator.create_telemetry_tools",
            return_value={
                "read_all_telemetry": MagicMock(),
                "get_crop_catalog": MagicMock(),
            },
        ),
        patch(
            "src.agents.orchestrator.create_action_tools",
            return_value={"allocate_energy": MagicMock()},
        ),
    ):
        from src.agents.orchestrator import create_orchestrator

        create_orchestrator(_make_snapshot(), extra_tools=[mock_extra_tool])

    tools = mock_agent_cls.call_args.kwargs["tools"]
    assert mock_extra_tool in tools


def test_create_orchestrator_adds_memory_prompt_section_with_session_manager():
    """create_orchestrator() appends the memory prompt when memory is enabled."""
    mock_agent_cls = MagicMock()
    mock_agent_cls.return_value = MagicMock()

    with (
        patch("src.agents.orchestrator.Agent", mock_agent_cls),
        patch("src.agents.orchestrator.BedrockModel", MagicMock()),
        patch(
            "src.agents.orchestrator.create_telemetry_tools",
            return_value={
                "read_all_telemetry": MagicMock(),
                "get_crop_catalog": MagicMock(),
            },
        ),
        patch(
            "src.agents.orchestrator.create_action_tools",
            return_value={"allocate_energy": MagicMock()},
        ),
    ):
        from src.agents.orchestrator import create_orchestrator

        create_orchestrator(_make_snapshot(), session_manager=MagicMock())

    system_prompt = mock_agent_cls.call_args.kwargs["system_prompt"]
    assert "Strategic Memory" in system_prompt


def test_create_orchestrator_omits_memory_prompt_without_session_manager():
    """create_orchestrator() keeps the base prompt when memory is disabled."""
    mock_agent_cls = MagicMock()
    mock_agent_cls.return_value = MagicMock()

    with (
        patch("src.agents.orchestrator.Agent", mock_agent_cls),
        patch("src.agents.orchestrator.BedrockModel", MagicMock()),
        patch(
            "src.agents.orchestrator.create_telemetry_tools",
            return_value={
                "read_all_telemetry": MagicMock(),
                "get_crop_catalog": MagicMock(),
            },
        ),
        patch(
            "src.agents.orchestrator.create_action_tools",
            return_value={"allocate_energy": MagicMock()},
        ),
    ):
        from src.agents.orchestrator import create_orchestrator

        create_orchestrator(_make_snapshot())

    system_prompt = mock_agent_cls.call_args.kwargs["system_prompt"]
    assert "Strategic Memory" not in system_prompt
