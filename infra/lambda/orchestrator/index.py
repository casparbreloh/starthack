"""Lambda orchestrator for managing ECS Fargate simulation sessions.

Routes (API Gateway HTTP API):
    POST   /sessions             — start a new training session
    GET    /sessions             — list active sessions
    GET    /sessions/{id}        — get session detail
    DELETE /sessions/{id}        — stop a session
    GET    /sessions/{id}/results — get training results from S3
"""

from __future__ import annotations

import json
import logging
import os
import re
import uuid
from datetime import UTC, datetime

import boto3

logger = logging.getLogger()
logger.setLevel(logging.INFO)

ecs = boto3.client("ecs")
ec2 = boto3.client("ec2")
s3 = boto3.client("s3")

CLUSTER_NAME = os.environ["CLUSTER_NAME"]
TASK_DEFINITION_ARN = os.environ["TASK_DEFINITION_ARN"]
SUBNET_IDS = os.environ["SUBNET_IDS"].split(",")
SECURITY_GROUP_ID = os.environ["SECURITY_GROUP_ID"]
RESULTS_BUCKET = os.environ["RESULTS_BUCKET"]
AGENT_RUNTIME_ARN = os.environ.get("AGENT_RUNTIME_ARN", "")


def _json_response(status_code: int, body: dict | list) -> dict:
    return {
        "statusCode": status_code,
        "headers": {"Content-Type": "application/json"},
        "body": json.dumps(body, default=str),
    }


def _parse_body(event: dict) -> dict:
    raw = event.get("body", "{}")
    if not raw:
        return {}
    if event.get("isBase64Encoded"):
        import base64

        raw = base64.b64decode(raw).decode()
    return json.loads(raw)


def _resolve_public_ip(eni_id: str) -> str | None:
    """Resolve a public IPv4 address from an ENI ID via EC2 API."""
    try:
        resp = ec2.describe_network_interfaces(NetworkInterfaceIds=[eni_id])
        for ni in resp.get("NetworkInterfaces", []):
            assoc = ni.get("Association", {})
            public_ip = assoc.get("PublicIp")
            if public_ip:
                return public_ip
    except Exception:
        logger.warning("Failed to resolve public IP for ENI %s", eni_id, exc_info=True)
    return None


# ---------------------------------------------------------------------------
# Route: POST /sessions
# ---------------------------------------------------------------------------


def _start_session(event: dict) -> dict:
    body = _parse_body(event)
    run_id = str(uuid.uuid4())

    container_overrides = {
        "containerOverrides": [
            {
                "name": "simulation",
                "environment": [
                    {"name": "SEED", "value": str(body.get("seed", ""))},
                    {"name": "DIFFICULTY", "value": body.get("difficulty", "normal")},
                    {
                        "name": "MISSION_SOLS",
                        "value": str(body.get("mission_sols", 450)),
                    },
                    {"name": "TICK_DELAY_MS", "value": "0"},
                    {"name": "RUN_ID", "value": run_id},
                    {"name": "RESULTS_BUCKET", "value": RESULTS_BUCKET},
                    {"name": "AGENT_RUNTIME_ARN", "value": AGENT_RUNTIME_ARN},
                    {
                        "name": "SCENARIO_PRESET",
                        "value": body.get("scenario_preset", ""),
                    },
                ],
            }
        ]
    }

    try:
        resp = ecs.run_task(
            cluster=CLUSTER_NAME,
            taskDefinition=TASK_DEFINITION_ARN,
            launchType="FARGATE",
            networkConfiguration={
                "awsvpcConfiguration": {
                    "subnets": SUBNET_IDS,
                    "securityGroups": [SECURITY_GROUP_ID],
                    "assignPublicIp": "ENABLED",
                }
            },
            overrides=container_overrides,
            startedBy=run_id,
        )
    except Exception as exc:
        logger.exception("ecs.run_task raised for run %s", run_id)
        return _json_response(
            500, {"error": f"ECS RunTask failed: {exc}"}
        )

    tasks = resp.get("tasks", [])
    if not tasks:
        failures = resp.get("failures", [])
        logger.error("run_task failed: %s", failures)
        return _json_response(
            500, {"error": "Failed to start task", "details": failures}
        )

    task = tasks[0]
    return _json_response(
        201,
        {
            "session_id": run_id,
            "run_id": run_id,
            "status": "starting",
            "task_arn": task["taskArn"],
            "started_at": datetime.now(UTC).isoformat(),
        },
    )


# ---------------------------------------------------------------------------
# Route: GET /sessions
# ---------------------------------------------------------------------------


ECS_STATUS_MAP: dict[str, str] = {
    "PROVISIONING": "starting",
    "PENDING": "starting",
    "ACTIVATING": "starting",
    "RUNNING": "running",
    "DEACTIVATING": "stopped",
    "STOPPING": "stopped",
    "DEPROVISIONING": "stopped",
    "STOPPED": "stopped",
}


def _normalize_status(ecs_status: str, stop_code: str | None = None) -> str:
    """Map ECS task status to a frontend-friendly lowercase status."""
    mapped = ECS_STATUS_MAP.get(ecs_status, "starting")
    # If the task stopped, check if it completed successfully vs failed
    if mapped == "stopped" and stop_code:
        if stop_code == "EssentialContainerExited":
            mapped = "completed"
        elif stop_code in ("TaskFailedToStart", "ServiceSchedulerInitiated"):
            mapped = "failed"
    return mapped


