#!/usr/bin/env python3
from aws_cdk.core import App, Stack, CfnParameter
from stack.base_stack import BaseStack
from stack.core_stack import CoreStack

app = App()

main_stack = Stack(app, 'Main')

email_param = CfnParameter(main_stack, 'email', description='email for sns subscription').value_as_string
app_stack = CoreStack(main_stack, 'AppStack', email=email_param)
base_stack = BaseStack(main_stack, 'BaseStack', app_stack.functions.my_lambda, app_stack.step_fn.state_machine)

#CdkworkshopStack(app, "projetox", env={'region': 'sa-east-1', 'account': os.environ['CDK_DEFAULT_ACCOUNT']})

app.synth()
