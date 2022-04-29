from aws_cdk import (
    Duration,
    Stack,
    aws_lambda,
    aws_config,
)
from constructs import Construct
from utils import paths


class ControlBrokerConsumerExampleConfigStack(Stack):

    def __init__(self, scope: Construct, construct_id: str, **kwargs) -> None:
        super().__init__(scope, construct_id, **kwargs)

        self.invoked_by_config = aws_lambda.Function(
            self,
            f"InvokedByConfig",
            code=aws_lambda.Code.from_asset(str(paths.LAMBDA_FUNCTIONS / 'invoked_by_config')),
            handler='lambda_function.lambda_handler',
            runtime=aws_lambda.Runtime.PYTHON_3_9,
            # environment=dict(
            #     ProcessingSfnArn=control_broker_statemachine.state_machine_arn
            # ),
        )
        # control_broker_statemachine.grant_start_execution(self.invoked_by_config)
        # control_broker_statemachine.grant_start_sync_execution(self.invoked_by_config)

        self.custom_config_rule = aws_config.CustomRule(
            self,
            "SQS-PoC",
            rule_scope=aws_config.RuleScope(
                resource_types = [
                    aws_config.ResourceType.SQS_QUEUE
                ]
            ),
            lambda_function=self.invoked_by_config,
            configuration_changes=True,
        )