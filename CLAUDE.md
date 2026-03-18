# CLAUDE.md

Read @AGENTS.md for the agent architecture and system overview.

## Project

Mars Greenhouse Agent System — a hackathon project for the Syngenta START Hack challenge. Autonomous AI agents manage a Martian greenhouse simulation for a 450-day crew mission.

## Stack

- **Agent**: Python, deployed on AWS AgentCore
- **Simulation**: Python, FastAPI
- **Frontend**: React, TypeScript
- **AI**: AWS AgentCore gateway (Syngenta knowledge base)

## Commands

- **Simulation**: `cd simulation && uv run uvicorn main:app --reload`
- **Frontend**: `cd frontend && npm install && npm run dev`
