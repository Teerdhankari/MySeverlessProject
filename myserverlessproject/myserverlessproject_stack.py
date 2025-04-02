# -----------------------------------------------------------------------------
# File: myserverlessproject/myserverlessproject_stack.py
# -----------------------------------------------------------------------------

from aws_cdk import (
    Stack,
    RemovalPolicy,  # For controlling resource deletion
    CfnOutput       # For outputting values like the API URL
)
# Import AWS service modules needed
import aws_cdk.aws_dynamodb as dynamodb
import aws_cdk.aws_lambda as _lambda  # Use _lambda to avoid keyword conflict
import aws_cdk.aws_apigateway as apigw

from constructs import Construct

# Define the main stack class
class MyserverlessprojectStack(Stack):

    def __init__(self, scope: Construct, construct_id: str, **kwargs) -> None:
        """
        Initializes the CDK stack defining the serverless API resources.
        """
        super().__init__(scope, construct_id, **kwargs)

        # --- 1. DynamoDB Table Definition ---
        # This table will store the notes data.
        notes_table = dynamodb.Table(
            self, "NotesTable",                     # Logical ID within CloudFormation
            partition_key=dynamodb.Attribute(       # Define the primary key
                name="noteId",                      # Name of the partition key attribute
                type=dynamodb.AttributeType.STRING  # Data type (S = String)
            ),
            billing_mode=dynamodb.BillingMode.PAY_PER_REQUEST, # Use on-demand capacity
            # WARNING: DESTROY is convenient for demos but risks data loss.
            # Use RETAIN or SNAPSHOT for production environments.
            removal_policy=RemovalPolicy.DESTROY
        )

        # --- 2. Lambda Function Definition ---
        # This function contains the Python code to handle API requests (CRUD operations).
        notes_lambda = _lambda.Function(
            self, "NotesFunction",                  # Logical ID within CloudFormation
            runtime=_lambda.Runtime.PYTHON_3_9,     # Specify the Python runtime
            handler="notes_handler.lambda_handler", # Points to lambda_functions/notes_handler.py -> lambda_handler function
            code=_lambda.Code.from_asset("lambda_functions"), # Directory containing the Lambda code
            environment={                           # Pass environment variables to the Lambda
                # The Lambda needs to know the name of the table to interact with.
                "DYNAMODB_TABLE_NAME": notes_table.table_name
            },
            # Optional: Increase memory or timeout if needed
            # memory_size=256,
            # timeout=cdk.Duration.seconds(10)
        )

        # --- 3. Grant Permissions ---
        # Explicitly grant the Lambda function read and write permissions to the DynamoDB table.
        notes_table.grant_read_write_data(notes_lambda)

        # --- 4. API Gateway Definition ---
        # This creates the HTTP endpoint that clients will call.
        notes_api = apigw.LambdaRestApi(
            self, "NotesApi",                       # Logical ID within CloudFormation
            handler=notes_lambda,                   # Default handler for routes if not overridden
            proxy=False,                            # Set to False because we define specific routes/methods below
            # Configure CORS (Cross-Origin Resource Sharing) to allow web browsers
            # from any origin to call this API. Restrict origins in production.
            default_cors_preflight_options=apigw.CorsOptions(
                allow_origins=apigw.Cors.ALL_ORIGINS,
                allow_methods=apigw.Cors.ALL_METHODS, # Allows GET, POST, PUT, DELETE, OPTIONS etc.
                allow_headers=apigw.Cors.DEFAULT_HEADERS + ["Content-Type", "X-Amz-Date", "Authorization", "X-Api-Key", "X-Amz-Security-Token"] # Standard + common headers
            )
        )

        # --- 5. Define API Resources and Methods ---
        # Create the base '/notes' resource path
        notes_resource = notes_api.root.add_resource("notes")

        # Add methods to the '/notes' resource:
        notes_resource.add_method("POST")   # POST /notes -> invokes notes_lambda
        notes_resource.add_method("GET")    # GET /notes -> invokes notes_lambda

        # Create the '/notes/{noteId}' resource path for individual notes
        # The {noteId} part indicates a path parameter.
        note_item_resource = notes_resource.add_resource("{noteId}")

        # Add methods to the '/notes/{noteId}' resource:
        note_item_resource.add_method("GET")    # GET /notes/{noteId} -> invokes notes_lambda
        note_item_resource.add_method("PUT")    # PUT /notes/{noteId} -> invokes notes_lambda
        note_item_resource.add_method("DELETE") # DELETE /notes/{noteId} -> invokes notes_lambda

        # --- 6. Output the API Gateway URL ---
        # This makes the deployed API endpoint URL easily accessible after deployment.
        CfnOutput(self, "ApiUrl",
                  value=notes_api.url,
                  description="The URL of the deployed API Gateway endpoint")

        # --- 7. Output the DynamoDB Table Name ---
        # Useful for reference or manual checks.
        CfnOutput(self, "TableName",
                  value=notes_table.table_name,
                  description="The name of the DynamoDB table")

# End of file: myserverlessproject/myserverlessproject_stack.py
# -----------------------------------------------------------------------------