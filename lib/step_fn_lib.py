from aws_cdk.core import Construct, Duration

from aws_cdk import (
    aws_stepfunctions as sfn,
    aws_stepfunctions_tasks as tasks
)
from lib.lambda_lib import LambdaLib

import constants

class StepFunctionsLib(Construct):
    def __init__(self, scope: Construct, id: str, functions: LambdaLib, **kwargs) -> None:
        super().__init__(scope, id)

        # Step Function
        send_to_sechub = tasks.LambdaInvoke(self, "Sechub Findings",
            lambda_function=functions.sechub_custom_new,
            # payload=sfn.TaskInput.from_object({'ExecutionContext.$': '$$'}),
            result_path=sfn.JsonPath.DISCARD
        )

        resolved_sechub = tasks.LambdaInvoke(self, "Sechub Resolved Status",
            lambda_function=functions.sechub_custom_solved,
            # payload=sfn.TaskInput.from_object({'ExecutionContext.$': '$$'}),
            result_path=sfn.JsonPath.DISCARD
        )

        submit_job = tasks.LambdaInvoke(self, "Submit Job",
            lambda_function=functions.send_email_approval,
            payload=sfn.TaskInput.from_object({'ExecutionContext.$': '$$'}),
            result_path=sfn.JsonPath.DISCARD
        )

        wait_x = sfn.Wait(self, "Wait",
            time= sfn.WaitTime.duration(Duration.minutes(2))
        )

        get_status = tasks.LambdaInvoke(self, "Get Job Status",
            lambda_function=functions.check_status_dynamo,
            payload=sfn.TaskInput.from_object({'ExecutionContext.$': '$$'}),
            result_path="$.status"
        )

        restrict_es = tasks.LambdaInvoke(self, "Restric ES Policy",
            lambda_function=functions.restric_es_policy,
            payload=sfn.TaskInput.from_object({'ExecutionContext.$': '$$'}),
            result_path=sfn.JsonPath.DISCARD
        )

        restrict_rds = tasks.LambdaInvoke(self, "Restric RDS",
            lambda_function=functions.restric_rds_policy,
            payload=sfn.TaskInput.from_object({'ExecutionContext.$': '$$'}),
            result_path=sfn.JsonPath.DISCARD
        )

        restrict_es_condition = sfn.Condition.string_equals("$.detail.additionalEventData.configRuleName", constants.CONFIG_RULE_ES_PUBLIC)
        restrict_rds_condition = sfn.Condition.string_equals("$.detail.additionalEventData.configRuleName", constants.CONFIG_RULE_RDS_PUBLIC)

        definition = (send_to_sechub.next(submit_job)
                                .next(wait_x)
                                .next(get_status)
                                .next(sfn.Choice(self, "Job Complete?")
                                .when(sfn.Condition.string_equals("$.status.Payload.status", "Rejected!"), wait_x)
                                # .when(sfn.Condition.string_equals("$.status.Payload.status", "NON_COMPLIANT"), final_task)
                                # .when(sfn.Condition.string_equals("$.status.Payload.status", "Accepted!"), final_task))
                                .otherwise(sfn.Choice(self, "Remediation Choice")
                                .when(restrict_es_condition, restrict_es)
                                .when(restrict_rds_condition, restrict_rds).afterwards().next(resolved_sechub)))
                                )


        self.state_machine = sfn.StateMachine(self, "StateMachine",
            definition=definition,
            timeout=Duration.hours(2)
        )