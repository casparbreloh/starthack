"""Unit tests for src/memory.py — AgentCore Memory factory functions.

All AWS/boto3 calls are mocked so tests run without AWS credentials.
"""

from __future__ import annotations

from unittest.mock import MagicMock, patch


def test_create_session_manager_uses_correct_config():
    """create_session_manager() builds AgentCoreMemoryConfig with correct fields."""
    mock_config_cls = MagicMock()
    mock_sm_cls = MagicMock()
    mock_config_instance = MagicMock()
    mock_config_cls.return_value = mock_config_instance

    with (
        patch("src.memory.AgentCoreMemoryConfig", mock_config_cls),
        patch("src.memory.AgentCoreMemorySessionManager", mock_sm_cls),
        patch("src.memory.MEMORY_ID", "test-memory-id"),
        patch("src.memory.ACTOR_ID", "mars-agent"),
        patch("src.memory.MEMORY_BATCH_SIZE", 15),
        patch("src.memory.MEMORY_REGION", "us-west-2"),
    ):
        from src.memory import create_session_manager

        create_session_manager(session_id="run_20260319_120000")

        mock_config_cls.assert_called_once_with(
            memory_id="test-memory-id",
            session_id="run_20260319_120000",
            actor_id="mars-agent",
            batch_size=15,
        )
        mock_sm_cls.assert_called_once_with(
            agentcore_memory_config=mock_config_instance,
            region_name="us-west-2",
        )


def test_create_memory_client_uses_region():
    """create_memory_client() passes region to MemoryClient constructor."""
    mock_client_cls = MagicMock()

    with patch("src.memory.MemoryClient", mock_client_cls):
        from src.memory import create_memory_client

        create_memory_client(region="eu-west-1")

        mock_client_cls.assert_called_once_with(region_name="eu-west-1")


def test_create_memory_client_default_region():
    """create_memory_client() uses MEMORY_REGION by default."""
    mock_client_cls = MagicMock()

    with (
        patch("src.memory.MemoryClient", mock_client_cls),
        patch("src.memory.MEMORY_REGION", "us-west-2"),
    ):
        from src.memory import create_memory_client

        create_memory_client()

        mock_client_cls.assert_called_once_with(region_name="us-west-2")


def test_retrieve_past_learnings_extracts_text():
    """retrieve_past_learnings() returns list of text strings from results."""
    mock_client = MagicMock()
    mock_client.retrieve_memories.return_value = [
        {"content": "Plant potatoes early to avoid food shortage"},
        {"text": "Water recycling critical in hard difficulty"},
        {"memory": "Crisis dust storm: pre-charge battery to 90%"},
    ]

    from src.memory import retrieve_past_learnings

    results = retrieve_past_learnings(
        memory_client=mock_client,
        memory_id="test-id",
        actor_id="mars-agent",
        query="mission strategy",
    )

    assert len(results) == 3
    assert "Plant potatoes" in results[0]
    assert "Water recycling" in results[1]
    assert "dust storm" in results[2]

    mock_client.retrieve_memories.assert_called_once_with(
        memory_id="test-id",
        namespace="/",
        query="mission strategy",
        actor_id="mars-agent",
        top_k=5,
    )


def test_retrieve_past_learnings_returns_empty_on_failure():
    """retrieve_past_learnings() returns [] when the API call raises an exception."""
    mock_client = MagicMock()
    mock_client.retrieve_memories.side_effect = RuntimeError("AWS connection failed")

    from src.memory import retrieve_past_learnings

    results = retrieve_past_learnings(
        memory_client=mock_client,
        memory_id="test-id",
        actor_id="mars-agent",
        query="anything",
    )

    assert results == []


def test_retrieve_past_learnings_handles_string_results():
    """retrieve_past_learnings() handles raw string results (not dicts)."""
    mock_client = MagicMock()
    mock_client.retrieve_memories.return_value = [
        "Direct string learning",
        "Another string",
    ]

    from src.memory import retrieve_past_learnings

    results = retrieve_past_learnings(
        memory_client=mock_client,
        memory_id="test-id",
        actor_id="mars-agent",
        query="any query",
    )

    assert results == ["Direct string learning", "Another string"]
