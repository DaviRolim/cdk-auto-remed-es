import json
import boto3
import os

client = boto3.client('rds')
def handler(event, context):
  print(event)
  event_input = event['ExecutionContext']['Execution']['Input']
  
  resource = event_input['detail']['requestParameters']['evaluations']
  rds_identifier = resource[0]['complianceResourceId']
  response = client.modify_db_instance(DBInstanceIdentifier=rds_identifier,PubliclyAccessible=False)
  print(response)

