"""Unit tests for src/tools/memory_tool.py — strategic_memory @tool function.

All MemoryClient calls are mocked. Tests verify the tool routes correctly
to create_event (RECORD) and retrieve_memories (RETRIEVE), and returns
sensible error messages for invalid inputs.
"""

from __future__ import annotations

from unittest.mock import MagicMock


def _make_tool():
    """Create a strategic_memory tool with a fresh mock MemoryClient."""
    mock_client = MagicMock()
    from src.tools.memory_tool import create_memory_tools

    tools = create_memory_tools(
        memory_client=mock_client,
        memory_id="test-memory-id",
        actor_id="mars-agent",
        session_id="run_test_session",
    )
    return tools["strategic_memory"], mock_client


def test_create_memory_tools_returns_dict_with_strategic_memory():
    """create_memory_tools() returns a dict containing 'strategic_memory' key."""
    mock_client = MagicMock()
    from src.tools.memory_tool import create_memory_tools

    tools = create_memory_tools(
        memory_client=mock_client,
        memory_id="test-memory-id",
        actor_id="mars-agent",
        session_id="run_test",
    )

    assert isinstance(tools, dict)
    assert "strategic_memory" in tools
    assert callable(tools["strategic_memory"])


def test_record_action_calls_create_event():
    """RECORD action calls memory_client.create_event with messages list."""
    strategic_memory, mock_client = _make_tool()

    result = strategic_memory(
        action="RECORD",
        content="Plant potatoes in Zone C before sol 50 to prevent food shortage.",
    )

    assert mock_client.create_event.call_count == 1
    call_kwargs = mock_client.create_event.call_args
    assert call_kwargs.kwargs["memory_id"] == "test-memory-id"
    assert call_kwargs.kwargs["actor_id"] == "mars-agent"
    assert call_kwargs.kwargs["session_id"] == "run_test_session"
    messages = call_kwargs.kwargs["messages"]
    assert isinstance(messages, list)
    assert len(messages) == 1
    role, content = messages[0]
    assert role == "user"
    assert "Plant potatoes" in content
    assert "Strategic learning recorded" in result


def test_record_action_lowercase_works():
    """RECORD action is case-insensitive (lowercase 'record' works)."""
    strategic_memory, mock_client = _make_tool()

    result = strategic_memory(action="record", content="Some insight.")

    assert mock_client.create_event.call_count == 1
    assert "recorded" in result.lower()


def test_record_empty_content_returns_error():
    """RECORD with empty content returns an ERROR message, no API call."""
    strategic_memory, mock_client = _make_tool()

    result = strategic_memory(action="RECORD", content="")

    mock_client.create_event.assert_not_called()
    assert "ERROR" in result


def test_retrieve_action_calls_retrieve_memories():
    """RETRIEVE action calls memory_client.retrieve_memories with correct args."""
    strategic_memory, mock_client = _make_tool()
    mock_client.retrieve_memories.return_value = [
        {"content": "Plant potatoes early"},
        {"content": "Battery pre-charge before dust storm"},
    ]

    result = strategic_memory(action="RETRIEVE", query="dust storm strategy")

    mock_client.retrieve_memories.assert_called_once_with(
        memory_id="test-memory-id",
        namespace="/",
        query="dust storm strategy",
        actor_id="mars-agent",
        top_k=5,
    )
    assert "Past Strategic Learnings" in result
    assert "Plant potatoes" in result
    assert "Battery" in result


def test_retrieve_empty_results_returns_message():
    """RETRIEVE with no results returns a helpful no-results message."""
    strategic_memory, mock_client = _make_tool()
    mock_client.retrieve_memories.return_value = []

    result = strategic_memory(action="RETRIEVE", query="anything")

    assert "No past learnings" in result


def test_retrieve_empty_query_returns_error():
    """RETRIEVE with empty query returns ERROR, no API call."""
    strategic_memory, mock_client = _make_tool()

    result = strategic_memory(action="RETRIEVE", query="")

    mock_client.retrieve_memories.assert_not_called()
    assert "ERROR" in result


def test_invalid_action_returns_error():
    """Unknown action returns ERROR message without making any API calls."""
    strategic_memory, mock_client = _make_tool()

    result = strategic_memory(action="DELETE", content="something")

    mock_client.create_event.assert_not_called()
    mock_client.retrieve_memories.assert_not_called()
    assert "ERROR" in result
    assert "DELETE" in result


def test_record_api_failure_returns_error_string():
    """RECORD returns an ERROR string if create_event raises an exception."""
    strategic_memory, mock_client = _make_tool()
    mock_client.create_event.side_effect = RuntimeError("AWS error")

    result = strategic_memory(action="RECORD", content="Some insight.")

    assert "ERROR" in result


def test_retrieve_api_failure_returns_error_string():
    """RETRIEVE returns an ERROR string if retrieve_memories raises an exception."""
    strategic_memory, mock_client = _make_tool()
    mock_client.retrieve_memories.side_effect = RuntimeError("Network timeout")

    result = strategic_memory(action="RETRIEVE", query="any query")

    assert "ERROR" in result
