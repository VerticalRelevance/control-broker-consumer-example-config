import json
import boto3
from botocore.exceptions import ClientError

s3 = boto3.client('s3')

def object_exists(*,bucket,key):
    print(f'trying head_object\nbucket:\n{bucket}\nkey:\n{key}')
    try:
        r = s3.head_object(
            Bucket = bucket,
            Key = key
        )
    except ClientError as e:
        print(e)
        if e.response['ResponseMetadata']['HTTPStatusCode'] == 403:
            print(f'403 as proxy for nonexistance, but may hide actual actual IAM issues')
            return False
        if e.response['ResponseMetadata']['HTTPStatusCode'] == 404:
            return False
        else:
            raise
    else:
        return True

def s3_uri_to_bucket_key(*,uri):
    path_parts=uri.replace("s3://","").split("/")
    bucket=path_parts.pop(0)
    key="/".join(path_parts)
    return bucket, key

def lambda_handler(event,context):
    
    class ObjectDoesNotExistException(Exception):
        pass
    
    print(event)
    
    bucket = event.get('Bucket')
    key = event.get('Key')
    
    if not bucket and not key:
        bucket, key = s3_uri_to_bucket_key(uri=event['S3Uri'])

    existance = object_exists(bucket=bucket,key=key)
    print(f'existance:\n{existance}')
    
    if not existance:
        raise ObjectDoesNotExistException
    else:
        return True