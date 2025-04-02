# In myserverlessproject/myserverlessproject_stack.py

import os
from aws_cdk import (
    Stack,
    RemovalPolicy,
    Duration,
    CfnOutput,
    SecretValue,
    aws_dynamodb as dynamodb,
    aws_iam as iam,
    aws_lambda as _lambda, # Using alias to avoid conflict with Python keyword
    # Import the specific submodule for Python Lambda Alpha
    aws_lambda_python_alpha as lambda_python, # <--- CORRECTED IMPORT
    aws_apigateway as apigw,
    aws_codepipeline as codepipeline,
    aws_codepipeline_actions as codepipeline_actions,
    aws_codebuild as codebuild,
)
from constructs import Construct

# --- Constants ---
# Replace with your actual GitHub details and CodeStar Connection ARN
# !!! IMPORTANT: Do NOT commit your personal access token if using that method !!!
GITHUB_OWNER = "Teerdhankari"
GITHUB_REPO = "MySeverlessProject"
GITHUB_BRANCH = "main" # Or your default development branch

# vvvvvvvvvvvvvvvvvvvvvvvvvvvvvvvvvvvvvvvvvvvvvvvvvvvvvvvvvvvvvvvvvvvvvvvvvvvvvvv
# PASTE YOUR COPIED CODESTAR CONNECTION ARN FROM AWS CONSOLE HERE:
# It looks like: arn:aws:codestar-connections:REGION:ACCOUNT_ID:connection/UUID
CODESTAR_CONNECTION_ARN = "arn:aws:codeconnections:us-east-1:383014559627:connection/67d7ed99-3d52-4ab3-8a86-23c7c9ba61c0" # <--- REPLACE THIS VALUE
# ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^

