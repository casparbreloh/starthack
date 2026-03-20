from pathlib import Path

from aws_cdk import CfnOutput, Duration, RemovalPolicy, Stack
from aws_cdk import aws_amplify as amplify
from aws_cdk import aws_apigatewayv2 as apigwv2
from aws_cdk import aws_apigatewayv2_integrations as apigwv2_integrations
from aws_cdk import aws_bedrockagentcore as agentcore
from aws_cdk import aws_cloudfront as cloudfront
from aws_cdk import aws_cloudfront_origins as origins
from aws_cdk import aws_ec2 as ec2
from aws_cdk import aws_ecr_assets as ecr_assets
from aws_cdk import aws_ecs as ecs
from aws_cdk import aws_elasticloadbalancingv2 as elbv2
from aws_cdk import aws_iam as iam
from aws_cdk import aws_lambda as lambda_
from aws_cdk import aws_logs as logs
from aws_cdk import aws_s3 as s3
from constructs import Construct

_INFRA_DIR = Path(__file__).parent.parent
_AGENT_DIR = _INFRA_DIR.parent / "agent"
_SIMULATION_DIR = _INFRA_DIR.parent / "simulation"
_ML_DIR = _INFRA_DIR.parent / "ml"


class OasisStack(Stack):
    def __init__(self, scope: Construct, construct_id: str, **kwargs) -> None:
        super().__init__(scope, construct_id, **kwargs)

        # --- VPC ---
        vpc = ec2.Vpc(
            self,
            "Vpc",
            vpc_name="oasis-vpc",
            max_azs=2,
            nat_gateways=1,
            subnet_configuration=[
                ec2.SubnetConfiguration(
                    name="Public",
                    subnet_type=ec2.SubnetType.PUBLIC,
                    cidr_mask=24,
                ),
                ec2.SubnetConfiguration(
                    name="Private",
                    subnet_type=ec2.SubnetType.PRIVATE_WITH_EGRESS,
                    cidr_mask=24,
                ),
            ],
        )

        # --- ECS Cluster ---
        cluster = ecs.Cluster(
            self,
            "Cluster",
            cluster_name="oasis",
            vpc=vpc,
        )

        # --- Simulation Docker Image ---
        simulation_image = ecr_assets.DockerImageAsset(
            self,
            "SimulationImage",
            directory=str(_SIMULATION_DIR),
            platform=ecr_assets.Platform.LINUX_AMD64,
        )

        # --- S3 Results Bucket ---
        results_bucket = s3.Bucket(
            self,
            "ResultsBucket",
            bucket_name=None,  # auto-generated
            removal_policy=RemovalPolicy.DESTROY,
            auto_delete_objects=True,
            lifecycle_rules=[
                s3.LifecycleRule(expiration=Duration.days(90)),
            ],
            cors=[
                s3.CorsRule(
                    allowed_methods=[s3.HttpMethods.GET],
                    allowed_origins=["*"],
                    allowed_headers=["*"],
                ),
            ],
        )

        # --- Security Group ---
        simulation_sg = ec2.SecurityGroup(
            self,
            "SimulationSg",
            vpc=vpc,
            description="Allow inbound WebSocket traffic to simulation tasks",
            allow_all_outbound=True,
        )
        # --- ALB Security Group ---
        alb_sg = ec2.SecurityGroup(
            self,
            "AlbSg",
            vpc=vpc,
            description="Allow inbound HTTP from CloudFront to ALB",
            allow_all_outbound=True,
        )
        alb_sg.add_ingress_rule(
            ec2.Peer.any_ipv4(),
            ec2.Port.tcp(80),
            "Allow inbound HTTP (CloudFront)",
        )

        simulation_sg.add_ingress_rule(
            alb_sg,
            ec2.Port.tcp(8080),
            "Allow inbound TCP 8080 from ALB",
        )

        # --- Application Load Balancer ---
        alb = elbv2.ApplicationLoadBalancer(
            self,
            "SimulationAlb",
            vpc=vpc,
            internet_facing=True,
            security_group=alb_sg,
            vpc_subnets=ec2.SubnetSelection(
                subnet_type=ec2.SubnetType.PUBLIC,
            ),
        )

        http_listener = alb.add_listener(
            "HttpListener",
            port=80,
            protocol=elbv2.ApplicationProtocol.HTTP,
            default_action=elbv2.ListenerAction.fixed_response(
                status_code=404,
                content_type="text/plain",
                message_body="No active session",
            ),
        )

        # --- CloudFront Distribution (TLS termination for WebSocket) ---
        cf_distribution = cloudfront.Distribution(
            self,
            "WsDistribution",
            default_behavior=cloudfront.BehaviorOptions(
                origin=origins.HttpOrigin(
                    alb.load_balancer_dns_name,
                    protocol_policy=cloudfront.OriginProtocolPolicy.HTTP_ONLY,
                    http_port=80,
                ),
                viewer_protocol_policy=cloudfront.ViewerProtocolPolicy.REDIRECT_TO_HTTPS,
                cache_policy=cloudfront.CachePolicy.CACHING_DISABLED,
                origin_request_policy=cloudfront.OriginRequestPolicy.ALL_VIEWER_EXCEPT_HOST_HEADER,
                allowed_methods=cloudfront.AllowedMethods.ALLOW_ALL,
            ),
        )

        # --- ML Lambda Function (Docker-based, ONNX Runtime inference) ---
        ml_fn = lambda_.DockerImageFunction(
            self,
            "MlFn",
            function_name="oasis-ml",
            code=lambda_.DockerImageCode.from_image_asset(
                directory=str(_ML_DIR),
                platform=ecr_assets.Platform.LINUX_ARM64,
            ),
            architecture=lambda_.Architecture.ARM_64,
            memory_size=512,
            timeout=Duration.seconds(30),
        )

        ml_fn_url = ml_fn.add_function_url(
            auth_type=lambda_.FunctionUrlAuthType.NONE,
        )

        # --- AgentCore Runtime (Bedrock-managed agent container) ---
        agent_image = ecr_assets.DockerImageAsset(
            self,
            "AgentImage",
            directory=str(_AGENT_DIR),
            platform=ecr_assets.Platform.LINUX_ARM64,
        )

        agent_runtime_role = iam.Role(
            self,
            "AgentRuntimeRole",
            assumed_by=iam.ServicePrincipal("bedrock-agentcore.amazonaws.com"),
            description="IAM role for the Oasis AgentCore Runtime",
        )
        agent_runtime_role.add_to_policy(
            iam.PolicyStatement(
                actions=[
                    "bedrock:InvokeModel",
                    "bedrock:InvokeModelWithResponseStream",
                ],
                resources=[
                    f"arn:aws:bedrock:{self.region}::foundation-model/*",
                    "arn:aws:bedrock:us-*::foundation-model/*",
                ],
            )
        )
        agent_runtime_role.add_managed_policy(
            iam.ManagedPolicy.from_aws_managed_policy_name(
                "AmazonEC2ContainerRegistryReadOnly"
            )
        )

        agent_runtime = agentcore.CfnRuntime(
            self,
            "AgentRuntime",
            agent_runtime_name="oasisAgent",
            agent_runtime_artifact=agentcore.CfnRuntime.AgentRuntimeArtifactProperty(
                container_configuration=agentcore.CfnRuntime.ContainerConfigurationProperty(
                    container_uri=agent_image.image_uri,
                ),
            ),
            network_configuration=agentcore.CfnRuntime.NetworkConfigurationProperty(
                network_mode="PUBLIC",
            ),
            role_arn=agent_runtime_role.role_arn,
            description="Oasis AI agent — manages a 450-sol crew mission",
            environment_variables={
                "MODEL_ID": "us.anthropic.claude-sonnet-4-6",
            },
        )

        agent_runtime_endpoint = agentcore.CfnRuntimeEndpoint(
            self,
            "AgentRuntimeEndpoint",
            agent_runtime_id=agent_runtime.attr_agent_runtime_id,
            name="oasisAgentEndpoint",
            description="Production endpoint for the Oasis agent",
        )

        # --- ECS Fargate Task Definition ---
        task_definition = ecs.FargateTaskDefinition(
            self,
            "SimulationTask",
            family="oasis-simulation",
            cpu=512,
            memory_limit_mib=1024,
        )

        results_bucket.grant_put(task_definition.task_role)

        # Allow simulation to invoke the agent via AgentCore
        task_definition.task_role.add_to_policy(
            iam.PolicyStatement(
                actions=["bedrock-agent-runtime:InvokeAgentRuntime"],
                resources=[agent_runtime.attr_agent_runtime_arn],
            )
        )

        log_group = logs.LogGroup(
            self,
            "SimulationLogGroup",
            log_group_name="/oasis/simulation",
            removal_policy=RemovalPolicy.DESTROY,
            retention=logs.RetentionDays.ONE_MONTH,
        )

        task_definition.add_container(
            "simulation",
            image=ecs.ContainerImage.from_docker_image_asset(simulation_image),
            port_mappings=[
                ecs.PortMapping(container_port=8080, protocol=ecs.Protocol.TCP),
            ],
            environment={
                "FARGATE_MODE": "1",
                "ML_SERVICE_URL": ml_fn_url.url,
                "AGENT_RUNTIME_ARN": agent_runtime.attr_agent_runtime_arn,
            },
            logging=ecs.LogDrivers.aws_logs(
                stream_prefix="simulation",
                log_group=log_group,
            ),
        )

        # --- Lambda Orchestrator ---
        public_subnets = vpc.select_subnets(
            subnet_type=ec2.SubnetType.PUBLIC,
        )

        orchestrator_fn = lambda_.Function(
            self,
            "OrchestratorFn",
            function_name="oasis-orchestrator",
            runtime=lambda_.Runtime.PYTHON_3_13,
            handler="index.handler",
            code=lambda_.Code.from_asset("lambda/orchestrator"),
            timeout=Duration.seconds(30),
            memory_size=256,
            environment={
                "CLUSTER_NAME": cluster.cluster_name,
                "TASK_DEFINITION_ARN": task_definition.task_definition_arn,
                "SUBNET_IDS": ",".join(
                    [subnet.subnet_id for subnet in public_subnets.subnets]
                ),
                "SECURITY_GROUP_ID": simulation_sg.security_group_id,
                "RESULTS_BUCKET": results_bucket.bucket_name,
                "AGENT_RUNTIME_ARN": agent_runtime.attr_agent_runtime_arn,
                "ALB_LISTENER_ARN": http_listener.listener_arn,
                "VPC_ID": vpc.vpc_id,
                "WS_BASE_URL": f"wss://{cf_distribution.distribution_domain_name}",
            },
        )

        # ECS permissions
        orchestrator_fn.add_to_role_policy(
            iam.PolicyStatement(
                actions=[
                    "ecs:RunTask",
                    "ecs:DescribeTasks",
                    "ecs:ListTasks",
                    "ecs:StopTask",
                ],
                resources=["*"],
                conditions={
                    "ArnEquals": {
                        "ecs:cluster": cluster.cluster_arn,
                    }
                },
            )
        )

        # RunTask also needs unconstrained ecs:RunTask on the task definition
        orchestrator_fn.add_to_role_policy(
            iam.PolicyStatement(
                actions=["ecs:RunTask"],
                resources=[task_definition.task_definition_arn],
            )
        )

        # PassRole for task execution role and task role
        orchestrator_fn.add_to_role_policy(
            iam.PolicyStatement(
                actions=["iam:PassRole"],
                resources=[
                    task_definition.execution_role.role_arn,
                    task_definition.task_role.role_arn,
                ],
            )
        )

        # EC2 permissions for resolving Fargate task public IPs from ENIs
        orchestrator_fn.add_to_role_policy(
            iam.PolicyStatement(
                actions=["ec2:DescribeNetworkInterfaces"],
                resources=["*"],
            )
        )

        # ELBv2 permissions for ALB target group / listener rule management
        orchestrator_fn.add_to_role_policy(
            iam.PolicyStatement(
                actions=[
                    "elasticloadbalancingv2:CreateTargetGroup",
                    "elasticloadbalancingv2:DeleteTargetGroup",
                    "elasticloadbalancingv2:RegisterTargets",
                    "elasticloadbalancingv2:DeregisterTargets",
                    "elasticloadbalancingv2:CreateRule",
                    "elasticloadbalancingv2:DeleteRule",
                    "elasticloadbalancingv2:DescribeRules",
                    "elasticloadbalancingv2:DescribeTargetGroups",
                ],
                resources=["*"],
            )
        )

        # S3 read for fetching results
        results_bucket.grant_read(orchestrator_fn)

        # --- API Gateway HTTP API ---
        http_api = apigwv2.HttpApi(
            self,
            "OrchestratorApi",
            api_name="oasis-api",
            cors_preflight=apigwv2.CorsPreflightOptions(
                allow_origins=["*"],
                allow_methods=[
                    apigwv2.CorsHttpMethod.GET,
                    apigwv2.CorsHttpMethod.POST,
                    apigwv2.CorsHttpMethod.DELETE,
                    apigwv2.CorsHttpMethod.OPTIONS,
                ],
                allow_headers=["*"],
            ),
        )

        lambda_integration = apigwv2_integrations.HttpLambdaIntegration(
            "OrchestratorIntegration",
            handler=orchestrator_fn,
        )

        routes = [
            ("POST", "/sessions"),
            ("GET", "/sessions"),
            ("GET", "/sessions/{id}"),
            ("DELETE", "/sessions/{id}"),
            ("GET", "/sessions/{id}/results"),
        ]
        for method_str, path in routes:
            http_method = apigwv2.HttpMethod(method_str)
            http_api.add_routes(
                path=path,
                methods=[http_method],
                integration=lambda_integration,
            )

        # --- Amplify Hosting (frontend) ---
        # Pass GitHub token via: make deploy GITHUB_TOKEN=ghp_xxx
        # Create one at https://github.com/settings/tokens with repo scope.
        github_token = self.node.try_get_context("github_token") or "PLACEHOLDER"

        amplify_app = amplify.CfnApp(
            self,
            "FrontendApp",
            name="oasis",
            repository="https://github.com/casparbreloh/starthack",
            access_token=github_token,
            platform="WEB",
            environment_variables=[
                amplify.CfnApp.EnvironmentVariableProperty(
                    name="VITE_ORCHESTRATOR_URL",
                    value=http_api.url or "",
                ),
                amplify.CfnApp.EnvironmentVariableProperty(
                    name="AMPLIFY_MONOREPO_APP_ROOT",
                    value="frontend",
                ),
            ],
            build_spec="""version: 1
applications:
  - appRoot: frontend
    frontend:
      phases:
        preBuild:
          commands:
            - npm install -g pnpm
            - pnpm install
        build:
          commands:
            - pnpm run build
      artifacts:
        baseDirectory: dist
        files:
          - '**/*'
      cache:
        paths:
          - node_modules/**/*
""",
        )

        amplify.CfnBranch(
            self,
            "FrontendMainBranch",
            app_id=amplify_app.attr_app_id,
            branch_name="main",
            enable_auto_build=True,
            framework="React",
            stage="PRODUCTION",
        )

        # --- CloudFormation Outputs ---

        CfnOutput(
            self,
            "TaskDefinitionArn",
            value=task_definition.task_definition_arn,
            export_name="TaskDefinitionArn",
        )
        CfnOutput(
            self,
            "ResultsBucketName",
            value=results_bucket.bucket_name,
            export_name="ResultsBucketName",
        )
        CfnOutput(
            self,
            "SecurityGroupId",
            value=simulation_sg.security_group_id,
            export_name="SimulationSecurityGroupId",
        )
        CfnOutput(
            self,
            "PublicSubnetIds",
            value=",".join([subnet.subnet_id for subnet in public_subnets.subnets]),
            export_name="PublicSubnetIds",
        )
        CfnOutput(
            self,
            "ClusterName",
            value=cluster.cluster_name,
            export_name="ClusterName",
        )
        CfnOutput(
            self,
            "SimulationImageUri",
            value=simulation_image.image_uri,
            export_name="SimulationImageUri",
        )
        CfnOutput(
            self,
            "MlFunctionUrl",
            value=ml_fn_url.url,
            description="Lambda function URL for the ML weather prediction service",
        )
        CfnOutput(
            self,
            "ApiUrl",
            value=http_api.url or "",
            export_name="ApiUrl",
            description="Orchestrator HTTP API URL",
        )
        CfnOutput(
            self,
            "AgentRuntimeArn",
            value=agent_runtime.attr_agent_runtime_arn,
            export_name="AgentRuntimeArn",
            description="ARN of the AgentCore Runtime for the Oasis agent",
        )
        CfnOutput(
            self,
            "AgentRuntimeEndpointArn",
            value=agent_runtime_endpoint.attr_agent_runtime_endpoint_arn,
            export_name="AgentRuntimeEndpointArn",
            description="ARN of the AgentCore Runtime endpoint",
        )
        CfnOutput(
            self,
            "AmplifyAppId",
            value=amplify_app.attr_app_id,
            description="Amplify app ID",
        )
        CfnOutput(
            self,
            "AmplifyAppUrl",
            value=f"https://main.{amplify_app.attr_default_domain}",
            description="Amplify frontend URL",
        )
        CfnOutput(
            self,
            "WsUrl",
            value=f"wss://{cf_distribution.distribution_domain_name}",
            description="CloudFront WebSocket URL (wss://)",
        )
        CfnOutput(
            self,
            "AlbDnsName",
            value=alb.load_balancer_dns_name,
            description="ALB DNS name (for debugging)",
        )
