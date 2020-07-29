from aws_cdk import (
    core,
    aws_lambda as _lambda,
    aws_config as config,
    aws_events as events,
    aws_events_targets as targets,
    aws_stepfunctions as sfn,
    aws_stepfunctions_tasks as tasks,
    aws_dynamodb as dynamodb,
    aws_sns as sns,
    aws_sns_subscriptions as subscriptions,
    aws_apigateway as apigateway,
    aws_iam as iam,
    aws_s3_assets as assets
)
import os
from utils import get_string_code

class CdkworkshopStack(core.Stack):

    def __init__(self, scope: core.Construct, id: str, **kwargs) -> None:
        super().__init__(scope, id, **kwargs)
        function_path = os.getcwd() + '/lambda/'
        code = get_string_code(function_path + 'custom_config.py')
        _lambda.Function(self, 'NEW_customConfig',
            code=_lambda.Code.inline(code),
            runtime=_lambda.Runtime.PYTHON_3_7,
            handler='index.handler',
            timeout=core.Duration.seconds(30)
        )

        email_param = core.CfnParameter(self, 'email', description='email for sns subscription')
        
        # Dynamo Table
        table = dynamodb.Table(self, "auto-remediation",
            partition_key=dynamodb.Attribute(name="execution_arn", type=dynamodb.AttributeType.STRING)
        )
        #API Gateway for approval or reject the email
        email_approval = _lambda.Function(self, 'RespondEmailApproval',
            code=_lambda.Code.from_asset('lambda'),
            runtime=_lambda.Runtime.NODEJS_12_X,
            handler='lambda_approval.handler',
            timeout=core.Duration.seconds(30),
            environment={
                'DYNAMOTABLE' : table.table_name
            }
        )

        api = apigateway.RestApi(self, "Human approval endpoint")
        api_email_approval = apigateway.LambdaIntegration(email_approval)
        execution = api.root.add_resource("execution")
        execution.add_method("GET", api_email_approval)

        # SNS policy
        my_topic = sns.Topic(self, "capstoneTopic")
        my_topic.add_subscription(subscriptions.EmailSubscription(email_param.value_as_string))


        my_lambda = _lambda.Function(
            self, 'custom_config_ES',
            runtime=_lambda.Runtime.PYTHON_3_7,
            code=_lambda.Code.from_asset('lambda'),
            handler='custom_config.handler',
            timeout=core.Duration.seconds(30)
        )

        custom_rule = config.CustomRule(self, "Custom",
        configuration_changes=True,
        lambda_function=my_lambda
        )

        custom_rule.scope_to_resource("AWS::Elasticsearch::Domain")
        rule_detail = {
            "requestParameters": {
            "evaluations": {
                "complianceType": [
                "NON_COMPLIANT"
                ]
            }
          }
        }
        event_pattern = events.EventPattern(detail=rule_detail)


     # Start step functions
        send_email_approval = _lambda.Function(self, 'SendEmailApproval',
            code=_lambda.Code.from_asset('lambda'),
            runtime=_lambda.Runtime.NODEJS_12_X,
            handler='SendEmailApproval.handler',
            timeout=core.Duration.seconds(30),
            environment={
                'SNSTOPIC' : my_topic.topic_arn,
                'DYNAMOTABLE' : table.table_name,
                'APIURL': api.url
            }
        )
        my_topic.grant_publish(send_email_approval)

        check_status_dynamo = _lambda.Function(
            self, 'CheckStatus',
            runtime=_lambda.Runtime.PYTHON_3_7,
            code=_lambda.Code.from_asset('lambda'),
            handler='check_dynamo_status.handler',
            timeout=core.Duration.seconds(30),
            environment={
                'DYNAMOTABLE' : table.table_name
            }
        )
        restric_es_policy = _lambda.Function(
            self, 'RestricESpolicy',
            runtime=_lambda.Runtime.PYTHON_3_7,
            code=_lambda.Code.from_asset('lambda'),
            handler='restrict_es_policy.handler',
            timeout=core.Duration.seconds(30),
            environment={
                'DYNAMOTABLE' : table.table_name
            }
        )
        restric_es_policy.add_to_role_policy(iam.PolicyStatement(
                                                effect=iam.Effect.ALLOW,
                                                actions=["es:*"],
                                                resources=["*"]))

        submit_job = tasks.LambdaInvoke(self, "Submit Job",
            lambda_function=send_email_approval,
            payload=sfn.TaskInput.from_object({'ExecutionContext.$': '$$'}),
            result_path=sfn.JsonPath.DISCARD

            # Lambda's result is in the attribute `Payload`
        )

        wait_x = sfn.Wait(self, "Wait One Hour",
            time= sfn.WaitTime.duration(core.Duration.minutes(2))
        )

        get_status = tasks.LambdaInvoke(self, "Get Job Status",
            lambda_function=check_status_dynamo,
            payload=sfn.TaskInput.from_object({'ExecutionContext.$': '$$'}),
            result_path="$.status"
        )

        # job_failed = sfn.Fail(self, "Job Failed",
        #     cause="AWS Batch Job Failed",
        #     error="DescribeJob returned FAILED"
        # )

        final_task = tasks.LambdaInvoke(self, "Restric ES Policy",
            lambda_function=restric_es_policy,
            payload=sfn.TaskInput.from_object({'ExecutionContext.$': '$$'}),
        )
        definition = (submit_job.next(wait_x)
                                .next(get_status)
                                .next(sfn.Choice(self, "Job Complete?")
                                .when(sfn.Condition.string_equals("$.status.Payload.status", "Rejected!"), wait_x)
                                .when(sfn.Condition.string_equals("$.status.Payload.status", "started"), final_task)
                                .when(sfn.Condition.string_equals("$.status.Payload.status", "Accepted!"), final_task)))


        state_machine = sfn.StateMachine(self, "StateMachine",
            definition=definition,
            timeout=core.Duration.hours(2)
        )

        # Create an event when compliance change to trigger the step function
        custom_rule.on_compliance_change(id='ComplianceChange', 
                                        event_pattern=event_pattern,
                                        target=targets.SfnStateMachine(state_machine))

        table.grant_read_write_data(send_email_approval)
        table.grant_read_write_data(check_status_dynamo)
        table.grant_read_write_data(email_approval)
        table.grant_read_write_data(restric_es_policy)
