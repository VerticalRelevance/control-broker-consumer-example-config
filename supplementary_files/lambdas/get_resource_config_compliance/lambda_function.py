import json
import boto3
import os
from botocore.exceptions import ClientError

config = boto3.client('config')

class NoMatchingEvaluationResults(Exception):
    print('NoMatchingEvaluationResults')
    pass

def get_resource_config_compliance_by_resource(*,resource_type,resource_id, config_rule_name):
    
    print('begin get_resource_config_compliance_by_resource')
    
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
        
        try:
            
            evaluation_result = evaluation_results[0]
        
        except IndexError:
            
            print('NoMatchingEvaluationResults')
            return None
            # raise NoMatchingEvaluationResults
        
        else:
            
            print(f'evaluation_result:\n{evaluation_result}')
    
            return evaluation_result == 'COMPLIANT'

def get_resource_config_compliance_by_rule(*,resource_id, config_rule_name):
    
    print('begin get_resource_config_compliance_by_rule')
    
    try:
        r = config.get_compliance_details_by_config_rule(
            ConfigRuleName = config_rule_name,
            ComplianceTypes=[
                'COMPLIANT',
                'NON_COMPLIANT',
                'NOT_APPLICABLE'
            ],
            Limit = 100 #Max
        )
    except ClientError as e:
        print(f"ClientError\n{e}")
        raise
    else:
        print(r)
        
        evaluation_results = r['EvaluationResults']
        
        print(f'evaluation_results\n{evaluation_results}')
        
        evaluation_results = [i['ComplianceType'] for i in evaluation_results if i['EvaluationResultIdentifier']['EvaluationResultQualifier']['ResourceId'] == resource_id]
        
        try:
            
            evaluation_result = evaluation_results[0]
        
        except IndexError:
            
            print('NoMatchingEvaluationResults')
            return None
            # raise NoMatchingEvaluationResults
        
        else:
            
            print(f'evaluation_result:\n{evaluation_result}')
    
            return evaluation_result == 'COMPLIANT'


def lambda_handler(event, context):


    class ConfigComplianceStatusIsNotAsExpectedException(Exception):
        pass

    print(event)
    
    consumer_metadata = event['ConsumerMetadata']

    print(f'consumer_metadata\n{consumer_metadata}')
    
    resource_type = consumer_metadata['ResourceType']
    
    resource_id = consumer_metadata['ResourceId']
    
    config_rule_name = consumer_metadata['ConfigRuleName']
    
    # result_token = consumer_metadata['ResultToken']
    
    compliance =  get_resource_config_compliance_by_resource(
        resource_type = resource_type,
        resource_id = resource_id,
        config_rule_name = config_rule_name,
    )
    
    get_resource_config_compliance_by_rule(
        resource_id = resource_id,
        config_rule_name = config_rule_name,
    )
    
    expected_final_status = event['ExpectedFinalStatusIsCompliant']
    
    print(f'expected_final_status:\n{expected_final_status}')
    
    if expected_final_status is not None:
        
        if expected_final_status != compliance:
            
            print(f'{expected_final_status} != {compliance}\nraising ConfigComplianceStatusIsNotAsExpectedException')
            
            raise ConfigComplianceStatusIsNotAsExpectedException
        
        else:
            
            print(f'{expected_final_status} == {compliance}')
            
    return {
        "ResourceConfigIsCompliant":compliance
    }