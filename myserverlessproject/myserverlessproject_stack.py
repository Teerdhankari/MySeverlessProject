# In myserverlessproject/myserverlessproject_stack.py

import os
from aws_cdk import (
    Stack,
    RemovalPolicy,
    Duration,
    CfnOutput,
    SecretValue, # Keep if considering GitHub PAT alternative
    aws_dynamodb as dynamodb,
    aws_iam as iam,
    aws_lambda as _lambda, # Using alias to avoid conflict with Python keyword
    # Import the specific submodule for Python Lambda Alpha
    aws_lambda_python_alpha as lambda_python, # Correct import for PythonFunction
    aws_apigateway as apigw,
    aws_codepipeline as codepipeline,
    aws_codepipeline_actions as codepipeline_actions,
    aws_codebuild as codebuild,
)
from constructs import Construct

# --- Constants ---
# Ensure these match your GitHub repository details
GITHUB_OWNER = "Teerdhankari"
GITHUB_REPO = "MySeverlessProject"
GITHUB_BRANCH = "main" # Or your primary development branch

# vvvvvvvvvvvvvvvvvvvvvvvvvvvvvvvvvvvvvvvvvvvvvvvvvvvvvvvvvvvvvvvvvvvvvvvvvvvvvvv
# CRITICAL: VALIDATE AND REPLACE THIS ARN!
# Get the ARN from the AWS Console -> Developer Tools -> CodeStar Connections
# Make sure it's for the correct AWS Region (e.g., ap-south-1 based on your EC2 info)
# The service name is 'codestar-connections'.
# Format: arn:aws:codestar-connections:REGION:ACCOUNT_ID:connection/UUID
CODESTAR_CONNECTION_ARN = "arn:aws:codeconnections:us-east-1:383014559627:connection/67d7ed99-3d52-4ab3-8a86-23c7c9ba61c0" # <--- ### REPLACE THIS VALUE ###
# ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^

