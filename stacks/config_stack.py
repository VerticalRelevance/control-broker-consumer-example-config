import json

from aws_cdk import (
    Duration,
    Stack,
    RemovalPolicy,
    aws_lambda,
    aws_config,
    aws_sqs,
    aws_iam,
    aws_stepfunctions,
    aws_logs,
)
from constructs import Construct
from utils import paths


class ControlBrokerConsumerExampleConfigStack(Stack):

    def __init__(self, scope: Construct, construct_id: str, **kwargs) -> None:
        super().__init__(scope, construct_id, **kwargs)
        
        self.invoked_by_config()
        self.demo_change_tracked_by_config()
    
    def demo_change_tracked_by_config(self):
        
        pass
    
        # toggle content-based deduplication to trigger change tracked by Config
        
        aws_sqs.Queue(
            self,
            "DemoChangeTrackedByConfig",
            fifo = True,
            # content_based_deduplication = True,
            content_based_deduplication = False,
        )
    
    
    def invoked_by_config(self):
        
        self.invoked_by_config = aws_lambda.Function(
            self,
            f"InvokedByConfig",
            code=aws_lambda.Code.from_asset(str(paths.LAMBDA_FUNCTIONS / 'invoked_by_config')),
            handler='lambda_function.lambda_handler',
            runtime=aws_lambda.Runtime.PYTHON_3_9,
            environment=dict(
                ProcessingSfnArn=self.sfn_config_event_processing.state_machine_arn
            ),
        )
        # control_broker_statemachine.grant_start_execution(self.invoked_by_config)
        # control_broker_statemachine.grant_start_sync_execution(self.invoked_by_config)

        self.custom_config_rule = aws_config.CustomRule(
            self,
            "SQS-PoC",
            rule_scope=aws_config.RuleScope.from_resources([
                aws_config.ResourceType.SQS_QUEUE,
            ]),
            lambda_function=self.invoked_by_config,
            configuration_changes=True,
        )

    def config_event_processing_sfn(self):
        
        log_group_inner_eval_engine_sfn = aws_logs.LogGroup(
            self,
            "ConfigEventProcessingSfnLogs",
            log_group_name=f"/aws/vendedlogs/states/ConfigEventProcessingSfnLogs",
            removal_policy=RemovalPolicy.DESTROY,
        )

        self.role_inner_eval_engine_sfn = aws_iam.Role(
            self,
            "ConfigEventProcessingSfn",
            assumed_by=aws_iam.ServicePrincipal("states.amazonaws.com"),
        )

        self.role_inner_eval_engine_sfn.add_to_policy(
            aws_iam.PolicyStatement(
                actions=[
                    # "logs:*",
                    "logs:CreateLogDelivery",
                    "logs:GetLogDelivery",
                    "logs:UpdateLogDelivery",
                    "logs:DeleteLogDelivery",
                    "logs:ListLogDeliveries",
                    "logs:PutResourcePolicy",
                    "logs:DescribeResourcePolicies",
                    "logs:DescribeLogGroups",
                ],
                resources=[
                    "*",
                    log_group_inner_eval_engine_sfn.log_group_arn,
                    f"{log_group_inner_eval_engine_sfn.log_group_arn}*",
                ],
            )
        )
        self.role_inner_eval_engine_sfn.add_to_policy(
            aws_iam.PolicyStatement(
                actions=["lambda:InvokeFunction"],
                resources=[
                    self.lambda_opa_eval_python_subprocess.function_arn,
                    self.lambda_gather_infractions.function_arn,
                    self.lambda_handle_infraction.function_arn,
                ],
            )
        )

        self.sfn_config_event_processing = aws_stepfunctions.CfnStateMachine(
            self,
            "ConfigEventProcessing",
            state_machine_type="STANDARD",
            # state_machine_type="EXPRESS",
            role_arn=self.role_inner_eval_engine_sfn.role_arn,
            logging_configuration=aws_stepfunctions.CfnStateMachine.LoggingConfigurationProperty(
                destinations=[
                    aws_stepfunctions.CfnStateMachine.LogDestinationProperty(
                        cloud_watch_logs_log_group=aws_stepfunctions.CfnStateMachine.CloudWatchLogsLogGroupProperty(
                            log_group_arn=log_group_inner_eval_engine_sfn.log_group_arn
                        )
                    )
                ],
                # include_execution_data=False,
                # level="ERROR",
                include_execution_data=True,
                level="ALL",
            ),
            definition_string=json.dumps(
                {
                    "StartAt": "ParseInput",
                    "States": {
                        "ParseInput": {
                            "Type": "Pass",
                            "End": True,
                            "ResultPath": "$",
                        },
                    },
                }
            ),
        )

        self.sfn_config_event_processing.node.add_dependency(self.role_inner_eval_engine_sfn)