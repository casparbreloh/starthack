# agent/src/tools/

## Purpose

Strands `@tool`-decorated functions that the LLM agent can call. Split into actions (write), telemetry (read), and memory (cross-session learning).

## Key Files

- `actions.py` — `create_action_tools()` factory returning 8 action tools (plant, harvest, irrigate, set_climate, allocate_energy, etc.)
- `telemetry.py` — `create_telemetry_tools()` factory returning read-only tools for parsing consultation snapshots
- `memory_tool.py` — `create_memory_tools()` factory for the `strategic_memory` tool (RECORD insights / RETRIEVE past experiences via AgentCore Memory)
- `__init__.py` — Re-exports all factory functions

## Conventions

- Tools are created via factory functions, not module-level singletons
- Each `@tool` function has a docstring that serves as the LLM tool description
- Action tools send commands via the WebSocket client (not direct HTTP)
