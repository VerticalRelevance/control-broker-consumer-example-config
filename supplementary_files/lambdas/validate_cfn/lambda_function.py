import json

import boto3
from botocore.exceptions import ClientError
from botocore.config import Config

cfn = boto3.client('cloudformation')
s3 = boto3.client('s3')

def validate_cfn(*,s3_uri):
    
    def s3_uri_to_bucket_key(*,s3_uri):
        path_parts=s3_uri.replace("s3://","").split("/")
        bucket=path_parts.pop(0)
        key="/".join(path_parts)
        return bucket, key
    
    def generate_presigned_url(Bucket,Key,ClientMethod="get_object",TTL=3600):
        try:
            url = s3.generate_presigned_url(
                ClientMethod=ClientMethod,
                Params={
                    'Bucket':Bucket,
                    'Key':Key
                },
                ExpiresIn=TTL
            )
        except ClientError:
            raise
        else:
            print(f"Presigned URL:\n{url}")
            return url
    
    bucket,key = s3_uri_to_bucket_key(s3_uri=s3_uri)
    
    presigned = generate_presigned_url(Bucket=bucket,Key=key)
    
    try:
        r = cfn.validate_template(
            TemplateURL=presigned
        )
    except ClientError as e:
        print(f'ClientError:\n{e}')
        return False
    else:
        print(r)
        return True

def lambda_handler(event, context):
    
    print(event)
    
    validity = validate_cfn(
        s3_uri = event['CloudFormationTemplate']['S3Uri']
    )
    
    print(f'validity:\n{validity}')
    return validity