import json
import boto3
import os
from botocore.exceptions import ClientError

config = boto3.client('config')

def get_resource_config_compliance(*,resource_type,resource_id, config_rule_name):
    
    try:
        r = config.get_compliance_details_by_resource(
            ResourceType=resource_type,
            ResourceId=resource_id,
            ComplianceTypes=[
                'COMPLIANT',
                'NON_COMPLIANT',
                # 'NOT_APPLICABLE',
                # 'INSUFFICIENT_DATA',
            ],
        )
    except ClientError as e:
        print(f"ClientError\n{e}")
        raise
    else:
        print(r)
        
        evaluation_results = r['EvaluationResults']
        
        print(f'evaluation_results\n{evaluation_results}')
        
        evaluation_results = [i['ComplianceType'] for i in evaluation_results if i['EvaluationResultIdentifier']['EvaluationResultQualifier']['ConfigRuleName'] == config_rule_name]
        
        print(f'evaluation_results\n{evaluation_results}')
        
        compliance = evaluation_results[0]
        
        print(f'compliance\n{compliance}')

        return compliance == 'COMPLIANT'


def lambda_handler(event, context):

    print(event)
    
    control_broker_consumer_inputs = event['ControlBrokerConsumerInputs']
    
    print(f'control_broker_consumer_inputs\n{control_broker_consumer_inputs}')
    
    consumer_metadata = control_broker_consumer_inputs['ConsumerMetadata']

    print(f'consumer_metadata\n{consumer_metadata}')
    
    resource_type = consumer_metadata['ResourceType']
    
    resource_id = consumer_metadata['ResourceId']
    
    config_rule_name = consumer_metadata['ConfigRuleName']
    
    # result_token = consumer_metadata['ResultToken']
    
    compliance =  get_resource_config_compliance(
        resource_type = resource_type,
        resource_id = resource_id,
        config_rule_name = config_rule_name,
    )
    
    return {
        "ResourceConfigIsCompliant":compliance
    }