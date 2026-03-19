"""Unit tests for orchestrator memory integration.

Verifies that:
  - create_orchestrator() passes session_manager to Agent when provided
  - create_orchestrator() without session_manager works as before (backward compat)
  - extra_tools are included in the Agent's tool list when provided
  - MEMORY_PROMPT_SECTION is included in system prompt when session_manager given
  - run_mission() branches correctly on memory_enabled

All AWS/Strands Agent calls are mocked.
"""

from __future__ import annotations

from unittest.mock import MagicMock, patch, call


# ============================================================================
# create_orchestrator() tests
# ============================================================================


def _make_mock_client():
    """Build a minimal mock SimClient."""
    mock = MagicMock()
    mock.read_all_telemetry.return_value = {
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
    return mock


def test_create_orchestrator_without_session_manager():
    """create_orchestrator() without session_manager creates Agent without it."""
    mock_agent_cls = MagicMock()
    mock_agent_instance = MagicMock()
    mock_agent_cls.return_value = mock_agent_instance
    mock_model_cls = MagicMock()

    with (
        patch("src.agents.orchestrator.Agent", mock_agent_cls),
        patch("src.agents.orchestrator.BedrockModel", mock_model_cls),
        patch("src.agents.orchestrator.create_telemetry_tools", return_value={"read_all_telemetry": MagicMock(), "get_crop_catalog": MagicMock()}),
        patch("src.agents.orchestrator.create_action_tools", return_value={"advance_simulation": MagicMock(), "irrigate": MagicMock()}),
    ):
        from src.agents.orchestrator import create_orchestrator

        agent, funcs = create_orchestrator(_make_mock_client())

        # Agent called without session_manager kwarg
        call_kwargs = mock_agent_cls.call_args.kwargs
        assert "session_manager" not in call_kwargs
        assert "advance_simulation" in funcs


def test_create_orchestrator_with_session_manager():
    """create_orchestrator() with session_manager passes it to Agent constructor."""
    mock_agent_cls = MagicMock()
    mock_agent_instance = MagicMock()
    mock_agent_cls.return_value = mock_agent_instance
    mock_model_cls = MagicMock()
    mock_session_manager = MagicMock()

    with (
        patch("src.agents.orchestrator.Agent", mock_agent_cls),
        patch("src.agents.orchestrator.BedrockModel", mock_model_cls),
        patch("src.agents.orchestrator.create_telemetry_tools", return_value={"read_all_telemetry": MagicMock(), "get_crop_catalog": MagicMock()}),
        patch("src.agents.orchestrator.create_action_tools", return_value={"advance_simulation": MagicMock(), "irrigate": MagicMock()}),
    ):
        from src.agents.orchestrator import create_orchestrator

        agent, funcs = create_orchestrator(
            _make_mock_client(),
            session_manager=mock_session_manager,
        )

        call_kwargs = mock_agent_cls.call_args.kwargs
        assert "session_manager" in call_kwargs
        assert call_kwargs["session_manager"] is mock_session_manager


def test_create_orchestrator_extra_tools_included():
    """create_orchestrator() with extra_tools includes them in the Agent tool list."""
    mock_agent_cls = MagicMock()
    mock_agent_cls.return_value = MagicMock()
    mock_extra_tool = MagicMock()
    mock_extra_tool.__name__ = "strategic_memory"

    with (
        patch("src.agents.orchestrator.Agent", mock_agent_cls),
        patch("src.agents.orchestrator.BedrockModel", MagicMock()),
        patch("src.agents.orchestrator.create_telemetry_tools", return_value={"read_all_telemetry": MagicMock(), "get_crop_catalog": MagicMock()}),
        patch("src.agents.orchestrator.create_action_tools", return_value={"advance_simulation": MagicMock(), "irrigate": MagicMock()}),
    ):
        from src.agents.orchestrator import create_orchestrator

        create_orchestrator(
            _make_mock_client(),
            extra_tools=[mock_extra_tool],
        )

        call_kwargs = mock_agent_cls.call_args.kwargs
        tools = call_kwargs["tools"]
        assert mock_extra_tool in tools


def test_create_orchestrator_memory_prompt_section_added_with_session_manager():
    """create_orchestrator() appends MEMORY_PROMPT_SECTION to system prompt when session_manager given."""
    mock_agent_cls = MagicMock()
    mock_agent_cls.return_value = MagicMock()
    mock_session_manager = MagicMock()

    with (
        patch("src.agents.orchestrator.Agent", mock_agent_cls),
        patch("src.agents.orchestrator.BedrockModel", MagicMock()),
        patch("src.agents.orchestrator.create_telemetry_tools", return_value={"read_all_telemetry": MagicMock(), "get_crop_catalog": MagicMock()}),
        patch("src.agents.orchestrator.create_action_tools", return_value={"advance_simulation": MagicMock(), "irrigate": MagicMock()}),
    ):
        from src.agents.orchestrator import create_orchestrator

        create_orchestrator(
            _make_mock_client(),
            session_manager=mock_session_manager,
        )

        call_kwargs = mock_agent_cls.call_args.kwargs
        system_prompt = call_kwargs["system_prompt"]
        assert "Strategic Memory" in system_prompt


def test_create_orchestrator_no_memory_prompt_without_session_manager():
    """create_orchestrator() without session_manager does NOT add Strategic Memory section."""
    mock_agent_cls = MagicMock()
    mock_agent_cls.return_value = MagicMock()

    with (
        patch("src.agents.orchestrator.Agent", mock_agent_cls),
        patch("src.agents.orchestrator.BedrockModel", MagicMock()),
        patch("src.agents.orchestrator.create_telemetry_tools", return_value={"read_all_telemetry": MagicMock(), "get_crop_catalog": MagicMock()}),
        patch("src.agents.orchestrator.create_action_tools", return_value={"advance_simulation": MagicMock(), "irrigate": MagicMock()}),
    ):
        from src.agents.orchestrator import create_orchestrator

        create_orchestrator(_make_mock_client())

        call_kwargs = mock_agent_cls.call_args.kwargs
        system_prompt = call_kwargs["system_prompt"]
        assert "Strategic Memory" not in system_prompt


# ============================================================================
# run_mission() branching tests
# ============================================================================


def _build_minimal_run_mission_mocks(memory_enabled_value: bool):
    """Build the stack of mocks needed to call run_mission() without real I/O."""
    mock_client = _make_mock_client()
    mock_client.reset.return_value = {}
    mock_client.get_active_crises.return_value = {"crises": []}
    mock_client.get_score_current.return_value = {"scores": {"overall_score": 60.0}}
    mock_client.get_sim_status.return_value = {"mission_phase": "active"}
    mock_client.log_decision.return_value = {}

    mock_agent = MagicMock()
    mock_agent_result = MagicMock()
    mock_agent_result.message = {"content": []}
    mock_agent.return_value = mock_agent_result
    # __call__ needed because Agent is called as a callable
    mock_agent.__call__ = MagicMock(return_value=mock_agent_result)

    # advance_simulation returns complete immediately
    mock_advance = MagicMock(return_value={"mission_phase": "complete"})

    return mock_client, mock_agent, mock_advance, memory_enabled_value


def test_run_mission_legacy_path_creates_orchestrator_per_sol():
    """With memory_enabled=False, run_mission() creates a fresh orchestrator each sol."""
    mock_client = _make_mock_client()
    mock_client.reset.return_value = {}
    mock_client.get_active_crises.return_value = {"crises": []}
    mock_client.get_score_current.return_value = {"scores": {"overall_score": 60.0}}
    mock_client.log_decision.return_value = {}

    create_orchestrator_calls = []

    mock_agent_instance = MagicMock()
    mock_result = MagicMock()
    mock_result.message = {"content": []}
    mock_agent_instance.return_value = mock_result

    def fake_create_orchestrator(client, cross_session_context="", kb_tools=None, session_manager=None, extra_tools=None):
        create_orchestrator_calls.append({"session_manager": session_manager})
        funcs = {"advance_simulation": MagicMock(return_value={"mission_phase": "complete"})}
        return mock_agent_instance, funcs

    mock_cross_session = MagicMock()
    mock_cross_session.format_for_prompt.return_value = ""
    mock_cross_session.save_summary.return_value = None

    with (
        patch("src.agents.orchestrator.memory_enabled", False),
        patch("src.agents.orchestrator.create_orchestrator", side_effect=fake_create_orchestrator),
        patch("src.agents.orchestrator.set_client"),
        patch("src.agents.orchestrator.create_mcp_client") as mock_mcp,
        patch("src.agents.orchestrator.discover_kb_tools", return_value=[]),
        patch("src.agents.orchestrator.WeatherForecaster") as mock_wf,
        patch("src.agents.orchestrator.CrossSessionLearning", return_value=mock_cross_session),
    ):
        mock_mcp.return_value.__enter__ = MagicMock(return_value=MagicMock())
        mock_mcp.return_value.__exit__ = MagicMock(return_value=False)
        mock_wf.return_value.get_full_context.return_value = {"forecast_7sol": [], "sensor_anomalies": []}

        from src.agents.orchestrator import run_mission

        # Run 1 sol
        result = run_mission(mock_client, seed=0, difficulty="easy", mission_sols=1)

    # With legacy path: create_orchestrator called once per sol (plus once for summary)
    # At least one call should have session_manager=None
    calls_without_sm = [c for c in create_orchestrator_calls if c["session_manager"] is None]
    assert len(calls_without_sm) >= 1, "Legacy path must call create_orchestrator without session_manager"
    assert "run_id" in result
