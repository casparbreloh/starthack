#!/usr/bin/env python3
import aws_cdk as cdk

from stacks.oasis_stack import OasisStack

app = cdk.App()

OasisStack(
    app,
    "OasisStack",
    env=cdk.Environment(account="961812672853", region="us-west-2"),
)

app.synth()
