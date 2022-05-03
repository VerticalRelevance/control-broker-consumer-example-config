import json
from typing import List

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
    aws_s3,
    aws_lambda_python_alpha, #expirmental
)
from constructs import Construct
from utils import paths


class ControlBrokerConsumerExampleConfigStack(Stack):

    def __init__(self,
        scope: Construct,
        construct_id: str,
        control_broker_apigw_url:str,
        control_broker_input_reader_arns:List[str],
        **kwargs) -> None:
        super().__init__(scope, construct_id, **kwargs)
        
        self.control_broker_apigw_url = control_broker_apigw_url
        self.control_broker_input_reader_arns = control_broker_input_reader_arns
        
        self.demo_change_tracked_by_config()
        self.utils()
        self.config_event_processing_sfn_lambdas()
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
    
    def utils(self):
        
        self.bucket_config_event_payloads = aws_s3.Bucket(
            self,
            "ConfigEventPayloads",
            block_public_access=aws_s3.BlockPublicAccess.BLOCK_ALL,
            removal_policy=RemovalPolicy.DESTROY,
            auto_delete_objects=True,
        )
        
        # Give read permission to the control broker on the templates we store
        # and pass to the control broker
        for control_broker_principal_arn in self.control_broker_input_reader_arns:
            self.bucket_config_event_payloads.grant_read(
                aws_iam.ArnPrincipal(control_broker_principal_arn)
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
                "ApigwInvokeUrl" : self.control_broker_apigw_url,
                "ConfigEventPayloadsBucket": self.bucket_config_event_payloads.bucket_name
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
        
        # put evaluations
        
        self.lambda_put_evaluations = aws_lambda.Function(
            self,
            "PutEvaluations",
            runtime=aws_lambda.Runtime.PYTHON_3_9,
            handler="lambda_function.lambda_handler",
            timeout=Duration.seconds(60),
            memory_size=1024,
            code=aws_lambda.Code.from_asset("./supplementary_files/lambdas/put_evaluations"),
        )
        
         self.lambda_put_evaluations.role.add_to_policy(
            aws_iam.PolicyStatement(
                actions=[
                    "config:PutEvaluations",
                ],
                resources=["*"]
            )
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
        self.role_config_event_processing_sfn.add_to_policy(
            aws_iam.PolicyStatement(
                actions=["lambda:InvokeFunction"],
                resources=[
                    self.lambda_sign_apigw_request.function_arn,
                    self.lambda_object_exists.function_arn,
                    self.lambda_s3_select.function_arn,
                ],
            )
        )
        
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
            definition_string=json.dumps({
                "StartAt": "SignApigwRequest",
                "States": {
                    "SignApigwRequest": {
                        "Type": "Task",
                        "Next": "CheckResultsReportExists",
                        "ResultPath": "$.SignApigwRequest",
                        "Resource": "arn:aws:states:::lambda:invoke",
                        "Parameters": {
                            "FunctionName": self.lambda_sign_apigw_request.function_name,
                            "Payload.$": "$"
                        },
                        "ResultSelector": {
                            "Payload.$": "$.Payload"
                        },
                    },
                    "CheckResultsReportExists": {
                        "Type": "Task",
                        "Next": "GetResultsReportIsCompliantBoolean",
                        "ResultPath": "$.CheckResultsReportExists",
                        "Resource": "arn:aws:states:::lambda:invoke",
                        "Parameters": {
                            "FunctionName": self.lambda_object_exists.function_name,
                            "Payload": {
                                "S3Uri.$":"$.SignApigwRequest.Payload.ControlBrokerRequestStatus.ResultsReportS3Uri"
                            }
                        },
                        "ResultSelector": {
                            "Payload.$": "$.Payload"
                        },
                        "Retry": [
                            {
                                "ErrorEquals": [
                                    "ObjectDoesNotExistException"
                                ],
                                "IntervalSeconds": 1,
                                "MaxAttempts": 6,
                                "BackoffRate": 2.0
                            }
                        ],
                        "Catch": [
                            {
                                "ErrorEquals":[
                                    "States.ALL"
                                ],
                                "Next": "ResultsReportDoesNotYetExist"
                            }
                        ]
                    },
                    "ResultsReportDoesNotYetExist": {
                        "Type":"Fail"
                    },
                    "GetResultsReportIsCompliantBoolean": {
                        "Type": "Task",
                        "Next": "ChoiceIsComplaint",
                        "ResultPath": "$.GetResultsReportIsCompliantBoolean",
                        "Resource": "arn:aws:states:::lambda:invoke",
                        "Parameters": {
                            "FunctionName": self.lambda_s3_select.function_name,
                            "Payload": {
                                "S3Uri.$":"$.SignApigwRequest.Payload.ControlBrokerRequestStatus.ResultsReportS3Uri",
                                "Expression": "SELECT * from S3Object s",
                            },
                        },
                        "ResultSelector": {"S3SelectResult.$": "$.Payload.Selected"},
                    },
                    "ChoiceIsComplaint": {
                        "Type":"Choice",
                        "Default":"PutEvaluationsNonCompliant",
                        "Choices":[
                            {
                                "Variable":"$.GetResultsReportIsCompliantBoolean.S3SelectResult.ControlBrokerResultsReport.Evaluation.IsCompliant",
                                "BooleanEquals":True,
                                "Next":"PutEvaluationsCompliant"
                            }
                        ]
                    },
                    "PutEvaluationsCompliant": {
                        "Type": "Task",
                        "Next": "Compliant",
                        "ResultPath": "$.PutEvaluationsCompliant",
                        "Resource": "arn:aws:states:::lambda:invoke",
                        "Parameters": {
                            "FunctionName": self.lambda_put_evaluations.function_name,
                            "Payload": {
                                "Compliance": True
                                "ConfigResultToken.$":"$.ControlBrokerConsumerInputs.ConsumerMetadata.ConfigResultToken",
                                "ResourceType.$":"$.ControlBrokerConsumerInputs.ConsumerMetadata.ResourceType",
                                "ResourceId.$":"$.ControlBrokerConsumerInputs.ConsumerMetadata.ResourceId",
                            },
                        },
                    },
                    "PutEvaluationsNonCompliant": {
                        "Type": "Task",
                        "Next": "Compliant",
                        "ResultPath": "$.PutEvaluationsCompliant",
                        "Resource": "arn:aws:states:::lambda:invoke",
                        "Parameters": {
                            "FunctionName": self.lambda_put_evaluations.function_name,
                            "Payload": {
                                "Compliance": False
                                "ConfigResultToken.$":"$.ControlBrokerConsumerInputs.ConsumerMetadata.ConfigResultToken",
                                "ResourceType.$":"$.ControlBrokerConsumerInputs.ConsumerMetadata.ResourceType",
                                "ResourceId.$":"$.ControlBrokerConsumerInputs.ConsumerMetadata.ResourceId",
                            },
                        },
                    },
                    "Compliant": {
                        "Type":"Succeed"
                    }
                    "NonCompliant": {
                        "Type":"Fail"
                    }
                }
            }),
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
                ConfigEventProcessingSfnArn=self.sfn_config_event_processing.attr_arn,
                ConfigEventPayloadsBucket=self.bucket_config_event_payloads.bucket_name,
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
        self.lambda_invoked_by_config.role.add_to_policy(
            aws_iam.PolicyStatement(
                actions=[
                    "s3:PutObject",
                ],
                resources=[
                    self.bucket_config_event_payloads.arn_for_objects("*"),
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
