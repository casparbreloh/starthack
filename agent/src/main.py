import json
import logging
from typing import Any

from bedrock_agentcore.runtime import BedrockAgentCoreApp, RequestContext
from strands import Agent
from strands.models.bedrock import BedrockModel

logger = logging.getLogger(__name__)

SYSTEM_PROMPT = """\
You are the AI agent managing a Martian greenhouse for a 450-day crew mission.
You monitor crop health, environmental conditions, and resource usage.
Answer questions about greenhouse operations and provide recommendations.
"""

app = BedrockAgentCoreApp()


@app.entrypoint
async def agent_handler(payload: dict[str, Any], context: RequestContext):
    prompt = payload.get("prompt", "Give me a status report on the greenhouse.")

    model = BedrockModel(
        model_id="us.anthropic.claude-sonnet-4-5-20250929-v1:0",
        temperature=0.3,
    )

    agent = Agent(
        name="GreenhouseAgent",
        model=model,
        system_prompt=SYSTEM_PROMPT,
    )

    response = agent(prompt)

    yield {"data": json.dumps({"result": str(response.message)}, default=str)}


if __name__ == "__main__":
    app.run()
