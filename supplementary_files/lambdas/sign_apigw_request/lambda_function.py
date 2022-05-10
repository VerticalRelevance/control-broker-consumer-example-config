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
    
def lambda_handler(event,context):
    
    # invoked_by_key = f'{config_rule_name}-{resource_type}-{resource_id}-{invoking_event["notificationCreationTime"]}'

    invoked_by_key = os.environ['AWS_LAMBDA_FUNCTION_NAME']

    invoke_url = os.environ['ControlBrokerInvokeUrl']
    
    input_analyzed = {
        "Bucket":os.environ['ConfigEventsRawInputBucket'],
        "Key":invoked_by_key
    }
    
    put_object(
        bucket = input_analyzed['Bucket'],
        key = input_analyzed['Key'],
        object_ = event
    )
    
    cb_input_object = {
        "Context":{
            "EnvironmentEvaluation":"Prod",
        },
        "Input": input_analyzed
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
    
    return apigw_formatted_response