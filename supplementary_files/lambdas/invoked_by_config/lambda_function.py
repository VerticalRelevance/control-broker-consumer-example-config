import json
import boto3
import os
from botocore.exceptions import ClientError
from datetime import datetime

sfn = boto3.client("stepfunctions")
s3 = boto3.client("s3")

def async_sfn(*, sfn_arn, input: dict):
    try:
        r = sfn.start_execution(stateMachineArn=sfn_arn, input=json.dumps(input))
    except ClientError as e:
        print(f"ClientError\n{e}")
        raise
    else:
        print(f'no ClientError start_execution:\nsfn_arn:\n{sfn_arn}\ninput:\n{input}')
        return r["executionArn"]

def put_object(bucket,key,object_:dict):
    print(f'put_object\nbucket:\n{bucket}\nKey:\n{key}')
    try:
        r = s3.put_object(
            Bucket = bucket,
            Key = key,
            Body = json.dumps(object_)
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
        bucket = config_event_payload_bucket,
        key = key,
        object_ = event
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
        sfn_arn=os.environ["ConfigEventProcessingSfnArn"],
        input=control_broker_consumer_inputs
    )
    
    print(f'processed by sfn:\n{processed}')
    
    return True