from aws_cdk.core import NestedStack, Construct, CfnParameter, Duration

from aws_cdk import (
    aws_config as config,
    aws_events as events,
    aws_events_targets as targets,
    aws_iam as iam
)
from aws_cdk.aws_lambda import IFunction
from aws_cdk.aws_stepfunctions import IStateMachine

import os
class BaseStack(NestedStack):
    def __init__(self, scope: Construct, id: str, custom_function: IFunction, state_machine: IStateMachine, **kwargs) -> None:
        super().__init__(scope, id, **kwargs)

        custom_rule = config.CustomRule(self, "Custom",
        configuration_changes=True,
        lambda_function=custom_function,
        config_rule_name='custom-elasticsearch-public-access-remediation'
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

        events.Rule(self, 'ComplianceESrule',
                    enabled=True,
                    event_pattern=event_pattern,
                    targets=[targets.SfnStateMachine(state_machine)])