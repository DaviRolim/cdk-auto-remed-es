import boto3
from botocore.exceptions import ClientError
import json
import os

def get_item(executionArn, dynamodb=None):
    if not dynamodb:
        dynamodb = boto3.resource('dynamodb')

    table = dynamodb.Table(os.environ['DYNAMOTABLE'])

    try:
        response = table.get_item(Key={'execution_arn': executionArn})
    except ClientError as e:
        print(e.response['Error']['Message'])
    else:
        return response['Item']
        
def update_status(execution_arn, dynamodb=None):
    if not dynamodb:
        dynamodb = boto3.resource('dynamodb')

    table = dynamodb.Table(os.environ['DYNAMOTABLE'])

    response = table.update_item(
        Key={"execution_arn": execution_arn},
        UpdateExpression="set #stats=:s",
        ExpressionAttributeValues={
            ':s': 'started'
        },
        ExpressionAttributeNames={
            '#stats': 'status'
        },
        ReturnValues="UPDATED_NEW"
    )
    return response


def handler(event, context):
    execution_arn = event['ExecutionContext']['Execution']['Id']
    print(event)
    print(execution_arn)
    item = get_item(execution_arn)
    print(item)
    status = item['status']

    if status == 'Rejected!':
        update_status(execution_arn)
    
    return {"status": status}          
