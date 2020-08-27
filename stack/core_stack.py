from aws_cdk.core import NestedStack, Construct, CfnParameter, Duration

from aws_cdk import (
    aws_lambda as _lambda,
    aws_stepfunctions as sfn,
    aws_stepfunctions_tasks as tasks,
    aws_dynamodb as dynamodb,
    aws_sns as sns,
    aws_sns_subscriptions as subscriptions,
    aws_apigateway as apigateway,
    aws_iam as iam,
    aws_lambda_event_sources as event_source,
)
import os
from utils import get_code
from lib.lambda_lib import LambdaLib, LambdaProps
from lib.step_fn_lib import StepFunctionsLib

class CoreStack(NestedStack):
    def __init__(self, scope: Construct, id: str, email: str, **kwargs) -> None:
        super().__init__(scope, id, **kwargs)

        # Dynamo table
        self.table = dynamodb.Table(self, "auto-remediation",
            partition_key=dynamodb.Attribute(name="execution_arn", type=dynamodb.AttributeType.STRING),
            stream=dynamodb.StreamViewType.NEW_IMAGE
        )

        # SNS Topic
        self.my_topic = sns.Topic(self, "capstoneTopic")
        self.my_topic.add_subscription(subscriptions.EmailSubscription(email))

        # API Gateway
        self.api = apigateway.RestApi(self, "Human approval endpoint")

        # Lambda Functions
        lambda_props = LambdaProps(table=self.table, sns_topic=self.my_topic, api=self.api)
        self.functions = LambdaLib(self, 'functions', lambda_props)

        api_email_approval = apigateway.LambdaIntegration(self.functions.email_approval)
        execution = self.api.root.add_resource("execution")
        execution.add_method("GET", api_email_approval)
        
        # Step Functions
        self.step_fn = StepFunctionsLib(self, 'stepfn', self.functions)


        self.grant_permissions()
        '''
         Grants (????? TODO) the ideia is to put all grants into the same place 
         so I can quickly check if I have some permissions issues
        '''
    def grant_permissions(self):
        self.my_topic.grant_publish(self.functions.send_email_approval)
        self.table.grant_read_write_data(self.functions.send_email_approval)
        self.table.grant_read_write_data(self.functions.check_status_dynamo)
        self.table.grant_read_write_data(self.functions.email_approval)
        self.table.grant_read_write_data(self.functions.restric_es_policy)