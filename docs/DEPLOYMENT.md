# Deployment

AWS account `961812672853`, region `us-west-2`.

## Local Dev

Starts simulation, ML sidecar, frontend, and agent (waits for simulation health check before starting agent).

```bash
make dev
```

- Simulation: `http://localhost:8080`
- WebSocket: `ws://localhost:8080/ws`
- Frontend: `http://localhost:5173`
- ML sidecar: `http://localhost:8090`

AWS credentials are needed in your shell for the agent's Bedrock LLM access (`AWS_ACCESS_KEY_ID`, `AWS_SECRET_ACCESS_KEY`, `AWS_SESSION_TOKEN`).

## Fargate / AgentCore

> TODO
