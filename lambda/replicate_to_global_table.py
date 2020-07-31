import boto3
import uuid
import os

def handler(event, context):
    print(event)
    sts_connection = boto3.client('sts')
    acct_b = sts_connection.assume_role(
        RoleArn=os.environ['ROLE_ARN'],
        RoleSessionName="cross_acct_lambda"
    )
    
    ACCESS_KEY = acct_b['Credentials']['AccessKeyId']
    SECRET_KEY = acct_b['Credentials']['SecretAccessKey']
    SESSION_TOKEN = acct_b['Credentials']['SessionToken']
    # create service client using the assumed role credentials, e.g. S3
    dynamodb = boto3.resource(
        'dynamodb',
        aws_access_key_id=ACCESS_KEY,
        aws_secret_access_key=SECRET_KEY,
        aws_session_token=SESSION_TOKEN,
        region_name='us-east-1'
    )
    table = dynamodb.Table('Security_Occurrences')

    records = event['Records'][0]
    item = records['dynamodb']['NewImage']
    response = 'success'
    if item.get('status').get('S') in ['non_compliant', 'compliant']:
        print(item)
        item['ID'] = {'S': str(uuid.uuid4())}
        try:
            response = table.put_item(Item=item)
        except Exception as e:
            print(e)
            return "catched error -> " + str(e)
    return response