class MyserverlessprojectStack(Stack):

    def __init__(self, scope: Construct, construct_id: str, **kwargs) -> None:
        super().__init__(scope, construct_id, **kwargs)

        # --- DynamoDB Table ---
        # Define the DynamoDB table for storing items
        self.items_table = dynamodb.Table(
            self, "ItemsTable",
            partition_key=dynamodb.Attribute(
                name="itemID",
                type=dynamodb.AttributeType.STRING
            ),
            billing_mode=dynamodb.BillingMode.PAY_PER_REQUEST,
            # IMPORTANT: DESTROY deletes table when stack is deleted. Change to RETAIN for production data.
            removal_policy=RemovalPolicy.DESTROY
        )

        # --- IAM Role for Lambda ---
        # Define the execution role that the Lambda function will use
        self.lambda_role = iam.Role(
            self, "LambdaExecutionRole",
            assumed_by=iam.ServicePrincipal("lambda.amazonaws.com"),
            managed_policies=[
                # Provides permissions for Lambda logging to CloudWatch
                iam.ManagedPolicy.from_aws_managed_policy_name(
                    "service-role/AWSLambdaBasicExecutionRole"
                )
            ]
        )

        # --- Grant Permissions ---
        # Grant the Lambda function's role permissions to Read/Write to the DynamoDB table
        self.items_table.grant_read_write_data(self.lambda_role)

        # --- Lambda Function ---
        # Use PythonFunction construct for auto-bundling and handling dependencies from requirements.txt
        self.api_lambda = lambda_python.PythonFunction(
            self, "ApiHandlerLambda",
            entry="lambda_src",          # Directory containing Lambda code (lambda_src/)
            index="api_handler.py",      # File with the handler function
            handler="lambda_handler",    # Function name in the file
            runtime=_lambda.Runtime.PYTHON_3_11, # Or PYTHON_3_10, PYTHON_3_12 etc.
            role=self.lambda_role,       # Assign the role created earlier
            timeout=Duration.seconds(30),
            memory_size=256,
            environment={
                # Pass the DynamoDB table name to the Lambda function
                "DYNAMODB_TABLE_NAME": self.items_table.table_name,
                "LOG_LEVEL": "INFO"      # Example environment variable for logging config
            }
            # Bundling automatically includes requirements.txt from the 'entry' directory if it exists
            # Or you can specify a project root:
            # project_root=os.path.dirname(__file__) # Or point to the main project dir
        )

        # --- API Gateway ---
        # Define the REST API that fronts the Lambda function
        self.api = apigw.LambdaRestApi(
            self, "ItemsApi",
            handler=self.api_lambda,     # Default handler for routes defined below
            proxy=False,                 # We explicitly define resources and methods
            deploy_options=apigw.StageOptions(
                stage_name="prod",       # Deploy to a 'prod' stage
                throttling_rate_limit=10,# Example throttling
                throttling_burst_limit=5
            ),
            # Enable CORS for all methods on the API. Be more restrictive in production.
            default_cors_preflight_options=apigw.CorsOptions(
                allow_origins=apigw.Cors.ALL_ORIGINS, # WARNING: Very permissive. Restrict to your frontend domain in production.
                allow_methods=apigw.Cors.ALL_METHODS, # Allows GET, POST, PUT, DELETE, OPTIONS etc.
                allow_headers=['Content-Type', 'X-Amz-Date', 'Authorization', 'X-Api-Key', 'X-Amz-Security-Token']
            )
        )

        # --- API Gateway Resources and Methods ---
        # Define the '/items' resource
        items_resource = self.api.root.add_resource("items")
        items_resource.add_method("POST") # Integrates with self.api_lambda by default
        items_resource.add_method("GET")  # Integrates with self.api_lambda by default

        # Define the '/items/{itemID}' resource (path parameter)
        item_id_resource = items_resource.add_resource("{itemID}")
        item_id_resource.add_method("GET")    # Integrates with self.api_lambda
        item_id_resource.add_method("PUT")    # Integrates with self.api_lambda
        item_id_resource.add_method("DELETE") # Integrates with self.api_lambda

        # --- CDK Outputs (Infrastructure) ---
        CfnOutput(self, "DynamoDBTableName", value=self.items_table.table_name)
        CfnOutput(self, "LambdaFunctionArn", value=self.api_lambda.function_arn)
        CfnOutput(self, "ApiEndpointUrl", value=self.api.url) # Provides the base URL for the API

        # ======================================================================
        # --- CI/CD Pipeline Definition ---
        # ======================================================================

        # --- Pipeline Artifacts ---
        # Represents the output of the Source stage (source code)
        source_output = codepipeline.Artifact("SourceOutput")
        # Represents the output of the Build stage (synthesized CDK template)
        cdk_build_output = codepipeline.Artifact("CdkBuildOutput")

        # --- CodeBuild Project Definition ---
        # Defines how the CDK app is synthesized and tested
        cdk_build_project = codebuild.PipelineProject(
            self, "CdkBuildProject",
            project_name="ServerlessApi-CDK-Build",
            build_spec=codebuild.BuildSpec.from_object({
                "version": "0.2",
                "phases": {
                    "install": {
                        "runtime-versions": {
                            # Match the Node/Python versions needed for CDK and your tests/app
                            "python": "3.11"
                        },
                        "commands": [
                            "echo Installing Python dependencies...",
                            "pip install -r requirements.txt",      # CDK dependencies
                            "pip install -r requirements-dev.txt" # Pytest etc.
                            # No need to install Node/NPM/CDK CLI explicitly if using standard image
                        ]
                    },
                    "pre_build": {
                        "commands": [
                            "echo Running unit tests...",
                            "pytest tests/unit/" # Run tests defined in tests/unit directory
                        ]
                    },
                    "build": {
                        "commands": [
                            "echo Synthesizing CDK CloudFormation template...",
                            # Use npx to ensure the CDK version matches package.json (if you add it)
                            # or just 'cdk synth' if using globally installed CDK
                            "npx cdk synth"
                        ]
                    }
                }, # End of phases
                "artifacts": {
                    # Specify the output directory for the synthesized CloudFormation templates
                    "base-directory": "cdk.out", # CDK output directory
                    "files": [
                        # Include the main stack template JSON file
                        f"{self.stack_name}.template.json",
                        # Include any other assets (like Lambda code zip if not using PythonFunction's bundling)
                        "**/*"
                    ]
                } # End of artifacts
            }), # IMPORTANT: This closes the from_object dictionary and the method call
            environment=codebuild.BuildEnvironment(
                # Use a standard AWS CodeBuild image that includes Node.js and Python
                build_image=codebuild.LinuxBuildImage.STANDARD_7_0,
                privileged=False # Usually not needed unless building Docker images
            ),
            # Grant necessary permissions IF the build needs to access other AWS services
            # (e.g., fetching secrets, accessing ECR). Not needed for basic cdk synth/pytest.
            # role=...
        )

        # --- CodePipeline Definition ---
        self.pipeline = codepipeline.Pipeline(
            self, "ServerlessApiPipeline",
            pipeline_name="MyServerlessApiPipeline",
            cross_account_keys=False, # Keep False for single-account setup
            # Restart pipeline execution if the pipeline definition itself is updated via CDK
            restart_execution_on_update=True
        )

        # --- Pipeline Stages ---

        # 1. Source Stage (Get code from GitHub)
        self.pipeline.add_stage(
            stage_name="Source",
            actions=[
                codepipeline_actions.CodeStarConnectionsSourceAction(
                    action_name="GitHub_Source",
                    owner=GITHUB_OWNER,
                    repo=GITHUB_REPO,
                    branch=GITHUB_BRANCH,
                    connection_arn=CODESTAR_CONNECTION_ARN, # The ARN you created in AWS Console
                    output=source_output,
                    # Automatically trigger pipeline on commits pushed to the specified branch
                    trigger_on_push=True
                )
                # Alternative using GitHub personal access token (less recommended than CodeStar Connections):
                # Make sure token is stored securely in AWS Secrets Manager
                # codepipeline_actions.GitHubSourceAction(
                #     action_name="GitHub_Source",
                #     owner=GITHUB_OWNER,
                #     repo=GITHUB_REPO,
                #     branch=GITHUB_BRANCH,
                #     oauth_token=SecretValue.secrets_manager("your-github-token-secret-name"),
                #     output=source_output,
                #     trigger=codepipeline_actions.GitHubTrigger.WEBHOOK # Or POLL
                # )
            ]
        )

        # 2. Build Stage (Run tests, synthesize CDK template)
        self.pipeline.add_stage(
            stage_name="Build",
            actions=[
                codepipeline_actions.CodeBuildAction(
                    action_name="CDK_Build_Synth",
                    project=cdk_build_project, # The CodeBuild project defined above
                    input=source_output,       # Input is the source code from GitHub
                    outputs=[cdk_build_output] # Output is the cdk.out directory contents
                )
            ]
        )

        # 3. Deploy Stage (Deploy CloudFormation stack using the template from Build stage)
        self.pipeline.add_stage(
            stage_name="Deploy",
            actions=[
                codepipeline_actions.CloudFormationCreateUpdateStackAction(
                    action_name="Deploy_CFN_Stack",
                    # Use the stack name defined by this CDK app instance
                    stack_name=self.stack_name,
                    # Specify the template file from the build artifact
                    template_path=cdk_build_output.at_path(f"{self.stack_name}.template.json"),
                    # Grant CloudFormation permissions to create/update resources defined in the stack
                    # WARNING: admin_permissions=True is broad. Create a specific deployment role for production.
                    admin_permissions=True,
                    # If not using admin_permissions, you'd specify roles here:
                    # deployment_role=cfn_deployment_role, # Role assumed by CloudFormation
                    # role=pipeline_cfn_action_role,       # Role assumed by the Pipeline action itself
                    run_order=1 # First action in this stage
                )
                # --- Add more actions here for further steps ---
                # Example: Integration Testing Action (if you build one)
                # Example: Manual Approval Action
                # codepipeline_actions.ManualApprovalAction(action_name="Manual_Approval", run_order=2)
            ]
        )

        # --- CDK Output (Pipeline) ---
        CfnOutput(self, "PipelineName", value=self.pipeline.pipeline_name)