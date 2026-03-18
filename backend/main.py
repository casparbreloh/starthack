"""
Mars Greenhouse Agent System — Backend Entry Point

FastAPI server that orchestrates AI agents for autonomous Martian greenhouse management.
Agents communicate with the AWS AgentCore gateway for domain knowledge and coordinate
to optimize crop planning, environment control, and resource allocation.
"""

from fastapi import FastAPI

app = FastAPI(title="Mars Greenhouse Agent System")


@app.get("/health")
async def health():
    return {"status": "ok"}
