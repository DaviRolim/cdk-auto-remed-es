import json
import boto3
import urllib3

http = urllib3.PoolManager()

def check_public_policy(policy):
    print(policy)
    open_policy = False
    if('0.0.0.0/0' in policy):
        open_policy = True
    return open_policy

def evaluate_compliance(config_item):
    configuration = config_item['configuration']
    compliance_status = dict(complianceType='COMPLIANT', annotation='Restricted ES domain')
    if 'endpoint' in configuration:
        endpoint = configuration['endpoint']
        response = http.request('GET', f'http://{endpoint}')
        open_endpoint = response.status == 200
        access_policy = config_item['configuration']['accessPolicies']
        open_policy = check_public_policy(access_policy)
        print(f'is policy open? {open_policy} - is endpoint accessible? {open_endpoint}')
        if(open_endpoint or open_policy): 
            compliance_status =  dict(complianceType='NON_COMPLIANT', annotation='Endpoint accessible for everyone or policy too explicit')

    return compliance_status

def handler(event, context):
    print(event)
    config = boto3.client('config')

    invoking_event = json.loads(event['invokingEvent'])
    configuration_item = invoking_event["configurationItem"]
    evaluation = evaluate_compliance(configuration_item)
    response = config.put_evaluations(
    Evaluations=[
        {
            'ComplianceResourceType': invoking_event['configurationItem']['resourceType'],
            'ComplianceResourceId': invoking_event['configurationItem']['resourceName'],
            'ComplianceType': evaluation['complianceType'],
            "Annotation": evaluation['annotation'],
            'OrderingTimestamp': invoking_event['configurationItem']['configurationItemCaptureTime']
        },
    ],
    ResultToken=event['resultToken'])

    return response