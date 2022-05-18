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
        **kwargs) -> None:
        super().__init__(scope, construct_id, **kwargs)
        
        self.control_broker_apigw_url = control_broker_apigw_url
        
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

        # get object
        
        self.lambda_get_object = aws_lambda.Function(
            self,
            "GetObject",
            runtime=aws_lambda.Runtime.PYTHON_3_9,
            handler="lambda_function.lambda_handler",
            timeout=Duration.seconds(60),
            memory_size=1024,
            code=aws_lambda.Code.from_asset(
                "./supplementary_files/lambdas/get_object"
            ),
        )
        
        # s3 select
        
        # self.lambda_s3_select = aws_lambda.Function(
        #     self,
        #     "S3Select",
        #     runtime=aws_lambda.Runtime.PYTHON_3_9,
        #     handler="lambda_function.lambda_handler",
        #     timeout=Duration.seconds(60),
        #     memory_size=1024,
        #     code=aws_lambda.Code.from_asset(
        #         "./supplementary_files/lambdas/s3_select"
        #     ),
        # )
       
        # self.lambda_s3_select.role.add_to_policy(
        #     aws_iam.PolicyStatement(
        #         actions=[
        #             "s3:GetObject",
        #             "s3:GetBucket",
        #             "s3:List*",
        #         ],
        #         resources=[
        #             self.bucket_config_event_raw_inputs.bucket_arn,
        #             self.bucket_config_event_raw_inputs.arn_for_objects("*"),
        #         ],
        #     )
        # )
       
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
                    self.lambda_get_object.function_arn,
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
                        "Next":"GetResultsReportIsCompliantBoolean", 
                        "ResultPath": "$.GetResourceConfigComplianceInitial",
                        "Resource": "arn:aws:states:::lambda:invoke",
                        "Parameters": {
                            "FunctionName": self.lambda_get_resource_config_compliance.function_name,
                            "Payload": {
                                "ConfigEvent.$":"$.ConfigEvent",
                                "ExpectedComplianceStatus": None
                            }
                        },
                        "ResultSelector": {
                            "Payload.$": "$.Payload"
                        },
                    },
                    "GetResultsReportIsCompliantBoolean": {
                        "Type": "Task",
                        "Next": "PutEvaluations",
                        "ResultPath": "$.GetResultsReportIsCompliantBoolean",
                        "Resource": "arn:aws:states:::lambda:invoke",
                        "Parameters": {
                            "FunctionName": self.lambda_get_object.function_name,
                            "Payload": {
                                "Bucket.$":"$.SignApigwRequest.Payload.Content.Response.ResultsReport.Buckets.OutputHandlers[0].Bucket",
                                "Key.$":"$.SignApigwRequest.Payload.Content.Response.ResultsReport.Key",
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
                                "MaxAttempts": 8,
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
                    "PutEvaluations": {
                        "Type": "Task",
                        "Next": "GetResourceConfigCompliancee",
                        "ResultPath": "$.PutEvaluations",
                        "Resource": "arn:aws:states:::lambda:invoke",
                        "Parameters": {
                            "FunctionName": self.lambda_put_evaluations.function_name,
                            "Payload": {
                                "Compliance.$": "$.GetResultsReportIsCompliantBoolean.Payload.EvalEngineLambdalith.Evaluation.IsCompliant",
                                "ConfigResultToken.$":"$.ConfigEvent.resultToken",
                                "ResourceId.$":"$.InvokingEvent.configurationItem.resourceId",
                                "ResourceType.$":"$.InvokingEvent.configurationItem.resourceType",
                            },
                        },
                        "ResultSelector": {"Payload.$": "$.Payload"},
                    },
                    "GetResourceConfigCompliancee":{
                        "Type": "Task",
                        "Next":"ChoiceComplianceStatusIsAsExpected",
                        "ResultPath": "$.GetResourceConfigCompliancee",
                        "Resource": "arn:aws:states:::lambda:invoke",
                        "Parameters": {
                            "FunctionName": self.lambda_get_resource_config_compliance.function_name,
                            "Payload": {
                                "ConfigEvent.$":"$.ConfigEvent",
                                "ExpectedComplianceStatus.$": "$.GetResultsReportIsCompliantBoolean.Payload.EvalEngineLambdalith.Evaluation.IsCompliant"
                            }
                        },
                        "ResultSelector": {
                            "Payload.$": "$.Payload"
                        },
                    },
                    "ChoiceComplianceStatusIsAsExpected": {
                        "Type":"Choice",
                        "Default":"ComplianceStatusIsAsExpectedFalse",
                        "Choices":[
                            {
                                "Variable":"$.GetResourceConfigCompliancee.Payload.ComplianceIsAsExpected",
                                "BooleanEquals":True,
                                "Next":"ComplianceStatusIsAsExpectedTrue"
                            },
                        ]
                    },
                    "ComplianceStatusIsAsExpectedTrue":{
                        "Type":"Succeed"
                    },
                    "ComplianceStatusIsAsExpectedFalse":{
                        "Type":"Fail"
                    }
                }
            })
        )

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