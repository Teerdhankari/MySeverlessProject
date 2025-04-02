# In tests/unit/test_myserverlessproject_stack.py
import aws_cdk as core
import aws_cdk.assertions as assertions

# Make sure the correct stack class is imported
from myserverlessproject.myserverlessproject_stack import MyserverlessprojectStack
import pytest # Import pytest if you need fixtures, etc.

# example tests. To run these tests, uncomment this file along with the example
# resource in myserverlessproject/myserverlessproject_stack.py
def test_dynamodb_table_created():
    app = core.App()
    # WHEN
    # If you specified env in app.py, you might need context here, but often not needed for basic unit tests
    stack = MyserverlessprojectStack(app, "myserverlessproject")
    # THEN
    template = assertions.Template.from_stack(stack)

    # Assert that a DynamoDB table resource exists
    template.resource_count_is("AWS::DynamoDB::Table", 1)

    # Assert specific properties of the DynamoDB table
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
        "BillingMode": "PAY_PER_REQUEST",
    })

    # Assert other core resources exist
    template.resource_count_is("AWS::Lambda::Function", 1)
    template.resource_count_is("AWS::ApiGateway::RestApi", 1)

    # --- CORRECTED ASSERTION ---
    # Now expect multiple roles due to pipeline, codebuild, lambda etc.
    # The exact number might vary slightly with CDK versions/constructs,
    # but 8 was reported in your error.
    template.resource_count_is("AWS::IAM::Role", 8) # <--- CHANGE 1 to 8

    # You can add more specific checks, e.g., for the pipeline itself
    template.resource_count_is("AWS::CodePipeline::Pipeline", 1)

# You can add more focused tests if needed