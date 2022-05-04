import json
import boto3
import os
from botocore.exceptions import ClientError

config = boto3.client('config')

def lambda_handler(event, context):

    print(event)