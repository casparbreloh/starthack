"""Strategic memory tool for cross-session learning via AgentCore Memory.

Provides the `strategic_memory` @tool that lets the orchestrator LLM
explicitly RECORD high-value insights and RETRIEVE past experiences
by semantic similarity search.
"""

from __future__ import annotations

import logging
from datetime import UTC, datetime

from bedrock_agentcore.memory.client import MemoryClient
from strands import tool

logger = logging.getLogger(__name__)


def create_memory_tools(
    memory_client: MemoryClient,
    memory_id: str,
    actor_id: str,
    session_id: str,
) -> dict:
    """Create the strategic_memory tool bound to this session's memory context.

    Follows the same factory pattern as create_action_tools() and
    create_telemetry_tools() — returns a dict of @tool-decorated functions.

    Args:
        memory_client: MemoryClient instance for API calls.
        memory_id: AgentCore memory resource ID.
        actor_id: Actor scoping (e.g. "mars-agent").
        session_id: Current run/session ID for RECORD calls.

    Returns:
        Dict with key "strategic_memory" mapping to the @tool function.
    """

    @tool
    def strategic_memory(action: str, content: str = "", query: str = "") -> str:
        """Store strategic learnings that persist across missions (RECORD) or retrieve
        relevant past experiences by semantic similarity (RETRIEVE).

        Only RECORD high-value insights — e.g. effective crop strategies,
        crisis response outcomes, score correlation patterns, end-of-mission
        takeaways. Do NOT record routine per-sol observations.

        Actions:
          RECORD: Store a strategic insight for future missions.
                  Provide `content` with the insight text.
                  Example: "Planting potatoes in zone C before sol 50 consistently
                  prevents late-mission food crises on normal difficulty."

          RETRIEVE: Search for past experiences relevant to a topic.
                    Provide `query` describing what you're looking for.
                    Example: "dust storm energy management strategy"

        Args:
            action: "RECORD" or "RETRIEVE"
            content: The insight text to store (RECORD only).
            query: Natural language search query (RETRIEVE only).

        Returns:
            Confirmation message (RECORD) or formatted past learnings (RETRIEVE).
        """
        action_upper = action.strip().upper()

        if action_upper == "RECORD":
            if not content:
                return "ERROR: RECORD requires non-empty `content`."
            try:
                timestamp = datetime.now(UTC).isoformat()
                tagged_content = f"[STRATEGIC LEARNING — {timestamp}]\n{content}"
                memory_client.create_event(
                    memory_id=memory_id,
                    actor_id=actor_id,
                    session_id=session_id,
                    messages=[("user", tagged_content)],
                )
                logger.info("Strategic memory recorded: %.100s...", content)
                return f"Strategic learning recorded: {content[:200]}"
            except Exception as exc:
                logger.warning("strategic_memory RECORD failed: %s", exc)
                return f"ERROR recording strategic memory: {exc}"

        elif action_upper == "RETRIEVE":
            if not query:
                return "ERROR: RETRIEVE requires non-empty `query`."
            try:
                results = memory_client.retrieve_memories(
                    memory_id=memory_id,
                    namespace="/",
                    query=query,
                    actor_id=actor_id,
                    top_k=5,
                )
                if not results:
                    return "No past learnings found for this query."

                lines = ["## Past Strategic Learnings\n"]
                for i, item in enumerate(results, 1):
                    if isinstance(item, dict):
                        text = (
                            item.get("content")
                            or item.get("text")
                            or item.get("memory", "")
                            or str(item)
                        )
                    else:
                        text = str(item)
                    lines.append(f"{i}. {text}")

                return "\n".join(lines)
            except Exception as exc:
                logger.warning("strategic_memory RETRIEVE failed: %s", exc)
                return f"ERROR retrieving strategic memories: {exc}"

        else:
            return f"ERROR: Unknown action '{action}'. Use RECORD or RETRIEVE."

    return {"strategic_memory": strategic_memory}
