"""AgentCore Memory integration for the Mars greenhouse agent.

Provides factory functions for:
  - AgentCoreMemorySessionManager: per-session context window management
  - MemoryClient: explicit create_event / retrieve_memories API calls
  - retrieve_past_learnings: helper to query cross-session strategic learnings
"""

from __future__ import annotations

import logging

from bedrock_agentcore.memory.client import MemoryClient
from bedrock_agentcore.memory.integrations.strands.config import AgentCoreMemoryConfig
from bedrock_agentcore.memory.integrations.strands.session_manager import (
    AgentCoreMemorySessionManager,
)

from .config import ACTOR_ID, MEMORY_BATCH_SIZE, MEMORY_ID, MEMORY_REGION

logger = logging.getLogger(__name__)


def create_session_manager(session_id: str) -> AgentCoreMemorySessionManager:
    """Create an AgentCoreMemorySessionManager for the given session.

    The session manager handles conversation summarization and context
    truncation for a long-running (450-sol) mission.

    Args:
        session_id: Unique identifier for this run (e.g. run_id timestamp).

    Returns:
        Configured AgentCoreMemorySessionManager instance.
    """
    config = AgentCoreMemoryConfig(
        memory_id=MEMORY_ID,
        session_id=session_id,
        actor_id=ACTOR_ID,
        batch_size=MEMORY_BATCH_SIZE,
    )
    return AgentCoreMemorySessionManager(
        agentcore_memory_config=config,
        region_name=MEMORY_REGION,
    )


def create_memory_client(region: str = MEMORY_REGION) -> MemoryClient:
    """Create a MemoryClient for explicit RECORD/RETRIEVE API calls.

    Args:
        region: AWS region name (default: MEMORY_REGION from config).

    Returns:
        Configured MemoryClient instance.
    """
    return MemoryClient(region_name=region)


def retrieve_past_learnings(
    memory_client: MemoryClient,
    memory_id: str,
    actor_id: str,
    query: str,
    top_k: int = 5,
) -> list[str]:
    """Retrieve relevant past strategic learnings via semantic search.

    Uses namespace "/" as a broad catch-all since the memory is STM_ONLY
    (no LTM strategies to extract facts into namespaces).

    Args:
        memory_client: MemoryClient instance.
        memory_id: The AgentCore memory resource ID.
        actor_id: Actor ID to scope retrieval (e.g. "mars-agent").
        query: Natural language query for semantic search.
        top_k: Maximum number of results to return.

    Returns:
        List of text strings from retrieved memory records.
        Empty list if retrieval fails or no results found.
    """
    try:
        results = memory_client.retrieve_memories(
            memory_id=memory_id,
            namespace="/",
            query=query,
            actor_id=actor_id,
            top_k=top_k,
        )
        texts: list[str] = []
        for item in results:
            # Results may be dicts with 'content', 'text', or similar keys
            if isinstance(item, dict):
                text = (
                    item.get("content")
                    or item.get("text")
                    or item.get("memory", "")
                    or str(item)
                )
                if text:
                    texts.append(str(text))
            elif isinstance(item, str):
                texts.append(item)
        return texts
    except Exception as exc:
        logger.warning("retrieve_past_learnings failed: %s", exc)
        return []
