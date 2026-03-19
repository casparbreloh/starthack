# agent/

## Purpose

AI agent skeleton for managing the Mars greenhouse, deployed on AWS Bedrock AgentCore. No simulation API integration yet.

## Tech

- Python 3.13+, Strands Agents framework, Claude Sonnet 4.5
- AWS Bedrock AgentCore runtime

## Key Files

- `src/main.py` — Single entry point with `@app.entrypoint` handler, Strands Agent, BedrockModel

## Commands

```bash
uv sync                                          # Install dependencies
uv run uvicorn src.main:app --reload --port 9090  # Start agent server
```

## Conventions

- No tools defined yet (skeleton)
- Uses bedrock-agentcore runtime pattern