class MyserverlessprojectStack(Stack):

    def __init__(self, scope: Construct, construct_id: str, **kwargs) -> None:
        super().__init__(scope, construct_id, **kwargs)

        # --- DynamoDB Table ---
        self.items_table = dynamodb.Table(
            self, "ItemsTable",
            partition_key=dynamodb.Attribute(
                name="itemID",
                type=dynamodb.AttributeType.STRING
            ),
            billing_mode=dynamodb.BillingMode.PAY_PER_REQUEST,
            # WARNING: RemovalPolicy.DESTROY deletes the table when the stack is deleted.
            #          Change to RemovalPolicy.RETAIN or RETAIN_ON_UPDATE_OR_DELETE for production data.
            removal_policy=RemovalPolicy.DESTROY
        )

        # --- IAM Role for Lambda ---
        self.lambda_role = iam.Role(
            self, "LambdaExecutionRole",
            assumed_by=iam.ServicePrincipal("lambda.amazonaws.com"),
            managed_policies=[
                # Provides permissions for Lambda logging to CloudWatch Logs
                iam.ManagedPolicy.from_aws_managed_policy_name(
                    "service-role/AWSLambdaBasicExecutionRole"
                )
            ]
        )

        # --- Grant Permissions to Lambda Role ---
        self.items_table.grant_read_write_data(self.lambda_role)

        # --- Lambda Function (using PythonFunction for auto-bundling) ---
        self.api_lambda = lambda_python.PythonFunction(
            self, "ApiHandlerLambda",
            entry="lambda_src",          # Directory containing Lambda code (lambda_src/)
            index="api_handler.py",      # File with the handler function within 'entry'
            handler="lambda_handler",    # Function name in the index file
            runtime=_lambda.Runtime.PYTHON_3_11, # Match runtime used in CodeBuild/tests
            role=self.lambda_role,       # Assign the execution role
            timeout=Duration.seconds(30),
            memory_size=256,
            environment={
                "DYNAMODB_TABLE_NAME": self.items_table.table_name,
                "LOG_LEVEL": "INFO"
            },
            # Note: Bundling happens automatically using Docker. Requires Docker running
            # if deploying locally. In CodeBuild, the standard image has Docker.
            # This step caused the NoSuchKey error previously, ensure Build stage logs
            # show successful asset bundling and upload if issues persist.
        )

        # --- API Gateway ---
        self.api = apigw.LambdaRestApi(
            self, "ItemsApi",
            handler=self.api_lambda,     # Default Lambda integration
            proxy=False,                 # Define specific resources/methods below
            deploy_options=apigw.StageOptions(
                stage_name="prod",       # Deployment stage name
                throttling_rate_limit=10,# Example throttling
                throttling_burst_limit=5
            ),
            # WARNING: Default CORS settings are very permissive (allow all origins/methods).
            #          For production, restrict allow_origins to your specific frontend domain.
            default_cors_preflight_options=apigw.CorsOptions(
                allow_origins=apigw.Cors.ALL_ORIGINS,
                allow_methods=apigw.Cors.ALL_METHODS,
                allow_headers=apigw.Cors.DEFAULT_HEADERS + ['X-Api-Key', 'Authorization'] # Example including common custom headers
            )
        )

        # --- API Gateway Resources and Methods ---
        items_resource = self.api.root.add_resource("items")
        items_resource.add_method("POST") # Connects POST /items to api_lambda
        items_resource.add_method("GET")  # Connects GET /items to api_lambda

        item_id_resource = items_resource.add_resource("{itemID}") # Path parameter {itemID}
        item_id_resource.add_method("GET")    # Connects GET /items/{itemID} to api_lambda
        item_id_resource.add_method("PUT")    # Connects PUT /items/{itemID} to api_lambda
        item_id_resource.add_method("DELETE") # Connects DELETE /items/{itemID} to api_lambda

        # --- CDK Outputs (Infrastructure) ---
        CfnOutput(self, "DynamoDBTableNameOutput", value=self.items_table.table_name, export_name="ItemsTableName")
        CfnOutput(self, "LambdaFunctionArnOutput", value=self.api_lambda.function_arn, export_name="ApiLambdaArn")
        CfnOutput(self, "ApiEndpointUrlOutput", value=self.api.url, export_name="ApiUrl")

        # ======================================================================
        # --- CI/CD Pipeline Definition ---
        # ======================================================================

        # --- Pipeline Artifacts ---
        source_output = codepipeline.Artifact("SourceOutput")
        cdk_build_output = codepipeline.Artifact("CdkBuildOutput")

        # --- CodeBuild Project Definition ---
        cdk_build_project = codebuild.PipelineProject(
            self, "CdkBuildProject",
            project_name="ServerlessApi-CDK-Build",
            build_spec=codebuild.BuildSpec.from_object({
                "version": "0.2",
                "phases": {
                    "install": {
                        "runtime-versions": {
                            "python": "3.11" # Match Lambda runtime
                        },
                        "commands": [
                            "echo Installing Python project dependencies...",
                            "pip install -r requirements.txt",      # For CDK app itself
                            "pip install -r requirements-dev.txt" # For testing (pytest)
                        ]
                    },
                    "pre_build": {
                        "commands": [
                            "echo Running unit tests...",
                            "pytest tests/unit/" # Expects tests in tests/unit/
                        ]
                    },
                    "build": {
                        "commands": [
                            "echo Synthesizing CDK CloudFormation template...",
                            # npx ensures the CDK CLI version from node_modules is used (if defined in package.json)
                            # If CDK is installed globally in the image, 'cdk synth' also works.
                            "npx cdk synth"
                        ]
                    }
                }, # End phases
                "artifacts": {
                    "base-directory": "cdk.out", # Output directory of 'cdk synth'
                    "files": [
                        f"{self.stack_name}.template.json", # The synthesized CloudFormation template
                        "**/*" # Include any other assets/manifests in cdk.out
                    ]
                } # End artifacts
            }), # End build_spec
            environment=codebuild.BuildEnvironment(
                # Standard image with Python 3.11, Node.js, Docker pre-installed
                build_image=codebuild.LinuxBuildImage.STANDARD_7_0,
                privileged=False # Docker commands for bundling work without privileged mode
            ),
            # Note: The default CodeBuild role needs permissions to access the CDK S3 staging bucket
            #       (usually granted by default) and potentially ECR if using custom bundling images.
        )

        # --- CodePipeline Definition ---
        self.pipeline = codepipeline.Pipeline(
            self, "ServerlessApiPipeline",
            pipeline_name="MyServerlessApiPipeline",
            cross_account_keys=False,
            restart_execution_on_update=True # Automatically restart pipeline if definition changes
        )

        # --- Pipeline Stages ---

        # 1. Source Stage (GitHub)
        self.pipeline.add_stage(
            stage_name="Source",
            actions=[
                codepipeline_actions.CodeStarConnectionsSourceAction(
                    action_name="GitHub_Source",
                    owner=GITHUB_OWNER,
                    repo=GITHUB_REPO,
                    branch=GITHUB_BRANCH,
                    connection_arn=CODESTAR_CONNECTION_ARN, # Use the validated ARN constant
                    output=source_output,
                    trigger_on_push=True
                )
            ]
        )

        # 2. Build Stage (CodeBuild: Test & Synth)
        self.pipeline.add_stage(
            stage_name="Build",
            actions=[
                codepipeline_actions.CodeBuildAction(
                    action_name="CDK_Build_Synth",
                    project=cdk_build_project,
                    input=source_output,      # Use code from Source stage
                    outputs=[cdk_build_output] # Produce artifact for Deploy stage
                )
            ]
        )

        # 3. Deploy Stage (CloudFormation)
        self.pipeline.add_stage(
            stage_name="Deploy",
            actions=[
                codepipeline_actions.CloudFormationCreateUpdateStackAction(
                    action_name="Deploy_CFN_Stack",
                    stack_name=self.stack_name,
                    template_path=cdk_build_output.at_path(f"{self.stack_name}.template.json"),
                    # WARNING: admin_permissions=True is convenient for demos but insecure for production.
                    #          Create a dedicated CloudFormation deployment IAM Role with least privilege
                    #          and assign it using 'deployment_role' property instead.
                    admin_permissions=True,
                    run_order=1
                )
                # Add other actions like integration tests or manual approvals after initial deploy
                # codepipeline_actions.ManualApprovalAction(action_name="Approve_Prod", run_order=2)
            ]
        )

        # --- CDK Output (Pipeline) ---
        CfnOutput(self, "PipelineNameOutput", value=self.pipeline.pipeline_name, export_name="MyPipelineName")