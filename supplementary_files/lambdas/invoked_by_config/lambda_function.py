import json
import os
import re

import boto3
from botocore.exceptions import ClientError

import requests
from aws_requests_auth.boto_utils import BotoAWSRequestsAuth

session = boto3.session.Session()
region = session.region_name
account_id = boto3.client('sts').get_caller_identity().get('Account')

sfn = boto3.client("stepfunctions")

def async_sfn(*, sfn_arn, input: dict):
    try:
        r = sfn.start_execution(stateMachineArn=sfn_arn, input=json.dumps(input))
    except ClientError as e:
        print(f"ClientError\n{e}")
        raise
    else:
        print(f'no ClientError start_execution:\nsfn_arn:\n{sfn_arn}\ninput:\n{input}')
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
    
    if item_status == 'ResourceDeleted':
        return True

    resource_type = configuration_item["resourceType"]
    print(f"resource_type:\n{resource_type}")

    resource_configuration = configuration_item["configuration"]
    print(f"resource_configuration:\n{resource_configuration}")

    resource_id = configuration_item["resourceId"]
    print(f"resource_id:\n{resource_id}")

    result_token = event["resultToken"]
    print(f"result_token:\n{result_token}")
    
    config_rule_name = event["configRuleName"]
    print(f"config_rule_name:\n{config_rule_name}")

    # process
    
    processed = async_sfn(
        sfn_arn=os.environ["ConfigEventProcessingSfnArn"],
        input=event
    )

    print(f'processed by sfn:\n{processed}')
    
    return True