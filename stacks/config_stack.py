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
    aws_lambda_python_alpha, #expirmental
)
from constructs import Construct
from utils import paths


class ControlBrokerConsumerExampleConfigStack(Stack):

    def __init__(self, scope: Construct, construct_id: str, **kwargs) -> None:
        super().__init__(scope, construct_id, **kwargs)
        
        self.demo_change_tracked_by_config()
        self.config_event_processing_sfn_lambdas():
        self.config_event_processing_sfn()
        self.invoked_by_config()
    
    def demo_change_tracked_by_config(self):
        
        pass
    
        # toggle content-based deduplication to trigger change tracked by Config
        
        aws_sqs.Queue(
            self,
            "DemoChangeTrackedByConfig",
            fifo = True,
            content_based_deduplication = True,
            # content_based_deduplication = False,
        )
    
    def config_event_processing_sfn_lambdas(self):

        # sign apigw request
        
        self.lambda_sign_apigw_request = aws_lambda_python_alpha.PythonFunction(
            self,
            "SignApigwRequestVAlpha",
            entry="./supplementary_files/lambdas/sign_apigw_request",
            runtime= aws_lambda.Runtime.PYTHON_3_9,
            index="lambda_function.py",
            handler="lambda_handler",
            timeout=Duration.seconds(60),
            memory_size=1024,
            environment = {
                "ApigwInvokeUrl" : self.control_broker_apigw_url
            },
            layers=[
                aws_lambda_python_alpha.PythonLayerVersion(
                    self,
                    "aws_requests_auth",
                    entry="./supplementary_files/lambda_layers/aws_requests_auth",
                    compatible_runtimes=[
                        aws_lambda.Runtime.PYTHON_3_9
                    ]
                ),
                aws_lambda_python_alpha.PythonLayerVersion(self,
                    "requests",
                    entry="./supplementary_files/lambda_layers/requests",
                    compatible_runtimes=[
                        aws_lambda.Runtime.PYTHON_3_9
                    ]
                ),
            ]
        )
        
        # object exists
        
        self.lambda_object_exists = aws_lambda.Function(
            self,
            "ObjectExists",
            runtime=aws_lambda.Runtime.PYTHON_3_9,
            handler="lambda_function.lambda_handler",
            timeout=Duration.seconds(60),
            memory_size=1024,
            code=aws_lambda.Code.from_asset(
                "./supplementary_files/lambdas/s3_head_object"
            ),
        )
        
        # s3 select
        
        self.lambda_s3_select = aws_lambda.Function(
            self,
            "S3Select",
            runtime=aws_lambda.Runtime.PYTHON_3_9,
            handler="lambda_function.lambda_handler",
            timeout=Duration.seconds(60),
            memory_size=1024,
            code=aws_lambda.Code.from_asset("./supplementary_files/lambdas/s3_select"),
        )

    def config_event_processing_sfn(self):
        
        log_group_config_event_processing_sfn = aws_logs.LogGroup(
            self,
            "ConfigEventProcessingSfnLogs",
            log_group_name=f"/aws/vendedlogs/states/ConfigEventProcessingSfnLogs",
            removal_policy=RemovalPolicy.DESTROY,
        )

        self.role_config_event_processing_sfn = aws_iam.Role(
            self,
            "ConfigEventProcessingSfn",
            assumed_by=aws_iam.ServicePrincipal("states.amazonaws.com"),
        )
        # self.role_config_event_processing_sfn.add_to_policy(
        #     aws_iam.PolicyStatement(
        #         actions=["lambda:InvokeFunction"],
        #         resources=[
        #             "*"
        #         ],
        #     )
        # )
        
        # log_group_config_event_processing_sfn.grant(self.role_config_event_processing_sfn)

        self.role_config_event_processing_sfn.add_to_policy(
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
                    log_group_config_event_processing_sfn.log_group_arn,
                    f"{log_group_config_event_processing_sfn.log_group_arn}*",
                ],
            )
        )

        self.sfn_config_event_processing = aws_stepfunctions.CfnStateMachine(
            self,
            "ConfigEventProcessing",
            state_machine_type="STANDARD",
            # state_machine_type="EXPRESS",
            role_arn=self.role_config_event_processing_sfn.role_arn,
            logging_configuration=aws_stepfunctions.CfnStateMachine.LoggingConfigurationProperty(
                destinations=[
                    aws_stepfunctions.CfnStateMachine.LogDestinationProperty(
                        cloud_watch_logs_log_group=aws_stepfunctions.CfnStateMachine.CloudWatchLogsLogGroupProperty(
                            log_group_arn=log_group_config_event_processing_sfn.log_group_arn
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

        self.sfn_config_event_processing.node.add_dependency(self.role_config_event_processing_sfn)
    
    def invoked_by_config(self):
        
        self.lambda_invoked_by_config = aws_lambda.Function(
            self,
            f"InvokedByConfig",
            code=aws_lambda.Code.from_asset(str(paths.LAMBDA_FUNCTIONS / 'invoked_by_config')),
            handler='lambda_function.lambda_handler',
            runtime=aws_lambda.Runtime.PYTHON_3_9,
            environment=dict(
                ConfigEventProcessingSfnArn=self.sfn_config_event_processing.attr_arn
            ),
        )
        
        self.lambda_invoked_by_config.role.add_to_policy(
            aws_iam.PolicyStatement(
                actions=[
                    "states:StartExecution",
                ],
                resources=[
                    self.sfn_config_event_processing.attr_arn,
                ],
            )
        )

        self.custom_config_rule = aws_config.CustomRule(
            self,
            "SQS-PoC",
            rule_scope=aws_config.RuleScope.from_resources([
                aws_config.ResourceType.SQS_QUEUE,
            ]),
            lambda_function=self.lambda_invoked_by_config,
            configuration_changes=True,
        )
