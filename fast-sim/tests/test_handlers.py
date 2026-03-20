"""
Tests for Lambda handlers with mocked AWS services (moto).

Tests:
  - worker_handler: processes SQS record, writes to S3, increments DynamoDB counter
  - dispatcher_handler: creates DynamoDB #META, sends SQS messages
"""

from __future__ import annotations

import json
import os
from unittest.mock import MagicMock, patch

import boto3
import pytest


@pytest.fixture(autouse=True)
def aws_env(monkeypatch: pytest.MonkeyPatch) -> None:
    """Set required environment variables for handlers."""
    monkeypatch.setenv("RESULTS_BUCKET", "test-results")
    monkeypatch.setenv("WAVES_TABLE", "test-waves")
    monkeypatch.setenv("WORK_QUEUE_URL", "https://sqs.us-east-1.amazonaws.com/123456789/test-queue")
    monkeypatch.setenv("AWS_DEFAULT_REGION", "us-east-1")
    monkeypatch.setenv("AWS_ACCESS_KEY_ID", "testing")
    monkeypatch.setenv("AWS_SECRET_ACCESS_KEY", "testing")
    monkeypatch.setenv("AWS_SECURITY_TOKEN", "testing")
    monkeypatch.setenv("AWS_SESSION_TOKEN", "testing")
    # Note: Do NOT set AWS_LAMBDA_FUNCTION_NAME in tests -- that would prevent
    # engine_bridge.py from injecting sys.path for the simulation engine.
    # In actual Lambda, PYTHONPATH handles it; in tests, sys.path injection does.
    monkeypatch.delenv("AWS_LAMBDA_FUNCTION_NAME", raising=False)


def test_worker_handler_processes_sqs_record() -> None:
    """Worker handler should run simulation and write to S3/DynamoDB."""
    import moto  # noqa: PLC0415

    with moto.mock_aws():
        # Set up S3 bucket
        s3 = boto3.client("s3", region_name="us-east-1")
        s3.create_bucket(Bucket="test-results")

        # Set up DynamoDB table
        dynamodb = boto3.resource("dynamodb", region_name="us-east-1")
        table = dynamodb.create_table(
            TableName="test-waves",
            KeySchema=[
                {"AttributeName": "wave_id", "KeyType": "HASH"},
                {"AttributeName": "run_id", "KeyType": "RANGE"},
            ],
            AttributeDefinitions=[
                {"AttributeName": "wave_id", "AttributeType": "S"},
                {"AttributeName": "run_id", "AttributeType": "S"},
            ],
            BillingMode="PAY_PER_REQUEST",
        )

        # Create #META item
        table.put_item(Item={
            "wave_id": "test-wave",
            "run_id": "#META",
            "total_runs": 1,
            "completed_runs": 0,
            "status": "running",
            "best_score": 0,
        })

        # Build SQS event
        from src.config import DEFAULT_STRATEGY, RunConfig  # noqa: PLC0415

        config = RunConfig(
            strategy=DEFAULT_STRATEGY,
            seed=42,
            difficulty="normal",
            run_id="test-run-001",
            wave_id="test-wave",
        )
        sqs_event = {
            "Records": [{"body": config.to_json()}]
        }

        # Call handler
        from src.handlers import worker_handler  # noqa: PLC0415

        result = worker_handler(sqs_event, None)
        assert result["success"] == 1
        assert result["errors"] == 0

        # Verify S3 put
        response = s3.get_object(Bucket="test-results", Key="results/test-wave/test-run-001.json")
        body = json.loads(response["Body"].read())
        assert body["run_id"] == "test-run-001"
        assert body["wave_id"] == "test-wave"

        # Verify DynamoDB counter incremented
        meta = table.get_item(Key={"wave_id": "test-wave", "run_id": "#META"})["Item"]
        assert int(meta["completed_runs"]) == 1


def test_dispatcher_handler_creates_meta_and_sends_sqs() -> None:
    """Dispatcher should create #META item and send messages to SQS."""
    import moto  # noqa: PLC0415

    with moto.mock_aws():
        # Set up SQS
        sqs = boto3.client("sqs", region_name="us-east-1")
        queue = sqs.create_queue(QueueName="test-queue")
        queue_url = queue["QueueUrl"]

        # Update env var
        os.environ["WORK_QUEUE_URL"] = queue_url

        # Set up DynamoDB
        dynamodb = boto3.resource("dynamodb", region_name="us-east-1")
        dynamodb.create_table(
            TableName="test-waves",
            KeySchema=[
                {"AttributeName": "wave_id", "KeyType": "HASH"},
                {"AttributeName": "run_id", "KeyType": "RANGE"},
            ],
            AttributeDefinitions=[
                {"AttributeName": "wave_id", "AttributeType": "S"},
                {"AttributeName": "run_id", "AttributeType": "S"},
            ],
            BillingMode="PAY_PER_REQUEST",
        )

        event = {
            "wave_id": "test-wave-dispatch",
            "n_runs": 5,
            "mode": "random",
        }

        from src.handlers import dispatcher_handler  # noqa: PLC0415

        result = dispatcher_handler(event, None)
        assert result["wave_id"] == "test-wave-dispatch"
        assert result["dispatched"] == 5

        # Verify #META in DynamoDB
        table = dynamodb.Table("test-waves")
        meta = table.get_item(
            Key={"wave_id": "test-wave-dispatch", "run_id": "#META"}
        )["Item"]
        assert int(meta["total_runs"]) == 5
        assert meta["status"] == "running"
