"""
S3 results upload module for Fargate mode.

Builds a results JSON from a completed session and optionally uploads it
to S3.  The `build_results_json` function is pure (no AWS dependency) so
it can be unit-tested without mocking.
"""

from __future__ import annotations

import json
import logging
from datetime import UTC, datetime
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from src.session import Session

logger = logging.getLogger(__name__)


def build_results_json(session: Session) -> dict[str, Any]:
    """Assemble a results dict from a completed session.

    Includes run metadata, final score breakdown, crisis stats, and timing.
    """
    engine = session.engine
    score_snap = engine.scoring.snapshot
    all_crises = engine.events.all_crises()

    return {
        "run_id": getattr(session, "run_id", None),
        "session_id": session.id,
        "seed": session.config.seed,
        "difficulty": session.config.difficulty,
        "final_sol": engine.current_sol,
        "mission_phase": engine.mission_phase.value,
        "final_score": score_snap.overall_score,
        "score_breakdown": {
            "survival": score_snap.survival,
            "nutrition": score_snap.nutrition,
            "resource_efficiency": score_snap.resource_efficiency,
            "crisis_management": score_snap.crisis_management,
        },
        "total_crises": len(all_crises),
        "events_summary": {
            "crises_resolved": sum(1 for c in all_crises if c.resolved),
            "crises_unresolved": sum(1 for c in all_crises if not c.resolved),
        },
        "started_at": session.created_at.isoformat(),
        "completed_at": datetime.now(UTC).isoformat(),
    }


async def upload_results(session: Session, bucket_name: str, run_id: str) -> None:
    """Build results JSON and upload to S3.

    Uploads to ``s3://{bucket_name}/results/{run_id}.json``.
    If *bucket_name* is empty or the upload fails, the error is logged but
    not re-raised (non-fatal).
    """
    if not bucket_name:
        logger.info("RESULTS_BUCKET not set — skipping S3 upload")
        return

    results = build_results_json(session)
    results["run_id"] = run_id  # ensure run_id from env is authoritative
    key = f"results/{run_id}.json"
    body = json.dumps(results, indent=2, default=str)

    try:
        import boto3

        s3 = boto3.client("s3")
        s3.put_object(
            Bucket=bucket_name,
            Key=key,
            Body=body.encode(),
            ContentType="application/json",
        )
        logger.info("Results uploaded to s3://%s/%s", bucket_name, key)
    except Exception:
        logger.exception("Failed to upload results to s3://%s/%s", bucket_name, key)
