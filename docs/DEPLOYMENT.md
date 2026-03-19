# Deployment

AWS account `961812672853`, region `us-west-2`.

## Agent (AWS Bedrock AgentCore)

### Prerequisites

- AWS credentials configured in `~/.aws/credentials` (or env vars)
- `bedrock-agentcore-starter-toolkit` installed in the agent venv:
  ```
  cd agent && uv pip install bedrock-agentcore-starter-toolkit
  ```

### Deploy

```bash
cd agent
uv run agentcore deploy --auto-update-on-conflict
```

This builds an ARM64 container via CodeBuild, pushes to ECR, and deploys to AgentCore Runtime. Takes ~75s. No local Docker required.

### Test

```bash
uv run agentcore invoke '{"prompt": "What is your purpose?"}'
```

### Configuration

All config lives in `agent/.bedrock_agentcore.yaml` (auto-generated, do not hand-edit unless necessary).

Key runtime env vars (set via `agentcore deploy --env KEY=VALUE`):

| Variable | Default | Description |
|----------|---------|-------------|
| `SIM_BASE_URL` | `http://localhost:8080` | Simulation API URL (must be reachable from AgentCore) |
| `MODEL_ID` | `us.anthropic.claude-sonnet-4-6` | Bedrock inference profile ID |
| `AGENTCORE_GATEWAY_URL` | Syngenta KB gateway | MCP gateway for knowledge base |

### Resources created

- ECR repo: `bedrock-agentcore-mars_greenhouse_agent`
- IAM role: `AmazonBedrockAgentCoreSDKRuntime-us-west-2-*`
- CodeBuild project: `bedrock-agentcore-mars_greenhouse_agent-builder`
- S3 bucket: `bedrock-agentcore-codebuild-sources-961812672853-us-west-2`
- Agent ARN: `arn:aws:bedrock-agentcore:us-west-2:961812672853:runtime/mars_greenhouse_agent-JJDj794xYS`
- Memory: `mars_greenhouse_agent_mem-TMpX057Ro0` (STM, 30-day retention)

### Teardown

```bash
uv run agentcore destroy
```

### Logs

```bash
aws logs tail /aws/bedrock-agentcore/runtimes/mars_greenhouse_agent-JJDj794xYS-DEFAULT \
  --log-stream-name-prefix "$(date +%Y/%m/%d)/[runtime-logs]" --follow
```

---

## Simulation (FastAPI)

> TODO: Deploy to ECS/Lambda/EC2 and set `SIM_BASE_URL` on the agent.

---

## Frontend (React)

> TODO: Deploy to S3 + CloudFront or Amplify.

---

## ML Weather Service

> TODO: Upload trained models to S3, deploy Lambda for inference, expose via AgentCore MCP gateway.
