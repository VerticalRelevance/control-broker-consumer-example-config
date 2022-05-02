import json

import boto3
from botocore.exceptions import ClientError
from botocore.config import Config

cfn = boto3.client('cloudformation')
s3 = boto3.client('s3')

def validate_cfn(*,S3Uri):
    
    def s3_uri_to_bucket_key(*,S3Uri):
        path_parts=S3Uri.replace("s3://","").split("/")
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
    
    bucket,key = s3_uri_to_bucket_key(S3Uri=S3Uri)
    
    presigned = generate_presigned_url(Bucket=bucket,Key=key)
    
    try:
        r = cfn.validate_template(
            TemplateURL=presigned
        )
    except ClientError as e:
        print(f'ClientError:\n{e}')
        raise
    # except cfn.exceptions.TemplateValidationError as e:
    #     print(f'TemplateValidationError:\n{e}')
    #     return False
    else:
        print(r)
        return True

def lambda_handler(event, context):
    
    print(event)
    
    validate_cfn(
        S3Uri = event['CloudFormationTemplate']['S3Uri']
    )