import json
import boto3
import os
from botocore.exceptions import ClientError
from datetime import datetime

sfn = boto3.client("stepfunctions")
s3 = boto3.client("s3")

def async_sfn(*, SfnArn, Input: dict):
    try:
        r = sfn.start_execution(stateMachineArn=SfnArn, input=json.dumps(Input))
    except ClientError as e:
        print(f"ClientError\n{e}")
        raise
    else:
        print(r)
        return r["executionArn"]

def put_object(*,Bucket,Key,Dict):
    try:
        r = s3.put_object(
            Bucket = Bucket,
            Key = Key,
            Body = json.dumps(Dict)
        )
    except ClientError as e:
        print(f'ClientError:\n{e}')
        raise
    else:
        return True

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
    
    config_event_payload_bucket = os.environ["ConfigEventPayloadsBucket"]

    print(f'procesing sfn\n{os.environ["ConfigEventProcessingSfnArn"]}')
    
    key = f'{event["configRuleName"]}-{resource_type}-{resource_id}-{invoking_event["notificationCreationTime"]}'
    
    if not put_object(
        Bucket = config_event_payload_bucket,
        Key = key,
        Dict = event
    ):
        return False
    
    config_event_metadata = {
        "ResourceType":resource_type,
        "ResourceId":resource_id,
        "ConfigResultToken":result_token
    }
    
    control_broker_consumer_inputs = {
        "ControlBrokerConsumerInputs":{
            "InputType":"ConfigEvent",
            "Bucket": config_event_payload_bucket,
            "InputKeys":[key],
            "ConsumerMetadata": config_event_metadata,
        }
    }
    
    print(f'control_broker_consumer_inputs\n{control_broker_consumer_inputs}')

    processed = async_sfn(
        SfnArn=os.environ["ConfigEventProcessingSfnArn"],
        Input=control_broker_consumer_inputs
    )
    
    print(f'processed by sfn:\n{processed}')
    
    return True