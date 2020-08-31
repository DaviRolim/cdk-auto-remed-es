from aws_cdk.core import NestedStack, Construct, CfnParameter, Duration

from aws_cdk import (
    aws_config as config,
    aws_events as events,
    aws_events_targets as targets,
    aws_iam as iam
)
from aws_cdk.aws_lambda import IFunction
from aws_cdk.aws_stepfunctions import IStateMachine
import constants

import os
class BaseStack(NestedStack):
    def __init__(self, scope: Construct, id: str, custom_function_es: IFunction, custom_function_rds: IFunction, state_machine: IStateMachine, **kwargs) -> None:
        super().__init__(scope, id, **kwargs)

        custom_rule_es = config.CustomRule(self, "Custom_es",
        configuration_changes=True,
        lambda_function=custom_function_es,
        config_rule_name=constants.CONFIG_RULE_ES_PUBLIC
        )
        custom_rule_es.scope_to_resource("AWS::Elasticsearch::Domain")

        custom_rule_rds = config.CustomRule(self, "Custom_rds",
        configuration_changes=True,
        lambda_function=custom_function_rds,
        config_rule_name=constants.CONFIG_RULE_RDS_PUBLIC
        )
        custom_rule_rds.scope_to_resource("AWS::RDS::DBInstance")

        rule_detail = {
            "requestParameters": {
            "evaluations": {
                "complianceType": [
                "NON_COMPLIANT"
                ],
                "complianceResourceType": ["AWS::Elasticsearch::Domain", "AWS::RDS::DBInstance"]
            }
          }
        }
        event_pattern = events.EventPattern(source=["aws.config"], detail=rule_detail)

        events.Rule(self, 'ComplianceCustomRule',
                    enabled=True,
                    event_pattern=event_pattern,
                    targets=[targets.SfnStateMachine(state_machine)])