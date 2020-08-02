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
    aws_s3_assets as assets,
    aws_lambda_event_sources as event_source,
    aws_lambda_python as alp,
    aws_s3 as s3,
    aws_s3_deployment as s3_deployment
)
import os
from utils import get_string_code

class CdkworkshopStack(core.Stack):

    def __init__(self, scope: core.Construct, id: str, **kwargs) -> None:
        super().__init__(scope, id, **kwargs)
        function_path = os.getcwd() + '/lambda/'
        code_custom_config = get_string_code(function_path + 'custom_config.py')
        code_lambda_approval = get_string_code(function_path + 'lambda_approval.js')
        code_restrict_es_policy = get_string_code(function_path + 'restrict_es_policy.py')
        code_send_email_approval = get_string_code(function_path + 'sendEmailApproval.js')
        code_check_dynamo_status = get_string_code(function_path + 'check_dynamo_status.py')

        email_param = core.CfnParameter(self, 'email', description='email for sns subscription')

        # Dynamo Table
        table = dynamodb.Table(self, "auto-remediation",
            partition_key=dynamodb.Attribute(name="execution_arn", type=dynamodb.AttributeType.STRING),
            stream=dynamodb.StreamViewType.NEW_IMAGE
        )
        #API Gateway for approval or reject the email
        email_approval = _lambda.Function(self, 'RespondEmailApproval',
            code=_lambda.Code.inline(code_lambda_approval),
            runtime=_lambda.Runtime.NODEJS_12_X,
            handler='index.handler',
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
            code=_lambda.Code.inline(code_custom_config),
            handler='index.handler',
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
                ],
                "complianceResourceType": ["AWS::Elasticsearch::Domain"]
            }
          }
        }
        event_pattern = events.EventPattern(source=["aws.config"], detail=rule_detail)
     # Start step functions
        send_email_approval = _lambda.Function(self, 'SendEmailApproval',
            code=_lambda.Code.inline(code_send_email_approval),
            runtime=_lambda.Runtime.NODEJS_12_X,
            handler='index.handler',
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
            code=_lambda.Code.inline(code_check_dynamo_status),
            handler='index.handler',
            timeout=core.Duration.seconds(30),
            environment={
                'DYNAMOTABLE' : table.table_name
            }
        )
        restric_es_policy = _lambda.Function(
            self, 'RestricESpolicy',
            runtime=_lambda.Runtime.PYTHON_3_7,
            code=_lambda.Code.inline(code_restrict_es_policy),
            handler='index.handler',
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
                                .when(sfn.Condition.string_equals("$.status.Payload.status", "NON_COMPLIANT"), final_task)
                                .when(sfn.Condition.string_equals("$.status.Payload.status", "Accepted!"), final_task)))


        state_machine = sfn.StateMachine(self, "StateMachine",
            definition=definition,
            timeout=core.Duration.hours(2)
        )

        # Create an event when compliance change to trigger the step function
        events.Rule(self, 'ComplianceESrule',
                    enabled=True,
                    event_pattern=event_pattern,
                    targets=[targets.SfnStateMachine(state_machine)])
        # custom_rule.on_compliance_change(id='ComplianceChange', 
        #                                 event_pattern=event_pattern,
        #                                 target=targets.SfnStateMachine(state_machine))

        # Replication to global table
        dynamodb_stream_source = event_source.DynamoEventSource(table=table,
                                                                starting_position=_lambda.StartingPosition.LATEST,
                                                                batch_size=1,
                                                                retry_attempts=1)
        


        # Grants dynamo table
        table.grant_read_write_data(send_email_approval)
        table.grant_read_write_data(check_status_dynamo)
        table.grant_read_write_data(email_approval)
        table.grant_read_write_data(restric_es_policy)

        # Bucket to put lambda bundle
        my_bucket = s3.Bucket.from_bucket_attributes(self, 'mybucket', bucket_arn='arn:aws:s3:::lambdarepocapstone-sa')

        replicate_to_global = _lambda.Function(self, 'replicate_stream_global',
            code=_lambda.Code.from_bucket(my_bucket, 'aurora_conn_bundle.zip'),
            runtime=_lambda.Runtime.PYTHON_3_7,
            handler='replicate_to_global_table.handler',
            timeout=core.Duration.seconds(30)
            # environment={
            #     'ROLE_ARN' : cross_access_role_arn
            # }
        )
        replicate_to_global.add_event_source(dynamodb_stream_source)
