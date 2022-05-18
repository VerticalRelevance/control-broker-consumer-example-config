import json
import re
import os

import boto3
from botocore.exceptions import ClientError

import requests
from aws_requests_auth.boto_utils import BotoAWSRequestsAuth

session = boto3.session.Session()
region = session.region_name
account_id = boto3.client('sts').get_caller_identity().get('Account')

s3 = boto3.client("s3")

def get_host(*,full_invoke_url):
    m = re.search('https://(.*)/.*',full_invoke_url)
    return m.group(1)

def put_object(bucket,key,object_:dict):
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
        print(f'no ClientError put_object\nbucket:\n{bucket}\nKey:\n{key}')
        return True
    
def lambda_handler(event,context):
    
    invoke_url = os.environ['ControlBrokerInvokeUrl']
    
    invoking_event = json.loads(event["invokingEvent"])
    print(f"invoking_event:\n{invoking_event}")

    configuration_item = invoking_event["configurationItem"]
    print(f"configuration_item:\n{configuration_item}")

    resource_type = configuration_item["resourceType"]
    print(f"resource_type:\n{resource_type}")

    resource_id = configuration_item["resourceId"]
    print(f"resource_id:\n{resource_id}")

    result_token = event["resultToken"]
    print(f"result_token:\n{result_token}")
    
    config_rule_name = event["configRuleName"]
    print(f"config_rule_name:\n{config_rule_name}")
    
    invoked_by_key = f'{config_rule_name}-{resource_type}-{resource_id}-{invoking_event["notificationCreationTime"]}'

    cb_input_object = {
        "Context":{
            "EnvironmentEvaluation":"Prod",
        },
        "Input": event
    }
    
    def get_host(full_invoke_url):
        m = re.search('https://(.*)/.*',full_invoke_url)
        return m.group(1)
    
    full_invoke_url=os.environ['ControlBrokerInvokeUrl']
    
    host = get_host(full_invoke_url)
        
    auth = BotoAWSRequestsAuth(
        aws_host= host,
        aws_region=region,
        aws_service='execute-api'
    )
    
    r = requests.post(
        full_invoke_url,
        auth = auth,
        json = cb_input_object
    )
    
    print(f'headers:\n{dict(r.request.headers)}\n')
    
    cb_endpoint_response = json.loads(r.content)
    
    status_code = r.status_code
    
    apigw_formatted_response = {
        'StatusCode':status_code,
        'Content': cb_endpoint_response
    }
    
    print(f'\napigw_formatted_response:\n{apigw_formatted_response}')
    
    if status_code != 200:
        return False
    
    return cb_endpoint_response