"""MCP Gateway client for the Syngenta Knowledge Base.

Sets up the Strands MCPClient to connect to the AWS AgentCore MCP Gateway,
which provides domain knowledge tools for Mars crop management.

Usage pattern:
    mcp_client = create_mcp_client()
    with mcp_client:
        kb_tools = discover_kb_tools(mcp_client)
        agent = Agent(tools=[*action_tools, *kb_tools])
        # Run entire mission loop INSIDE this context:
        for sol in range(450):
            run_sol(...)
    # Context exits here — MCP connection closed

Notes:
    - No authentication required for the hackathon gateway [R6-MCP2]
    - MCPClient tool objects are lightweight references bound to the MCP context.
      They are safe to share across multiple Agent instances created within
      the same `with mcp_client:` block. [R9-M3]
    - Tool names are dynamic (e.g., x_amz_bedrock_agentcore_search or similar).
      They are discovered at startup, not hardcoded.
"""

from __future__ import annotations

import logging

from mcp.client.streamable_http import streamablehttp_client
from strands.tools.mcp.mcp_client import MCPClient

from .config import AGENTCORE_GATEWAY_URL

logger = logging.getLogger(__name__)


def create_mcp_client() -> MCPClient:
    """Create a Strands MCPClient connected to the AgentCore MCP Gateway.

    No auth headers needed — the hackathon gateway is open. [R6-MCP2]

    Returns:
        MCPClient instance. Use as a context manager:
        `with create_mcp_client() as mcp_client: ...`
        OR store reference and use `with mcp_client:`.
    """
    return MCPClient(lambda: streamablehttp_client(AGENTCORE_GATEWAY_URL))


def discover_kb_tools(mcp_client: MCPClient) -> list:
    """Discover available KB tools from the MCP Gateway.

    Calls list_tools_sync() once — no pagination loop needed since Strands
    MCPClient returns all tools in a single call. [R8-H2]

    Args:
        mcp_client: An active MCPClient instance (must be used inside its
                    context manager block).

    Returns:
        List of Strands tool objects ready to pass to Agent(tools=[...]).
        Returns empty list if discovery fails (network error, gateway down).
        The agent can operate without KB tools — they are supplementary.
    """
    try:
        tools = mcp_client.list_tools_sync()
        tool_names = [getattr(t, "name", str(t)) for t in tools]
        logger.info(
            "Discovered %d KB tools from MCP Gateway: %s", len(tools), tool_names
        )
        return tools
    except Exception as exc:
        logger.warning(
            "Failed to discover KB tools from MCP Gateway at %s: %s. "
            "Orchestrator will run without Syngenta KB.",
            AGENTCORE_GATEWAY_URL,
            exc,
        )
        return []
