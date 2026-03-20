# Deployment

AWS account `961812672853`, region `us-west-2`.

## Local Dev (Docker Compose)

Runs simulation + ML + agent locally. The agent needs AWS credentials for Bedrock LLM access.

```bash
docker compose up --build
```

- Simulation: `http://localhost:8080`
- ML service: `http://localhost:8090`
- WebSocket: `ws://localhost:8080/ws`
- Agent connects to simulation automatically via internal Docker networking

AWS credentials are passed through from your shell environment (`AWS_ACCESS_KEY_ID`, `AWS_SECRET_ACCESS_KEY`, `AWS_SESSION_TOKEN`).

## Local Fargate Testing

Run the simulation in Fargate-parity mode (auto-start session, max tick speed, no S3 upload) without AWS:

```bash
docker compose -f docker-compose.yml -f docker-compose.fargate.yml up
```

This sets `FARGATE_MODE=1` and `TICK_DELAY_MS=0` on the simulation container.

## Fargate / AgentCore

### Prerequisites

- AWS CDK CLI (`npm install -g aws-cdk`)
- AWS credentials configured for account 961812672853, region us-west-2
- CDK bootstrapped: `cdk bootstrap aws://961812672853/us-west-2`
- GitHub personal access token with `repo` scope (for Amplify)

### Deploy

1. Build and push simulation image to ECR:
   ```bash
   aws ecr get-login-password --region us-west-2 | docker login --username AWS --password-stdin 961812672853.dkr.ecr.us-west-2.amazonaws.com
   docker build -t oasis-simulation simulation/
   docker tag oasis-simulation:latest 961812672853.dkr.ecr.us-west-2.amazonaws.com/oasis-simulation:latest
   docker push 961812672853.dkr.ecr.us-west-2.amazonaws.com/oasis-simulation:latest
   ```
2. Build and push ML image:
   ```bash
   docker build -t oasis-ml ml/
   docker tag oasis-ml:latest 961812672853.dkr.ecr.us-west-2.amazonaws.com/oasis-ml:latest
   docker push 961812672853.dkr.ecr.us-west-2.amazonaws.com/oasis-ml:latest
   ```
3. Deploy infrastructure (pass GitHub token for Amplify):
   ```bash
   cd infra && uv run cdk deploy -c github_token=ghp_xxx --require-approval never
   ```
   Or use `make deploy` after setting the token in `cdk.json` context.
4. The CDK outputs include `AmplifyAppUrl` for the frontend and `ApiUrl` for the orchestrator.
   Amplify env vars (`VITE_ORCHESTRATOR_URL`) are wired automatically.

### Tear down

```bash
make destroy
```
