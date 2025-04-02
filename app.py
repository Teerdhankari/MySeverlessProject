# In app.py (example)
import os
import aws_cdk as cdk
from myserverlessproject.myserverlessproject_stack import MyserverlessprojectStack

app = cdk.App()
MyserverlessprojectStack(app, "MyserverlessprojectStack",
    env=cdk.Environment(
        account=os.getenv('CDK_DEFAULT_ACCOUNT', '383014559627'), # Replace or use env vars
        region=os.getenv('CDK_DEFAULT_REGION', 'ap-south-1') # Replace or use env vars
    )
)
app.synth()