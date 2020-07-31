import json
import boto3
import os

client = boto3.client('es')

def update_status(execution_arn, dynamodb=None):
    if not dynamodb:
        dynamodb = boto3.resource('dynamodb')

    table = dynamodb.Table(os.environ['DYNAMOTABLE'])

    response = table.update_item(
        Key={"execution_arn": execution_arn},
        UpdateExpression="set #stats=:s",
        ExpressionAttributeValues={
            ':s': 'COMPLIANT'
        },
        ExpressionAttributeNames={
            '#stats': 'status'
        },
        ReturnValues="UPDATED_NEW"
    )
    return response

def deny_public_access(domain_name):
    response = client.describe_elasticsearch_domain_config(
    DomainName=domain_name
    )
    access_policy = response.get('DomainConfig').get('AccessPolicies')
    
    options = access_policy['Options']
    statement_deny = json.loads(options.replace('Allow', 'Deny')).get('Statement')[0]
    new_access_policy = options.replace(']}', ', '+ json.dumps(statement_deny) + ']}')
    
    client.update_elasticsearch_domain_config(
      DomainName=domain_name, 
      AccessPolicies=new_access_policy
    )
    
def handler(event, context):
  print(event)
  execution_arn = event['ExecutionContext']['Execution']['Id']
  event_input = event['ExecutionContext']['Execution']['Input']
  
  resource = event_input['detail']['requestParameters']['evaluations']
  es_domain = resource[0]['complianceResourceId']
  deny_public_access(es_domain)
  dynamo_response = update_status(execution_arn)
  return dynamo_response
