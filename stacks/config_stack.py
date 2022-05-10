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
    aws_events_targets,
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
        
        self.layers = {
            'requests': aws_lambda_python_alpha.PythonLayerVersion(self,
                    "requests",
                    entry="./supplementary_files/lambda_layers/requests",
                    compatible_runtimes=[
                        aws_lambda.Runtime.PYTHON_3_9
                    ]
                ),
            'aws_requests_auth':aws_lambda_python_alpha.PythonLayerVersion(
                    self,
                    "aws_requests_auth",
                    entry="./supplementary_files/lambda_layers/aws_requests_auth",
                    compatible_runtimes=[
                        aws_lambda.Runtime.PYTHON_3_9
                    ]
                ),
        }
        
        self.demo_change_tracked_by_config()
        self.utils()
        self.config_event_processing_sfn_lambdas()
        self.config_event_processing_sfn()
        self.invoked_by_config()
    
    def demo_change_tracked_by_config(self):
        
        # toggle content-based deduplication to trigger change tracked by Config
        
        toggled_boolean_path='./dev/tracked_by_config/toggled_boolean.json'
        
        # DEV: ToggledBoolean alternates upon every deploy
        with open(toggled_boolean_path,'r') as f:
            toggled_boolean = json.loads(f.read())['ToggledBoolean']
        
        aws_sqs.Queue(
            self,
            "TrackedByConfig01",
            fifo = True,
            # content_based_deduplication = True,
            # content_based_deduplication = False,
            content_based_deduplication = toggled_boolean,
        )
        
        aws_sqs.Queue(
            self,
            "TrackedByConfig02",
            fifo = True,
            # content_based_deduplication = True,
            # content_based_deduplication = False,
            content_based_deduplication = not toggled_boolean,
        )
        
        # DEV: ToggledBoolean alternates upon every deploy
        with open(toggled_boolean_path,'w') as f:
            json.dump({'ToggledBoolean':not toggled_boolean},f)
        
    def utils(self):
        
        self.bucket_config_event_raw_inputs = aws_s3.Bucket(
            self,
            "ConfigEventsRawInput",
            block_public_access=aws_s3.BlockPublicAccess.BLOCK_ALL,
            removal_policy=RemovalPolicy.DESTROY,
            auto_delete_objects=True,
        )
        
        # Give read permission to the control broker on the Consumer Inputs we store
        # and pass to the control broker
        for control_broker_principal_arn in self.control_broker_input_reader_arns:
            self.bucket_config_event_raw_inputs.grant_read(
                aws_iam.ArnPrincipal(control_broker_principal_arn)
            )
    
    def config_event_processing_sfn_lambdas(self):

        # sign apigw request
        
        self.lambda_sign_apigw_request = aws_lambda.Function(
            self,
            "SignApigwRequest",
            runtime=aws_lambda.Runtime.PYTHON_3_9,
            handler="lambda_function.lambda_handler",
            timeout=Duration.seconds(60),
            memory_size=1024,
            code=aws_lambda.Code.from_asset(
                "./supplementary_files/lambdas/sign_apigw_request"
            ),
            environment=dict(
                ControlBrokerInvokeUrl=self.control_broker_apigw_url,
                ConfigEventsRawInputBucket=self.bucket_config_event_raw_inputs.bucket_name,
            ),
            layers = [
                self.layers['requests'],
                self.layers['aws_requests_auth'],
            ]
        )

        self.lambda_sign_apigw_request.role.add_to_policy(
            aws_iam.PolicyStatement(
                actions=[
                    "s3:PutObject",
                ],
                resources=[
                    self.bucket_config_event_raw_inputs.bucket_arn,
                    self.bucket_config_event_raw_inputs.arn_for_objects("*"),
                ],
            )
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
        
        # get config compliance
        
        self.lambda_get_resource_config_compliance = aws_lambda.Function(
            self,
            "GetResourceConfigCompliance",
            runtime=aws_lambda.Runtime.PYTHON_3_9,
            handler="lambda_function.lambda_handler",
            timeout=Duration.seconds(60),
            memory_size=1024,
            code=aws_lambda.Code.from_asset("./supplementary_files/lambdas/get_resource_config_compliance"),
        )
        
        self.lambda_get_resource_config_compliance.role.add_to_policy(
            aws_iam.PolicyStatement(
                actions=[
                    "config:GetComplianceDetailsByResource",
                    "config:GetComplianceDetailsByConfigRule",
                    "config:GetComplianceDetailsBy*",
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
                    self.lambda_object_exists.function_arn,
                    self.lambda_s3_select.function_arn,
                    self.lambda_put_evaluations.function_arn,
                    self.lambda_get_resource_config_compliance.function_arn,
                    self.lambda_sign_apigw_request.function_arn,
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
        
        """
        TODO: handle first run where lambda_get_resource_config_compliance returns None
        
        when no Compliance details yet available
        
        perhaps comparison to initial is not required,
        simply assert that final Compliance status is equal to expected_final_status
        
        """

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
                "StartAt": "ParseInput",
                "States": {
                    "ParseInput": {
                        "Type":"Pass",
                        "Next":"SignApigwRequest",
                        "Parameters": {
                            "InvokingEvent.$":"States.StringToJson($.invokingEvent)",
                            "ConfigEvent.$":"$"
                        }
                    },
                    "SignApigwRequest": {
                        "Type": "Task",
                        "Next":"GetResourceConfigComplianceInitial",
                        "ResultPath": "$.SignApigwRequest",
                        "Resource": "arn:aws:states:::lambda:invoke",
                        "Parameters": {
                            "FunctionName": self.lambda_sign_apigw_request.function_name,
                            "Payload.$": "$.ConfigEvent"
                        },
                        "ResultSelector": {"Payload.$": "$.Payload"},
                    },
                    "GetResourceConfigComplianceInitial":{
                        "Type": "Task",
                        "Next":"CheckResultsReportExists", 
                        "ResultPath": "$.GetResourceConfigComplianceInitial",
                        "Resource": "arn:aws:states:::lambda:invoke",
                        "Parameters": {
                            "FunctionName": self.lambda_get_resource_config_compliance.function_name,
                            "Payload": {
                                "ConfigEvent.$":"$.ConfigEvent",
                                "ExpectedFinalStatusIsCompliant": None
                            }
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
                                "Bucket.$":"$.SignApigwRequest.Payload.Request.Content.Input.Bucket",
                                "Key.$":"$.SignApigwRequest.Payload.Request.Content.Input.Key"
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
                        "Type":"Succeed"
                    },
                }
            })
        )
        #             "GetResultsReportIsCompliantBoolean": {
        #                 "Type": "Task",
        #                 "Next": "ChoiceIsComplaint",
        #                 "ResultPath": "$.GetResultsReportIsCompliantBoolean",
        #                 "Resource": "arn:aws:states:::lambda:invoke",
        #                 "Parameters": {
        #                     "FunctionName": self.lambda_s3_select.function_name,
        #                     "Payload": {
        #                         "S3Uri.$":"$.SignApigwRequest.Payload.ControlBrokerRequestStatus.ResultsReportS3Uri",
        #                         "Expression": "SELECT * from S3Object s",
        #                     },
        #                 },
        #                 "ResultSelector": {"S3SelectResult.$": "$.Payload.Selected"},
        #             },
        #             "ChoiceIsComplaint": {
        #                 "Type":"Choice",
        #                 # "Default":"PutEvaluationsNonCompliant",
        #                 "Choices":[
        #                     {
        #                         "Variable":"$.GetResultsReportIsCompliantBoolean.S3SelectResult.ControlBrokerResultsReport.Evaluation.IsCompliant",
        #                         "BooleanEquals":True,
        #                         "Next":"PutEvaluationsCompliant"
        #                     },
        #                     {
        #                         "Variable":"$.GetResultsReportIsCompliantBoolean.S3SelectResult.ControlBrokerResultsReport.Evaluation.IsCompliant",
        #                         "BooleanEquals":False,
        #                         "Next":"PutEvaluationsNonCompliant"
        #                     }
        #                 ]
        #             },
        #             "PutEvaluationsCompliant": {
        #                 "Type": "Task",
        #                 "Next": "ChoiceNowGood",
        #                 "ResultPath": "$.PutEvaluationsCompliant",
        #                 "Resource": "arn:aws:states:::lambda:invoke",
        #                 "Parameters": {
        #                     "FunctionName": self.lambda_put_evaluations.function_name,
        #                     "Payload": {
        #                         "Compliance": True,
        #                         "ConfigResultToken.$":"$.ControlBrokerConsumerInputs.ConsumerMetadata.ConfigResultToken",
        #                         "ResourceType.$":"$.ControlBrokerConsumerInputs.ConsumerMetadata.ResourceType",
        #                         "ResourceId.$":"$.ControlBrokerConsumerInputs.ConsumerMetadata.ResourceId",
        #                     },
        #                 },
        #                 "ResultSelector": {"Payload.$": "$.Payload"},
        #             },
        #             "ChoiceNowGood": {
        #                 "Type":"Choice",
        #                 # "Default":"WasBadNowGood",
        #                 "Choices":[
        #                     {
        #                         "Variable":"$.GetResourceConfigComplianceInitial.Payload.ResourceConfigIsCompliant",
        #                         "BooleanEquals": True,
        #                         "Next":"WasGoodStillGood"
        #                     },
        #                     {
        #                         "Variable":"$.GetResourceConfigComplianceInitial.Payload.ResourceConfigIsCompliant",
        #                         "BooleanEquals": False,
        #                         "Next":"WasBadNowGood"
        #                     }
        #                 ]
        #             },
        #             "WasGoodStillGood": {
        #                 "Type":"Pass",
        #                 "Next":"Compliant",
        #             },
        #             "WasBadNowGood": {
        #                 "Type":"Pass",
        #                 "Next":"ConfirmBadToGood",
        #             },
        #             "ConfirmBadToGood":{
        #                 "Type": "Task",
        #                 "Next": "Compliant",
        #                 "ResultPath": "$.GetResourceConfigComplianceInitial",
        #                 "Resource": "arn:aws:states:::lambda:invoke",
        #                 "Parameters": {
        #                     "FunctionName": self.lambda_get_resource_config_compliance.function_name,
        #                     "Payload": {
        #                         "ConsumerMetadata.$":"$.ControlBrokerConsumerInputs.ConsumerMetadata",
        #                         "ExpectedFinalStatusIsCompliant": True

        #                     }
        #                 },
        #                 "ResultSelector": {
        #                     "Payload.$": "$.Payload"
        #                 },
        #                 "Retry": [
        #                     {
        #                         "ErrorEquals": [
        #                             "ConfigComplianceStatusIsNotAsExpectedException"
        #                         ],
        #                         "IntervalSeconds": 1,
        #                         "MaxAttempts": 8,
        #                         "BackoffRate": 2.0
        #                     }
        #                 ],
        #                 "Catch": [
        #                     {
        #                         "ErrorEquals":[
        #                             "States.ALL"
        #                         ],
        #                         "Next": "CannotConfirmBadToGood"
        #                     }
        #                 ]
        #             },
        #             "CannotConfirmBadToGood": {
        #                 "Type":"Fail"
        #             },
        #             "PutEvaluationsNonCompliant": {
        #                 "Type": "Task",
        #                 "Next": "ChoiceNowBad",
        #                 "ResultPath": "$.PutEvaluationsCompliant",
        #                 "Resource": "arn:aws:states:::lambda:invoke",
        #                 "Parameters": {
        #                     "FunctionName": self.lambda_put_evaluations.function_name,
        #                     "Payload": {
        #                         "Compliance": False,
        #                         "ConfigResultToken.$":"$.ControlBrokerConsumerInputs.ConsumerMetadata.ConfigResultToken",
        #                         "ResourceType.$":"$.ControlBrokerConsumerInputs.ConsumerMetadata.ResourceType",
        #                         "ResourceId.$":"$.ControlBrokerConsumerInputs.ConsumerMetadata.ResourceId",
        #                     },
        #                 },
        #                 "ResultSelector": {"Payload.$": "$.Payload"},
        #             },
        #             "ChoiceNowBad": {
        #                 "Type":"Choice",
        #                 # "Default":"WasGoodNowBad",
        #                 "Choices":[
        #                     {
        #                         "Variable":"$.GetResourceConfigComplianceInitial.Payload.ResourceConfigIsCompliant",
        #                         "BooleanEquals":False,
        #                         "Next":"WasBadStillBad"
        #                     },
        #                     {
        #                         "Variable":"$.GetResourceConfigComplianceInitial.Payload.ResourceConfigIsCompliant",
        #                         "BooleanEquals":True,
        #                         "Next":"WasGoodNowBad"
        #                     }
        #                 ]
        #             },
        #             "WasBadStillBad": {
        #                 "Type":"Pass",
        #                 "Next":"NonCompliant",
        #             },
        #             "WasGoodNowBad": {
        #                 "Type":"Pass",
        #                 "Next":"ConfirmGoodToBad",
        #             },
        #             "ConfirmGoodToBad":{
        #                 "Type": "Task",
        #                 "Next": "NonCompliant",
        #                 "ResultPath": "$.GetResourceConfigComplianceInitial",
        #                 "Resource": "arn:aws:states:::lambda:invoke",
        #                 "Parameters": {
        #                     "FunctionName": self.lambda_get_resource_config_compliance.function_name,
        #                     "Payload": {
        #                         "ConsumerMetadata.$":"$.ControlBrokerConsumerInputs.ConsumerMetadata",
        #                         "ExpectedFinalStatusIsCompliant": False
        #                     }
        #                 },
        #                 "ResultSelector": {
        #                     "Payload.$": "$.Payload"
        #                 },
        #                 "Retry": [
        #                     {
        #                         "ErrorEquals": [
        #                             "ConfigComplianceStatusIsNotAsExpectedException"
        #                         ],
        #                         "IntervalSeconds": 1,
        #                         "MaxAttempts": 8,
        #                         "BackoffRate": 2.0
        #                     }
        #                 ],
        #                 "Catch": [
        #                     {
        #                         "ErrorEquals":[
        #                             "States.ALL"
        #                         ],
        #                         "Next": "CannotConfirmGoodToBad"
        #                     }
        #                 ]
        #             },
        #             "CannotConfirmGoodToBad": {
        #                 "Type":"Fail"
        #             },
        #             "Compliant": {
        #                 "Type":"Succeed"
        #             },
        #             "NonCompliant": {
        #                 "Type":"Succeed"
        #             }
        #         }
        #     }),
        # )

        self.sfn_config_event_processing.node.add_dependency(self.role_config_event_processing_sfn)
    
    def invoked_by_config(self):
        
        self.lambda_invoked_by_config = aws_lambda.Function(
            self,
            f"InvokedByConfig",
            code=aws_lambda.Code.from_asset(str(paths.LAMBDA_FUNCTIONS / 'invoked_by_config')),
            handler='lambda_function.lambda_handler',
            runtime=aws_lambda.Runtime.PYTHON_3_9,
            timeout=Duration.seconds(60),
            memory_size=1024,
            environment={
                
                "ConfigEventProcessingSfnArn": self.sfn_config_event_processing.attr_arn
            },
            layers=[
                self.layers['requests'],
                self.layers['aws_requests_auth']
            ]
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
        

        self.custom_config_rule_sqs_poc = aws_config.CustomRule(
            self,
            "SQS-PoC",
            rule_scope=aws_config.RuleScope.from_resources([
                aws_config.ResourceType.SQS_QUEUE,
            ]),
            lambda_function=self.lambda_invoked_by_config,
            configuration_changes=True,
        )

        log_group_config_compliance = aws_logs.LogGroup(
            self,
            "ConfigCompliance",
            # log_group_name=f"/aws/vendedlogs/states/ConfigEventProcessingSfnLogs",
            removal_policy=RemovalPolicy.DESTROY,
        )

        self.custom_config_rule_sqs_poc.on_compliance_change(
            "Log",
            target = aws_events_targets.CloudWatchLogGroup(log_group_config_compliance)
        )