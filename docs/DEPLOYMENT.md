# Deployment

AWS account `961812672853`, region `us-west-2`.

## Local Dev (Docker Compose)

Runs simulation + agent locally. The agent needs AWS credentials for Bedrock LLM access.

```bash
docker compose up --build
```

- Simulation: `http://localhost:8080`
- WebSocket: `ws://localhost:8080/ws`
- Agent connects to simulation automatically via internal Docker networking

AWS credentials are passed through from your shell environment (`AWS_ACCESS_KEY_ID`, `AWS_SECRET_ACCESS_KEY`, `AWS_SESSION_TOKEN`).

## Fargate / AgentCore

> TODO
