"""
AWS Lambda handler entrypoints for fast-sim.

Three handlers sharing the same container image:
  - worker_handler:     processes SQS messages, runs simulations, writes to S3
  - dispatcher_handler: generates configs, fans out to SQS, creates DynamoDB #META
  - aggregator_handler: scheduled every 5 min, aggregates completed waves
"""

from __future__ import annotations

import json
import logging
import os
import random
import time
from typing import Any

import boto3

logger = logging.getLogger(__name__)

# Environment variables (set by CDK)
RESULTS_BUCKET = os.environ.get("RESULTS_BUCKET", "fast-sim-results")
WAVES_TABLE = os.environ.get("WAVES_TABLE", "fast-sim-waves")
WORK_QUEUE_URL = os.environ.get("WORK_QUEUE_URL", "")

# Backoff constants for DynamoDB atomic counter updates
_MAX_RETRIES = 5
_BASE_DELAY_S = 0.1


def worker_handler(event: dict[str, Any], context: Any) -> dict[str, Any]:
    """
    Process SQS messages: each message is a JSON-encoded RunConfig.

    For each config:
      1. Run simulation
      2. Write RunResult JSON to S3
      3. Atomically increment DynamoDB #META completed_runs counter
    """
    from src.config import RunConfig  # noqa: PLC0415
    from src.runner import run_simulation  # noqa: PLC0415

    s3 = boto3.client("s3")
    dynamodb = boto3.resource("dynamodb")
    table = dynamodb.Table(WAVES_TABLE)  # type: ignore[attr-defined]

    success_count = 0
    error_count = 0

    for record in event.get("Records", []):
        try:
            config = RunConfig.from_json(record["body"])
            result = run_simulation(config)

            # Write result to S3
            key = f"results/{result.wave_id}/{result.run_id}.json"
            s3.put_object(
                Bucket=RESULTS_BUCKET,
                Key=key,
                Body=result.to_json().encode(),
                ContentType="application/json",
            )

            # Atomically increment completed_runs on #META item
            _atomic_increment_meta(table, result.wave_id, result.final_score)
            success_count += 1

        except Exception as exc:
            logger.error("Worker failed for record: %s", exc, exc_info=True)
            error_count += 1
            raise  # Let SQS retry via DLQ

    return {"success": success_count, "errors": error_count}


def dispatcher_handler(event: dict[str, Any], context: Any) -> dict[str, Any]:
    """
    Generate and fan out simulation configs to SQS.

    Event body:
      {wave_id, n_runs, mode: "random"|"evolve", base_wave_id?}
    """
    from src.sweep import evolve_configs, generate_random_configs  # noqa: PLC0415

    # Parse event (handles both direct invocation and API Gateway events)
    if isinstance(event.get("body"), str):
        payload = json.loads(event["body"])
    else:
        payload = event

    wave_id = payload["wave_id"]
    n_runs = int(payload.get("n_runs", 1000))
    mode = str(payload.get("mode", "random"))
    base_wave_id = payload.get("base_wave_id")

    # Generate configs
    if mode == "evolve" and base_wave_id:
        from src.aggregate import _load_top_results_from_dynamodb  # noqa: PLC0415

        top_k = _load_top_results_from_dynamodb(base_wave_id, k=50)
        configs = evolve_configs(top_k, n_runs, wave_id)
    else:
        configs = generate_random_configs(n_runs, wave_id)

    # Create #META item in DynamoDB
    dynamodb = boto3.resource("dynamodb")
    table = dynamodb.Table(WAVES_TABLE)  # type: ignore[attr-defined]
    table.put_item(
        Item={
            "wave_id": wave_id,
            "run_id": "#META",
            "total_runs": n_runs,
            "completed_runs": 0,
            "status": "running",
            "best_score": 0,
            "started_at": int(time.time()),
            "expires_at": int(time.time()) + 30 * 24 * 3600,  # 30 day TTL
        }
    )

    # Fan out to SQS in batches of 10
    sqs = boto3.client("sqs")
    sent = 0
    batch: list[dict[str, Any]] = []

    for config in configs:
        batch.append(
            {
                "Id": config.run_id,
                "MessageBody": config.to_json(),
            }
        )
        if len(batch) == 10:
            sqs.send_message_batch(QueueUrl=WORK_QUEUE_URL, Entries=batch)
            sent += len(batch)
            batch = []

    if batch:
        sqs.send_message_batch(QueueUrl=WORK_QUEUE_URL, Entries=batch)
        sent += len(batch)

    logger.info("Dispatched %d configs for wave %s", sent, wave_id)
    return {"wave_id": wave_id, "dispatched": sent}


