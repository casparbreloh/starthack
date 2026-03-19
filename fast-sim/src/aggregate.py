"""
Streaming S3 result aggregator.

Processes simulation results in batches of 1000 from S3 (constant memory usage),
maintains top-N/bottom-N heaps by score, and writes distilled learnings to
AgentCore Memory.
"""

from __future__ import annotations

import heapq
import json
import logging
import os
from dataclasses import dataclass, field
from typing import Any

logger = logging.getLogger(__name__)

MEMORY_ID = os.environ.get("MEMORY_ID", "fast-sim-learnings")
ACTOR_ID = os.environ.get("ACTOR_ID", "mars-agent")


@dataclass
class AggregateStats:
    """Aggregated statistics for a wave's simulation results."""

    count: int = 0
    score_sum: float = 0.0
    score_min: int = 100
    score_max: int = 0
    score_histogram: dict[str, int] = field(
        default_factory=lambda: {
            "0-10": 0,
            "11-20": 0,
            "21-30": 0,
            "31-40": 0,
            "41-50": 0,
            "51-60": 0,
            "61-70": 0,
            "71-80": 0,
            "81-90": 0,
            "91-100": 0,
        }
    )
    mission_complete_count: int = 0
    # Top-N and bottom-N stored as (score, result_dict) for heap operations
    _top_heap: list[tuple[int, dict[str, Any]]] = field(default_factory=list, repr=False)
    _bottom_heap: list[tuple[int, dict[str, Any]]] = field(default_factory=list, repr=False)
    top_n: int = 20
    bottom_n: int = 20

    @property
    def avg_score(self) -> float:
        return self.score_sum / self.count if self.count > 0 else 0.0

    @property
    def top_results(self) -> list[Any]:
        """Return top-N results as RunResult objects."""
        from src.results import RunResult  # noqa: PLC0415

        sorted_top = sorted(self._top_heap, key=lambda x: x[0], reverse=True)
        results = []
        for _, d in sorted_top:
            try:
                results.append(RunResult.from_dict(d))
            except Exception:
                pass
        return results

    @property
    def bottom_results(self) -> list[Any]:
        """Return bottom-N results as RunResult objects."""
        from src.results import RunResult  # noqa: PLC0415

        sorted_bottom = sorted(self._bottom_heap, key=lambda x: x[0])
        results = []
        for _, d in sorted_bottom:
            try:
                results.append(RunResult.from_dict(d))
            except Exception:
                pass
        return results

    def update(self, result_dict: dict[str, Any]) -> None:
        """Update running stats with a new result."""
        score = int(result_dict.get("final_score", 0))
        self.count += 1
        self.score_sum += score
        self.score_min = min(self.score_min, score)
        self.score_max = max(self.score_max, score)

        # Score histogram
        bucket = min(9, score // 10)
        bucket_key = f"{bucket * 10 + 1 if bucket > 0 else 0}-{(bucket + 1) * 10}"
        if bucket == 0:
            bucket_key = "0-10"
        if bucket_key in self.score_histogram:
            self.score_histogram[bucket_key] += 1

        if result_dict.get("mission_outcome") == "complete":
            self.mission_complete_count += 1

        # Top-N heap (min-heap on score, keep highest)
        if len(self._top_heap) < self.top_n:
            heapq.heappush(self._top_heap, (score, result_dict))
        elif score > self._top_heap[0][0]:
            heapq.heapreplace(self._top_heap, (score, result_dict))

        # Bottom-N heap (max-heap on negative score, keep lowest)
        neg_score = -score
        if len(self._bottom_heap) < self.bottom_n:
            heapq.heappush(self._bottom_heap, (neg_score, result_dict))
        elif neg_score > self._bottom_heap[0][0]:
            heapq.heapreplace(self._bottom_heap, (neg_score, result_dict))


def stream_aggregate_results(
    bucket: str,
    wave_id: str,
    batch_size: int = 1000,
    top_n: int = 20,
    bottom_n: int = 20,
) -> AggregateStats:
    """
    Stream-aggregate results from S3 in batches of batch_size.

    Memory usage is O(batch_size + top_n + bottom_n), not O(total_results).
    """
    import boto3  # noqa: PLC0415

    s3 = boto3.client("s3")
    stats = AggregateStats(top_n=top_n, bottom_n=bottom_n)

    prefix = f"results/{wave_id}/"
    paginator = s3.get_paginator("list_objects_v2")

    batch: list[dict[str, Any]] = []

    for page in paginator.paginate(Bucket=bucket, Prefix=prefix):
        for obj in page.get("Contents", []):
            key = obj["Key"]
            if not key.endswith(".json"):
                continue

            try:
                response = s3.get_object(Bucket=bucket, Key=key)
                result_dict = json.loads(response["Body"].read())
                batch.append(result_dict)
            except Exception as exc:
                logger.warning("Failed to read %s: %s", key, exc)
                continue

            if len(batch) >= batch_size:
                for r in batch:
                    stats.update(r)
                batch = []  # Discard processed batch (constant memory)

    # Process remaining batch
    for r in batch:
        stats.update(r)

    logger.info(
        "Aggregated %d results for wave %s (avg score: %.1f, top: %.1f, bottom: %.1f)",
        stats.count,
        wave_id,
        stats.avg_score,
        stats._top_heap[0][0] if stats._top_heap else 0,
        -stats._bottom_heap[0][0] if stats._bottom_heap else 0,
    )
    return stats


def write_learnings_to_memory(
    learnings: list[str],
    wave_id: str,
    memory_id: str = MEMORY_ID,
    actor_id: str = ACTOR_ID,
) -> None:
    """
    Write distilled learnings to AgentCore Memory.

    Uses the same memory_id and actor_id as the production agent
    so the agent can retrieve these learnings at decision time.
    """
    from bedrock_agentcore.memory.client import MemoryClient  # noqa: PLC0415

    client = MemoryClient()
    session_id = f"fast-sim-{wave_id}"

    for i, learning in enumerate(learnings):
        try:
            client.create_event(
                memory_id=memory_id,
                actor_id=actor_id,
                session_id=session_id,
                messages=[("user", learning)],
            )
            logger.info("Wrote learning %d/%d for wave %s", i + 1, len(learnings), wave_id)
        except Exception as exc:
            logger.error("Failed to write learning %d: %s", i + 1, exc)


def _load_top_results_from_dynamodb(
    wave_id: str,
    k: int = 50,
    table_name: str | None = None,
) -> list[Any]:
    """
    Load top-k RunResult objects from DynamoDB for evolution mode.

    Used by dispatcher_handler when mode="evolve".
    """
    import boto3  # noqa: PLC0415
    from boto3.dynamodb.conditions import Key  # noqa: PLC0415

    from src.results import RunResult  # noqa: PLC0415

    if table_name is None:
        table_name = os.environ.get("WAVES_TABLE", "fast-sim-waves")

    dynamodb = boto3.resource("dynamodb")
    table = dynamodb.Table(table_name)  # type: ignore[attr-defined]

    # Query all run items (sort key != #META) with a filter
    # Note: This is a simple scan for now; production would use a GSI on final_score
    response = table.query(
        KeyConditionExpression=Key("wave_id").eq(wave_id),
        FilterExpression="run_id <> :meta",
        ExpressionAttributeValues={":meta": "#META"},
    )

    items = response.get("Items", [])
    # Sort by score and take top-k
    items_sorted = sorted(
        items,
        key=lambda x: int(x.get("final_score", 0)),
        reverse=True,
    )[:k]

    results: list[RunResult] = []
    for item in items_sorted:
        try:
            result_json = item.get("result_json")
            if result_json:
                results.append(RunResult.from_json(result_json))
        except Exception:
            pass

    return results
