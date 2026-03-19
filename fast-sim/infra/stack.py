"""
FastSimStack — CDK infrastructure for the fast-sim Lambda sweeper.

Resources:
  - SQS work queue (visibility timeout 900s, DLQ after 3 retries)
  - S3 results bucket (lifecycle: Glacier after 90 days)
  - DynamoDB waves table (partition: wave_id, sort: run_id, TTL)
  - CloudWatch Events rule (aggregator schedule, every 5 min)
  - IAM Lambda execution role (SQS, S3, DynamoDB, Bedrock AgentCore Memory)
  - Worker Lambda (DockerImageFunction, 2GB, 900s, 1000 reserved)
  - Dispatcher Lambda (DockerImageFunction, 512MB, 300s)
  - Aggregator Lambda (DockerImageFunction, 2GB, 900s)
  - Glue Database + Table for Athena querying
"""

from __future__ import annotations

from aws_cdk import (
    Duration,
    RemovalPolicy,
    Stack,
)
from aws_cdk import aws_dynamodb as dynamodb
from aws_cdk import aws_events as events
from aws_cdk import aws_events_targets as targets
from aws_cdk import aws_glue as glue
from aws_cdk import aws_iam as iam
from aws_cdk import aws_lambda as _lambda
from aws_cdk import aws_lambda_event_sources as lambda_event_sources
from aws_cdk import aws_s3 as s3
from aws_cdk import aws_sqs as sqs
from constructs import Construct


