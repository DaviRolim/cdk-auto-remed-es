import json
import boto3
import urllib3

http = urllib3.PoolManager()

def check_public_policy(policy):
    print(policy)
    json_policy = json.loads(policy)
    aws, principal = [items for items in json_policy.get('Statement')[0].get('Principal').items()][0]

    open_principal = aws == 'AWS' and principal == '*'
    no_condition = "Condition" not in policy
    open_policy = False

    print(f'open_principal {open_principal} and no_condition {no_condition}')

    if( ('0.0.0.0/0' in policy and 'Deny' not in policy) or (open_principal and no_condition) ):
        open_policy = True


    return open_policy

def evaluate_compliance(config_item):
    compliance_status = dict(complianceType='COMPLIANT', annotation='restrict_es_open_policy')
    if config_item['configuration'] is not None:
        try:
            open_endpoint = False
            if 'endpoint' in config_item['configuration']:
                endpoint = config_item['configuration']['endpoint']
                print('endpoint: ', endpoint)
                response = http.request('GET', f'https://{endpoint}')
                open_endpoint = response.status == 200
            access_policy = config_item['configuration']['accessPolicies']
            open_policy = check_public_policy(access_policy)
            print(f'is policy open? {open_policy} - is endpoint accessible? {open_endpoint}')
            if(open_endpoint or open_policy): 
                compliance_status =  dict(complianceType='NON_COMPLIANT', annotation='restrict_es_open_policy')
        except Exception as e:
            print(f'catched error -> {e}')

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