def _extract_task_info(task: dict) -> dict:
    """Build a session info dict from an ECS task description."""
    task_arn = task["taskArn"]
    ecs_status = task.get("lastStatus", "UNKNOWN")
    stop_code = task.get("stopCode")
    status = _normalize_status(ecs_status, stop_code)
    started_by = task.get("startedBy", "")
    started_at = task.get("startedAt")

    # Extract ENI ID from task attachments, then resolve public IP via EC2
    public_ip = None
    for attachment in task.get("attachments", []):
        if attachment.get("type") != "ElasticNetworkInterface":
            continue
        for detail in attachment.get("details", []):
            if detail.get("name") == "networkInterfaceId":
                public_ip = _resolve_public_ip(detail["value"])
                break
        if public_ip:
            break

    ws_url = f"ws://{public_ip}:8080/ws" if public_ip else None

    return {
        "session_id": started_by,
        "task_arn": task_arn,
        "run_id": started_by,
        "status": status,
        "public_ip": public_ip,
        "ws_url": ws_url,
        "started_at": started_at,
    }


def _list_sessions(event: dict) -> dict:
    task_arns = []
    for desired in ("RUNNING", "STOPPED"):
        resp = ecs.list_tasks(cluster=CLUSTER_NAME, desiredStatus=desired)
        task_arns.extend(resp.get("taskArns", []))

    if not task_arns:
        return _json_response(200, [])

    # describe_tasks accepts max 100 ARNs — fine for hackathon scale
    described = ecs.describe_tasks(cluster=CLUSTER_NAME, tasks=task_arns)
    sessions = [_extract_task_info(t) for t in described.get("tasks", [])]

    # Sort by started_at descending (newest first)
    sessions.sort(key=lambda s: s.get("started_at") or "", reverse=True)

    return _json_response(200, sessions)


# ---------------------------------------------------------------------------
# Route: GET /sessions/{id}
# ---------------------------------------------------------------------------


def _get_session(event: dict, run_id: str) -> dict:
    # Search across active and stopped tasks
    task_arns = []
    for desired in ("RUNNING", "STOPPED"):
        resp = ecs.list_tasks(
            cluster=CLUSTER_NAME,
            desiredStatus=desired,
            startedBy=run_id,
        )
        task_arns.extend(resp.get("taskArns", []))

    if not task_arns:
        return _json_response(404, {"error": "Session not found"})

    described = ecs.describe_tasks(cluster=CLUSTER_NAME, tasks=task_arns)
    tasks = described.get("tasks", [])
    if not tasks:
        return _json_response(404, {"error": "Session not found"})

    task = tasks[0]
    info = _extract_task_info(task)

    # If stopped, check S3 for results
    if task.get("lastStatus") == "STOPPED":
        try:
            s3_resp = s3.get_object(
                Bucket=RESULTS_BUCKET,
                Key=f"results/{run_id}.json",
            )
            results = json.loads(s3_resp["Body"].read())
            info["final_score"] = results.get("final_score")
        except s3.exceptions.NoSuchKey:
            info["final_score"] = None
        except Exception:
            logger.exception("Failed to fetch results for %s", run_id)
            info["final_score"] = None

    return _json_response(200, info)


# ---------------------------------------------------------------------------
# Route: DELETE /sessions/{id}
# ---------------------------------------------------------------------------


def _stop_session(event: dict, run_id: str) -> dict:
    resp = ecs.list_tasks(
        cluster=CLUSTER_NAME,
        desiredStatus="RUNNING",
        startedBy=run_id,
    )
    task_arns = resp.get("taskArns", [])
    if not task_arns:
        return _json_response(404, {"error": "No running session found"})

    for arn in task_arns:
        ecs.stop_task(
            cluster=CLUSTER_NAME,
            task=arn,
            reason="User requested stop",
        )

    return _json_response(200, {"status": "stopped"})


# ---------------------------------------------------------------------------
# Route: GET /sessions/{id}/results
# ---------------------------------------------------------------------------


def _get_results(event: dict, run_id: str) -> dict:
    try:
        s3_resp = s3.get_object(
            Bucket=RESULTS_BUCKET,
            Key=f"results/{run_id}.json",
        )
        results = json.loads(s3_resp["Body"].read())
        return _json_response(200, results)
    except Exception:
        logger.exception("Failed to fetch results for %s", run_id)
        return _json_response(404, {"error": "Results not found"})


# ---------------------------------------------------------------------------
# Router
# ---------------------------------------------------------------------------

# Pattern: /sessions/{id} or /sessions/{id}/results
SESSION_ID_RE = re.compile(r"^/sessions/([^/]+)$")
SESSION_RESULTS_RE = re.compile(r"^/sessions/([^/]+)/results$")


def handler(event, context):
    http = event.get("requestContext", {}).get("http", {})
    method = http.get("method", "")
    path = http.get("path", "")

    logger.info("Request: %s %s", method, path)

    try:
        return _route(method, path, event)
    except Exception as exc:
        logger.exception("Unhandled error in handler")
        return _json_response(500, {"error": str(exc)})


def _route(method: str, path: str, event: dict) -> dict:
    # GET /sessions/{id}/results
    match = SESSION_RESULTS_RE.match(path)
    if match and method == "GET":
        return _get_results(event, match.group(1))

    # GET /sessions/{id}
    match = SESSION_ID_RE.match(path)
    if match and method == "GET":
        return _get_session(event, match.group(1))

    # DELETE /sessions/{id}
    match = SESSION_ID_RE.match(path)
    if match and method == "DELETE":
        return _stop_session(event, match.group(1))

    # POST /sessions
    if path == "/sessions" and method == "POST":
        return _start_session(event)

    # GET /sessions
    if path == "/sessions" and method == "GET":
        return _list_sessions(event)

    return _json_response(404, {"error": f"Not found: {method} {path}"})
