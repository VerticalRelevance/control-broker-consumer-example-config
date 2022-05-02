import json
import boto3
import os
from botocore.exceptions import ClientError
from datetime import datetime

sfn = boto3.client("stepfunctions")

def async_sfn(*, SfnArn, Input: dict):
    try:
        r = sfn.start_execution(stateMachineArn=SfnArn, input=json.dumps(Input))
    except ClientError as e:
        print(f"ClientError\n{e}")
        raise
    else:
        return r["executionArn"]

def lambda_handler(event, context):

    print(event)

    invoking_event = json.loads(event["invokingEvent"])
    print(f"invoking_event:\n{invoking_event}")

    rule_parameters = event.get("ruleParameters")
    if rule_parameters:
        rule_parameters = json.loads(rule_parameters)
        print(f"rule_parameters:\n{rule_parameters}")

    configuration_item = invoking_event["configurationItem"]
    print(f"configuration_item:\n{configuration_item}")

    item_status = configuration_item["configurationItemStatus"]
    print(f"item_status:\n{item_status}")

    resource_type = configuration_item["resourceType"]
    print(f"resource_type:\n{resource_type}")

    resource_configuration = configuration_item["configuration"]
    print(f"resource_configuration:\n{resource_configuration}")

    resource_id = configuration_item["resourceId"]
    print(f"resource_id:\n{resource_id}")

    result_token = event["resultToken"]
    print(f"result_token:\n{result_token}")

    # process

    print(f'procesing sfn\n{os.environ["ConfigEventProcessingSfnArn"]}')
    
    processing_sfn_input = {
        "Config":event
    }
    
    print(f'processing_sfn_input\n{processing_sfn_input}')

    processed = async_sfn(
        SfnArn=os.environ["ConfigEventProcessingSfnArn"],
        Input=processing_sfn_input
    )
    
    print(f'processed by sfn:\n{processed}')
    
    return True