class FastSimStack(Stack):
    """Main infrastructure stack for fast-sim Lambda sweeper."""

    def __init__(self, scope: Construct, construct_id: str, **kwargs: object) -> None:
        super().__init__(scope, construct_id, **kwargs)

        # ── SQS Work Queue ───────────────────────────────────────────────────
        dlq = sqs.Queue(
            self,
            "FastSimDLQ",
            queue_name="fast-sim-dlq",
            retention_period=Duration.days(14),
        )

        work_queue = sqs.Queue(
            self,
            "FastSimWorkQueue",
            queue_name="fast-sim-work-queue",
            visibility_timeout=Duration.seconds(900),
            retention_period=Duration.days(4),
            dead_letter_queue=sqs.DeadLetterQueue(
                max_receive_count=3,
                queue=dlq,
            ),
        )

        # ── S3 Results Bucket ────────────────────────────────────────────────
        results_bucket = s3.Bucket(
            self,
            "FastSimResultsBucket",
            bucket_name=f"fast-sim-results-{self.account}",
            versioned=False,
            removal_policy=RemovalPolicy.RETAIN,
            lifecycle_rules=[
                s3.LifecycleRule(
                    id="GlacierAfter90Days",
                    transitions=[
                        s3.Transition(
                            storage_class=s3.StorageClass.GLACIER,
                            transition_after=Duration.days(90),
                        )
                    ],
                )
            ],
        )

        # ── DynamoDB Waves Table ─────────────────────────────────────────────
        waves_table = dynamodb.Table(
            self,
            "FastSimWavesTable",
            table_name="fast-sim-waves",
            partition_key=dynamodb.Attribute(
                name="wave_id",
                type=dynamodb.AttributeType.STRING,
            ),
            sort_key=dynamodb.Attribute(
                name="run_id",
                type=dynamodb.AttributeType.STRING,
            ),
            billing_mode=dynamodb.BillingMode.PAY_PER_REQUEST,
            removal_policy=RemovalPolicy.RETAIN,
            time_to_live_attribute="expires_at",
        )

        # ── IAM Lambda Execution Role ────────────────────────────────────────
        lambda_role = iam.Role(
            self,
            "FastSimLambdaRole",
            assumed_by=iam.ServicePrincipal("lambda.amazonaws.com"),
            managed_policies=[
                iam.ManagedPolicy.from_aws_managed_policy_name(
                    "service-role/AWSLambdaBasicExecutionRole"
                )
            ],
        )

        # SQS permissions
        work_queue.grant_consume_messages(lambda_role)
        work_queue.grant_send_messages(lambda_role)
        dlq.grant_send_messages(lambda_role)

        # S3 permissions
        results_bucket.grant_read_write(lambda_role)

        # DynamoDB permissions
        waves_table.grant_read_write_data(lambda_role)

        # Bedrock AgentCore Memory permissions
        lambda_role.add_to_policy(
            iam.PolicyStatement(
                actions=[
                    "bedrock:*",
                    "bedrock-agentcore:*",
                ],
                resources=["*"],
            )
        )

        # ── Docker image asset (shared by all 3 Lambdas) ─────────────────────
        # Image is built from the repo root so it can copy simulation/src.
        # The .dockerignore at repo root uses deny-all + whitelist pattern,
        # so Docker only sees simulation/src/ and fast-sim/src/.
        # CDK exclude list must also prevent asset fingerprinting from
        # walking into .venv, node_modules, cdk.out etc.
        import os  # noqa: PLC0415

        repo_root = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
        docker_image = _lambda.DockerImageCode.from_image_asset(
            directory=repo_root,
            file="fast-sim/Dockerfile",
            # Use .dockerignore for the actual Docker build context filtering.
            # CDK exclude controls asset fingerprinting — use top-level names
            # (not globs) to reliably prevent recursion into heavy dirs.
            exclude=[
                ".git",
                ".venv",
                "node_modules",
                "cdk.out",
                "__pycache__",
                ".mypy_cache",
                ".pytest_cache",
                ".ruff_cache",
                "session_logs",
                "agent",
                "frontend",
                "ml",
                "docs",
                ".claude",
                "fast-sim/.venv",
                "fast-sim/cdk.out",
                "fast-sim/__pycache__",
                "simulation/.venv",
                "simulation/__pycache__",
            ],
        )

        common_env = {
            "RESULTS_BUCKET": results_bucket.bucket_name,
            "WAVES_TABLE": waves_table.table_name,
            "WORK_QUEUE_URL": work_queue.queue_url,
            "MEMORY_ID": "fast-sim-learnings",
            "MEMORY_REGION": self.region,
            "ACTOR_ID": "mars-agent",
        }

        # ── Worker Lambda ────────────────────────────────────────────────────
        worker_fn = _lambda.DockerImageFunction(
            self,
            "FastSimWorker",
            function_name="fast-sim-worker",
            code=docker_image,
            memory_size=2048,
            timeout=Duration.seconds(900),
            reserved_concurrent_executions=1000,
            role=lambda_role,
            environment=common_env,
        )

        # SQS event source (batchSize=1: one simulation per invocation)
        worker_fn.add_event_source(
            lambda_event_sources.SqsEventSource(
                work_queue,
                batch_size=1,
            )
        )

        # ── Dispatcher Lambda ────────────────────────────────────────────────
        _lambda.DockerImageFunction(
            self,
            "FastSimDispatcher",
            function_name="fast-sim-dispatcher",
            code=docker_image,
            memory_size=512,
            timeout=Duration.seconds(300),
            role=lambda_role,
            environment=common_env,
        )

        # ── Aggregator Lambda ────────────────────────────────────────────────
        aggregator_fn = _lambda.DockerImageFunction(
            self,
            "FastSimAggregator",
            function_name="fast-sim-aggregator",
            code=docker_image,
            memory_size=2048,
            timeout=Duration.seconds(900),
            role=lambda_role,
            environment=common_env,
        )

        # ── CloudWatch Events Schedule (every 5 minutes) ─────────────────────
        events.Rule(
            self,
            "FastSimAggregatorSchedule",
            rule_name="fast-sim-aggregator-schedule",
            schedule=events.Schedule.rate(Duration.minutes(5)),
            targets=[targets.LambdaFunction(aggregator_fn)],
        )

        # ── Glue Database and Table for Athena ───────────────────────────────
        glue_db = glue.CfnDatabase(
            self,
            "FastSimGlueDatabase",
            catalog_id=self.account,
            database_input=glue.CfnDatabase.DatabaseInputProperty(
                name="fast_sim_db",
                description="fast-sim simulation results database",
            ),
        )

        glue.CfnTable(
            self,
            "FastSimResultsTable",
            catalog_id=self.account,
            database_name="fast_sim_db",
            table_input=glue.CfnTable.TableInputProperty(
                name="results",
                description="fast-sim run results (JSON via JsonSerDe)",
                table_type="EXTERNAL_TABLE",
                parameters={
                    "classification": "json",
                    "projection.enabled": "true",
                    "projection.wave_id.type": "injected",
                    "storage.location.template": f"s3://{results_bucket.bucket_name}/results/${{wave_id}}/",
                },
                partition_keys=[glue.CfnTable.ColumnProperty(name="wave_id", type="string")],
                storage_descriptor=glue.CfnTable.StorageDescriptorProperty(
                    location=f"s3://{results_bucket.bucket_name}/results/",
                    input_format="org.apache.hadoop.mapred.TextInputFormat",
                    output_format="org.apache.hadoop.hive.ql.io.HiveIgnoreKeyTextOutputFormat",
                    serde_info=glue.CfnTable.SerdeInfoProperty(
                        serialization_library="org.openx.data.jsonserde.JsonSerDe",
                        parameters={"serialization.format": "1"},
                    ),
                    columns=[
                        glue.CfnTable.ColumnProperty(name="run_id", type="string"),
                        glue.CfnTable.ColumnProperty(name="seed", type="bigint"),
                        glue.CfnTable.ColumnProperty(name="difficulty", type="string"),
                        glue.CfnTable.ColumnProperty(name="final_sol", type="int"),
                        glue.CfnTable.ColumnProperty(name="mission_outcome", type="string"),
                        glue.CfnTable.ColumnProperty(name="final_score", type="int"),
                        glue.CfnTable.ColumnProperty(name="survival_score", type="int"),
                        glue.CfnTable.ColumnProperty(name="nutrition_score", type="int"),
                        glue.CfnTable.ColumnProperty(name="resource_efficiency_score", type="int"),
                        glue.CfnTable.ColumnProperty(name="crisis_mgmt_score", type="int"),
                        glue.CfnTable.ColumnProperty(name="crises_encountered", type="int"),
                        glue.CfnTable.ColumnProperty(name="crises_resolved", type="int"),
                        glue.CfnTable.ColumnProperty(name="crop_deaths", type="int"),
                        glue.CfnTable.ColumnProperty(name="crops_planted", type="int"),
                        glue.CfnTable.ColumnProperty(name="crops_harvested", type="int"),
                        glue.CfnTable.ColumnProperty(name="duration_seconds", type="double"),
                        glue.CfnTable.ColumnProperty(name="config_hash", type="string"),
                        glue.CfnTable.ColumnProperty(name="crisis_log_json", type="string"),
                        glue.CfnTable.ColumnProperty(name="crop_yields_json", type="string"),
                        glue.CfnTable.ColumnProperty(name="resource_extremes_json", type="string"),
                        glue.CfnTable.ColumnProperty(name="resource_averages_json", type="string"),
                        glue.CfnTable.ColumnProperty(name="key_decisions_json", type="string"),
                        glue.CfnTable.ColumnProperty(name="strategy_config_json", type="string"),
                    ],
                ),
            ),
        )
        glue_db  # used above in table