def aggregator_handler(event: dict[str, Any], context: Any) -> dict[str, Any]:
    """
    Scheduled every 5 minutes. Checks for completed waves and aggregates results.

    For each completed wave:
      1. Stream-aggregate results from S3 (constant memory)
      2. Distill learnings from top-N/bottom-N
      3. Write to AgentCore Memory
      4. Update DynamoDB wave status to "complete"
    """
    from src.aggregate import stream_aggregate_results, write_learnings_to_memory  # noqa: PLC0415
    from src.distill import distill_wave_learnings, format_for_memory  # noqa: PLC0415

    dynamodb = boto3.resource("dynamodb")
    table = dynamodb.Table(WAVES_TABLE)  # type: ignore[attr-defined]
    memory_id = os.environ.get("MEMORY_ID", "fast-sim-learnings")
    actor_id = os.environ.get("ACTOR_ID", "mars-agent")

    # Find running waves with completed_runs >= total_runs
    # Scan #META items
    response = table.scan(
        FilterExpression="run_id = :meta AND #status = :running",
        ExpressionAttributeNames={"#status": "status"},
        ExpressionAttributeValues={":meta": "#META", ":running": "running"},
    )

    processed = 0
    for meta in response.get("Items", []):
        wave_id = meta["wave_id"]
        total = int(meta.get("total_runs", 0))
        completed = int(meta.get("completed_runs", 0))

        if completed < total and not event.get("wave_id") == wave_id:
            continue  # Not yet complete (unless manually triggered)

        # Stream aggregate results from S3
        stats = stream_aggregate_results(
            bucket=RESULTS_BUCKET,
            wave_id=wave_id,
        )

        # Distill learnings from top/bottom results
        learnings = distill_wave_learnings(stats.top_results, stats.bottom_results)
        formatted = format_for_memory(learnings, wave_id)

        # Write to AgentCore Memory
        write_learnings_to_memory(
            learnings=[formatted],
            wave_id=wave_id,
            memory_id=memory_id,
            actor_id=actor_id,
        )

        # Mark wave complete
        table.update_item(
            Key={"wave_id": wave_id, "run_id": "#META"},
            UpdateExpression="SET #status = :complete, completed_at = :ts",
            ExpressionAttributeNames={"#status": "status"},
            ExpressionAttributeValues={":complete": "complete", ":ts": int(time.time())},
        )

        logger.info("Wave %s aggregation complete: %d learnings", wave_id, len(learnings))
        processed += 1

    return {"processed_waves": processed}


# ------------------------------------------------------------------
# Helpers
# ------------------------------------------------------------------


def _atomic_increment_meta(
    table: Any,
    wave_id: str,
    score: int,
) -> None:
    """
    Atomically increment completed_runs on the #META item.

    Uses exponential backoff to handle hot-partition contention.
    """
    for attempt in range(_MAX_RETRIES):
        try:
            table.update_item(
                Key={"wave_id": wave_id, "run_id": "#META"},
                UpdateExpression=(
                    "ADD completed_runs :one SET best_score = if_not_exists(best_score, :score)"
                ),
                ExpressionAttributeValues={":one": 1, ":score": score},
            )
            return
        except table.meta.client.exceptions.ProvisionedThroughputExceededException:
            if attempt == _MAX_RETRIES - 1:
                raise
            sleep_s = _BASE_DELAY_S * (2**attempt) + random.uniform(0, 0.1)
            time.sleep(sleep_s)
        except Exception:
            raise
