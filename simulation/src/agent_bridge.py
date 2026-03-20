"""
Bridge for invoking the Oasis agent.

Supports two invocation modes:
  1. **AgentCore Runtime** (``AGENT_RUNTIME_ARN`` env var) — uses boto3 to call
     ``bedrock-agent-runtime:invoke_agent_runtime``.  This is the production
     path when deployed via CDK.
  2. **Direct HTTP** (``AGENT_URL`` env var) — POSTs to ``/invocations`` on the
     agent's HTTP endpoint.  Used for local development with ``make dev-agent``.

Failures are non-fatal — the simulation continues without an agent.

In Fargate mode the container discovers its own IP so it can tell the agent
where to connect back.  When ``AGENT_RUNTIME_ARN`` is set (agent on AgentCore,
outside the VPC) the public IP is resolved via ``checkip.amazonaws.com``;
otherwise the private IP from ECS task metadata is used.
"""

from __future__ import annotations

import asyncio
import json
import logging
import os

import httpx

logger = logging.getLogger(__name__)

# Cached after first successful lookup so we don't hit the metadata
# endpoint on every session creation.
_cached_ws_url: str | None = None


async def _resolve_public_ip() -> str | None:
    """Discover this container's public IPv4 via an external service.

    Uses ``checkip.amazonaws.com`` which is fast and reliable from within AWS.
    Retries a few times since DNS may not be ready immediately at container
    startup.  Returns ``None`` on persistent failure.
    """
    for attempt in range(3):
        try:
            async with httpx.AsyncClient(timeout=httpx.Timeout(5.0)) as client:
                resp = await client.get("https://checkip.amazonaws.com")
                resp.raise_for_status()
                return resp.text.strip()
        except BaseException:
            # Must catch BaseException — asyncio.CancelledError is not an
            # Exception in Python 3.9+ and will crash the lifespan if it escapes.
            if attempt < 2:
                await asyncio.sleep(2)
            else:
                logger.warning(
                    "Failed to resolve public IP after 3 attempts", exc_info=True
                )
    return None


async def _resolve_fargate_ip() -> str | None:
    """Resolve this Fargate task's reachable IP address.

    When ``AGENT_RUNTIME_ARN`` is set the agent runs outside the VPC (on
    AgentCore), so it needs the *public* IP.  Otherwise, fall back to the
    private IP from ECS task metadata (works for in-VPC callers).

    Returns ``None`` when running outside Fargate (e.g. local dev).
    """
    # When the agent is on AgentCore it connects from outside the VPC,
    # so we need the public IP assigned to the Fargate task's ENI.
    if os.environ.get("AGENT_RUNTIME_ARN"):
        public_ip = await _resolve_public_ip()
        if public_ip:
            return public_ip

    # Fall back to private IP from ECS task metadata
    metadata_uri = os.environ.get("ECS_CONTAINER_METADATA_URI_V4")
    if not metadata_uri:
        return None

    try:
        async with httpx.AsyncClient(timeout=httpx.Timeout(5.0)) as client:
            resp = await client.get(f"{metadata_uri}/task")
            resp.raise_for_status()
            task_meta = resp.json()

            for container in task_meta.get("Containers", []):
                for network in container.get("Networks", []):
                    addrs = network.get("IPv4Addresses", [])
                    if addrs:
                        return addrs[0]
    except BaseException:
        logger.warning("Failed to fetch ECS task metadata", exc_info=True)

    return None


async def get_own_ws_url() -> str:
    """Return this simulation container's WebSocket URL.

    Resolution order:
      1. ``SIM_WS_URL`` environment variable (always wins — allows explicit override)
      2. Public IP via ``checkip.amazonaws.com`` (when ``AGENT_RUNTIME_ARN`` is set)
      3. Private IP from ECS task metadata (Fargate, in-VPC callers)
      4. Fallback ``ws://localhost:8080/ws`` (local development)
    """
    global _cached_ws_url  # noqa: PLW0603

    if _cached_ws_url is not None:
        return _cached_ws_url

    explicit = os.environ.get("SIM_WS_URL")
    if explicit:
        _cached_ws_url = explicit
        return _cached_ws_url

    ip = await _resolve_fargate_ip()
    if ip:
        port = os.environ.get("PORT", "8080")
        _cached_ws_url = f"ws://{ip}:{port}/ws"
        logger.info("Resolved own WS URL from ECS metadata: %s", _cached_ws_url)
        return _cached_ws_url

    _cached_ws_url = "ws://localhost:8080/ws"
    return _cached_ws_url


