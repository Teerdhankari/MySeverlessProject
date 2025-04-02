# In tests/unit/test_myserverlessproject_stack.py

import aws_cdk as core
import aws_cdk.assertions as assertions

from myserverlessproject.myserverlessproject_stack import MyserverlessprojectStack

# example tests. To run these tests, uncomment this file along with the example
# resource in myserverlessproject/myserverlessproject_stack.py
def test_resources_created():
    app = core.App()
    stack = MyserverlessprojectStack(app, "myserverlessproject")
    template = assertions.Template.from_stack(stack)

    # --- Assertions for Key Resources ---

    # Assert DynamoDB Table exists with correct Partition Key
    template.has_resource_properties("AWS::DynamoDB::Table", {
        "KeySchema": [
            {
                "AttributeName": "itemID",
                "KeyType": "HASH"
            }
        ],
        "AttributeDefinitions": [
            {
                "AttributeName": "itemID",
                "AttributeType": "S"
            }
        ],
        "BillingMode": "PAY_PER_REQUEST"
    })

    # Assert Lambda Function exists with correct Runtime and Handler
    template.has_resource_properties("AWS::Lambda::Function", {
        "Handler": "api_handler.lambda_handler",
        "Runtime": "python3.11", # Make sure this matches your stack definition
        # Add check for Environment Variables if desired
        "Environment": assertions.Match.object_like({
            "Variables": {
                "DYNAMODB_TABLE_NAME": assertions.Match.any_value(), # Check key exists
                "LOG_LEVEL": "INFO"
            }
        })
    })

    # Assert Lambda Function has IAM Role
    template.has_resource_properties("AWS::Lambda::Function", {
        "Role": assertions.Match.any_value() # Basic check that a Role is assigned
    })

    # Assert API Gateway REST API exists
    template.has_resource("AWS::ApiGateway::RestApi", {})

    # Assert API Gateway Resources (/items, /items/{itemID}) exist
    template.has_resource("AWS::ApiGateway::Resource", {
        "PathPart": "items"
    })
    template.has_resource("AWS::ApiGateway::Resource", {
        "PathPart": "{itemID}"
    })

    # Assert API Gateway Methods (e.g., POST /items) exist
    template.has_resource("AWS::ApiGateway::Method", {
        "HttpMethod": "POST",
        "ResourceId": assertions.Match.any_value() # Could refine this check further if needed
    })
    template.has_resource("AWS::ApiGateway::Method", {
        "HttpMethod": "GET",
        "ResourceId": assertions.Match.any_value() # Check for GET on /items or /items/{itemID}
        # You can add more specific checks for other methods (PUT, DELETE)
    })

    # Assert CodePipeline exists
    template.has_resource("AWS::CodePipeline::Pipeline", {})

    # Assert CodeBuild Project exists
    template.has_resource("AWS::CodeBuild::Project", {})

# You can add more specific tests if needed, e.g., checking IAM policy actions
def test_lambda_permissions():
    app = core.App()
    stack = MyserverlessprojectStack(app, "myserverlessproject")
    template = assertions.Template.from_stack(stack)

    # Assert the Lambda's IAM Role has DynamoDB permissions
    template.has_resource_properties("AWS::IAM::Policy", {
        "PolicyDocument": {
            "Statement": assertions.Match.array_with([
                assertions.Match.object_like({
                    "Action": assertions.Match.array_with([
                        "dynamodb:BatchGetItem",
                        "dynamodb:GetItem",
                        "dynamodb:Scan",
                        "dynamodb:Query",
                        "dynamodb:BatchWriteItem",
                        "dynamodb:PutItem",
                        "dynamodb:UpdateItem",
                        "dynamodb:DeleteItem"
                    ]),
                    "Effect": "Allow",
                    "Resource": assertions.Match.any_value() # Check Action and Effect primarily
                })
            ])
        }
    })