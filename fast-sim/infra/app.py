"""CDK application entry point for fast-sim."""

from __future__ import annotations

import aws_cdk as cdk

from infra.stack import FastSimStack

app = cdk.App()
FastSimStack(
    app,
    "FastSimStack",
    description="Fast-Sim: Lambda-based Mars Greenhouse policy sweep infrastructure",
)
app.synth()