# ---------------------------------------------------------------------------
# Invocation — AgentCore Runtime (production)
# ---------------------------------------------------------------------------


async def _invoke_via_agentcore(runtime_arn: str, session_id: str, ws_url: str) -> None:
    """Invoke the agent via Bedrock AgentCore Runtime SDK.

    Uses the ``bedrock-agentcore`` client (boto3 >= 1.39.8).
    """
    import boto3

    payload = json.dumps(
        {
            "action": "join_mission",
            "config": {
                "session_id": session_id,
                "ws_url": ws_url,
            },
        }
    )

    logger.info(
        "Invoking agent via AgentCore Runtime %s for session %s (ws_url=%s)",
        runtime_arn,
        session_id,
        ws_url,
    )

    def _call() -> None:
        client = boto3.client("bedrock-agentcore")
        response = client.invoke_agent_runtime(
            agentRuntimeArn=runtime_arn,
            runtimeSessionId=session_id,
            payload=payload.encode(),
        )
        # Process the streaming response
        content_type = response.get("contentType", "")
        if "text/event-stream" in content_type:
            for line in response["response"].iter_lines(chunk_size=10):
                if line:
                    decoded = line.decode("utf-8") if isinstance(line, bytes) else line
                    logger.info("Agent event: %s", decoded)
        elif response.get("response"):
            for chunk in response["response"]:
                decoded = chunk.decode("utf-8") if isinstance(chunk, bytes) else chunk
                logger.info("Agent event: %s", decoded)

    # boto3 is synchronous — run in a thread to avoid blocking the event loop
    loop = asyncio.get_running_loop()
    await loop.run_in_executor(None, _call)


# ---------------------------------------------------------------------------
# Invocation — Direct HTTP (local dev)
# ---------------------------------------------------------------------------


async def _invoke_via_http(agent_url: str, session_id: str, ws_url: str) -> None:
    """POST to the agent's /invocations endpoint to start a join_mission."""
    payload = {
        "action": "join_mission",
        "config": {
            "session_id": session_id,
            "ws_url": ws_url,
        },
    }

    logger.info(
        "Invoking agent at %s for session %s (ws_url=%s)",
        agent_url,
        session_id,
        ws_url,
    )

    async with httpx.AsyncClient(
        timeout=httpx.Timeout(connect=5.0, read=300.0, write=5.0, pool=5.0)
    ) as client:
        async with client.stream(
            "POST", f"{agent_url}/invocations", json=payload
        ) as resp:
            resp.raise_for_status()
            async for line in resp.aiter_lines():
                if not line.strip():
                    continue
                logger.info("Agent event: %s", line.rstrip())


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------


async def invoke_agent(session_id: str, ws_url: str) -> None:
    """Invoke the agent using the best available method.

    Checks ``AGENT_RUNTIME_ARN`` first (AgentCore), then falls back to
    ``AGENT_URL`` (direct HTTP).  If neither is set, logs a warning.
    """
    runtime_arn = os.environ.get("AGENT_RUNTIME_ARN", "")
    agent_url = os.environ.get("AGENT_URL", "")

    try:
        if runtime_arn:
            await _invoke_via_agentcore(runtime_arn, session_id, ws_url)
        elif agent_url:
            await _invoke_via_http(agent_url, session_id, ws_url)
        else:
            logger.warning(
                "Neither AGENT_RUNTIME_ARN nor AGENT_URL set — "
                "session %s will run without an agent",
                session_id,
            )
    except httpx.ConnectError:
        logger.warning("Could not reach agent — simulation continues without agent")
    except Exception:
        logger.exception("Agent invocation failed for session %s", session_id)
