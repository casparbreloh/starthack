# agent/

## Purpose

AI agent system for managing the Mars greenhouse. Orchestrator LLM reasons about decisions each sol; 6 specialist sub-agents handle crisis escalation. Deployed on AWS Bedrock AgentCore. Connects to simulation via WebSocket consultation protocol.

## Tech

- Python 3.13+, Strands Agents framework, Bedrock model
- AWS Bedrock AgentCore runtime + AgentCore Memory
- WebSocket client (websockets lib) for simulation communication
- httpx for ML sidecar communication
- MCP client for Syngenta crop knowledge base

## Key Files

- `src/main.py` — Entry point with `@app.entrypoint` handler, streaming SSE events
- `src/ws_client.py` — WebSocket client for simulation consultation protocol (register → create session → receive consultations → send actions)
- `src/config.py` — Environment variables and constants (SIM_WS_URL, MODEL_ID, ML_SERVICE_URL, MEMORY_ID)
- `src/prompts.py` — System prompts for orchestrator and all specialists
- `src/weather_integration.py` — LSTM forecast client (calls ML sidecar via HTTP)
- `src/energy_projection.py` — Solar energy budget calculations
- `src/journal.py` — Decision journaling and cross-session learning
- `src/memory.py` — AgentCore Memory integration (session manager + memory client)
- `src/crisis_tracker.py` — Crisis outcome tracker with 5/15/50-sol observation windows
- `src/mcp_client.py` — MCP client for Syngenta knowledge base tools
- `src/runner.py` — CLI entry point for local runs (WebSocket mode)

## Structure

- `src/agents/` — Orchestrator + 6 specialist agents + triage coordinator
- `src/tools/` — Factory-created tool functions (actions, telemetry, memory)
- `tests/` — Unit tests

## Commands

```bash
uv sync                                          # Install dependencies
uv run uvicorn src.main:app --reload --port 9090  # Start agent server
uv run mars-agent                                 # Run standalone mission (WebSocket)
uv run pytest tests/ -q                           # Run tests
```

## Conventions

- Factory pattern for tools: `create_action_tools()` / `create_telemetry_tools()` / `create_memory_tools()` return dicts of `@tool` functions
- WebSocket consultation protocol: simulation pauses on interrupts, agent receives snapshot, sends actions + next_checkin sol
- Weather forecasting delegates to ML sidecar service (port 8090), not local torch
- AgentCore Memory used for cross-session strategic learnings
