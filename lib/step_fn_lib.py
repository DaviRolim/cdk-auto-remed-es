from aws_cdk.core import Construct, Duration

from aws_cdk import (
    aws_stepfunctions as sfn,
    aws_stepfunctions_tasks as tasks
)
from lib.lambda_lib import LambdaLib

class StepFunctionsLib(Construct):
    def __init__(self, scope: Construct, id: str, functions: LambdaLib, **kwargs) -> None:
        super().__init__(scope, id)

        # Step Function
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

        final_task = tasks.LambdaInvoke(self, "Restric ES Policy",
            lambda_function=functions.restric_es_policy,
            payload=sfn.TaskInput.from_object({'ExecutionContext.$': '$$'}),
        )
        definition = (submit_job.next(wait_x)
                                .next(get_status)
                                .next(sfn.Choice(self, "Job Complete?")
                                .when(sfn.Condition.string_equals("$.status.Payload.status", "Rejected!"), wait_x)
                                .when(sfn.Condition.string_equals("$.status.Payload.status", "NON_COMPLIANT"), final_task)
                                .when(sfn.Condition.string_equals("$.status.Payload.status", "Accepted!"), final_task)))


        self.state_machine = sfn.StateMachine(self, "StateMachine",
            definition=definition,
            timeout=Duration.hours(2)
        )