from aws_cdk.core import Construct, Duration

from aws_cdk import (
    aws_lambda as _lambda,
    aws_iam as iam,
    aws_lambda_event_sources as event_source,
    aws_dynamodb as dynamo,
    aws_sns as sns,
    aws_apigateway as apigateway
)
import os
from utils import get_code

class LambdaProps:
    def __init__(self, table: dynamo.ITable, sns_topic: sns.ITopic, api=apigateway.IRestApi):
        self.table = table
        self.table_name = table.table_name
        self.sns_topic_arn = sns_topic.topic_arn
        self.api = api.url

class LambdaLib(Construct):
    def __init__(self, scope: Construct, id: str, props: LambdaProps, **kwargs) -> None:
        super().__init__(scope, id)

        common_runtimes = dict(
            runtime=_lambda.Runtime.PYTHON_3_7,
            handler='index.handler',
            timeout=Duration.seconds(30)
        )

        self.email_approval = _lambda.Function(self, 'RespondEmailApproval',
            code=_lambda.Code.inline(get_code('lambda_approval.js')),
            runtime=_lambda.Runtime.NODEJS_12_X,
            handler='index.handler',
            timeout=Duration.seconds(30),
            environment={
                'DYNAMOTABLE' : props.table_name
            }
        )
        self.send_email_approval = _lambda.Function(self, 'SendEmailApproval',
            code=_lambda.Code.inline(get_code('sendEmailApproval.js')),
            runtime=_lambda.Runtime.NODEJS_12_X,
            handler='index.handler',
            timeout=Duration.seconds(30),
            environment={
                'SNSTOPIC' : props.sns_topic_arn,
                'DYNAMOTABLE' : props.table_name,
                'APIURL': props.api
            }
        )

        self.my_lambda = _lambda.Function(
            self, 'custom_config_ES',
            code=_lambda.Code.inline(get_code('restrict_es_custom_config.py')),
            **common_runtimes
        )

        self.check_status_dynamo = _lambda.Function(
            self, 'CheckStatus',
            code=_lambda.Code.inline(get_code('check_dynamo_status.py')),
            **common_runtimes,
            environment={
                'DYNAMOTABLE' : props.table_name
            }
        )
        self.replicate_to_global = _lambda.Function(self, 'replicate_stream_global',
            code=_lambda.Code.from_inline(get_code('index.py')),
            **common_runtimes
        )
        self.stream_lambda_source(props.table, self.replicate_to_global)

        self.restric_es_policy = _lambda.Function(
            self, 'RestricESpolicy',
            **common_runtimes,
            code=_lambda.Code.inline(get_code('restrict_es_policy.py')),
            environment={
                'DYNAMOTABLE' : props.table_name
            }
        )

        self.restric_rds_policy = _lambda.Function(
            self, 'RestricRDS',
            **common_runtimes,
            code=_lambda.Code.inline(get_code('restrict_rds.py')),
            # environment={
            #     'DYNAMOTABLE' : props.table_name
            # }
        )

        self.custom_config_rds = _lambda.Function(
            self, 'custom_config_RDS',
            code=_lambda.Code.inline(get_code('public_rds_custom_config.py')),
            **common_runtimes
        )

        self.add_role_restric_es()
        self.add_role_restrict_rds()

        
    def stream_lambda_source(self, table: dynamo.ITable, function: _lambda.IFunction):
        dynamodb_stream_source = event_source.DynamoEventSource(table=table,
                                                                starting_position=_lambda.StartingPosition.LATEST,
                                                                batch_size=1,
                                                                retry_attempts=1)
        function.add_event_source(dynamodb_stream_source)

    
    def add_role_restric_es(self):
        self.restric_es_policy.add_to_role_policy(iam.PolicyStatement(
                                                effect=iam.Effect.ALLOW,
                                                actions=["es:*"],
                                                resources=["*"]))

    def add_role_restrict_rds(self):
        statement = iam.PolicyStatement(effect=iam.Effect.ALLOW,
                                        actions=["rds:*", "ec2:*"],
                                        resources=["*"])

        self.restric_rds_policy.add_to_role_policy(statement)

        self.custom_config_rds.add_to_role_policy(statement)