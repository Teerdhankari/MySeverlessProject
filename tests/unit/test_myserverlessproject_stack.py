import aws_cdk as core
import aws_cdk.assertions as assertions

from myserverlessproject.myserverlessproject_stack import MyserverlessprojectStack

# example tests. To run these tests, uncomment this file along with the example
# resource in myserverlessproject/myserverlessproject_stack.py
def test_sqs_queue_created():
    app = core.App()
    stack = MyserverlessprojectStack(app, "myserverlessproject")
    template = assertions.Template.from_stack(stack)

#     template.has_resource_properties("AWS::SQS::Queue", {
#         "VisibilityTimeout": 300
#     })
