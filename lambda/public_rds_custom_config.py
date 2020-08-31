import boto3
import botocore
import json

def evaluate_compliance(configuration_item):
    vpc_id = configuration_item["configuration"]['dBSubnetGroup']["vpcId"]
    subnet_ids = []
    for i in configuration_item["configuration"]['dBSubnetGroup']['subnets']:
        subnet_ids.append(i['subnetIdentifier'])
    client = boto3.client("ec2")

    response = client.describe_route_tables()

    print('Route table %s', response)

    private = True

    for subnet_id in subnet_ids:
        mainTableIsPublic = False
        noExplicitAssociationFound = True
        explicitAssocationIsPublic = False
        for i in response['RouteTables']:
            if i['VpcId'] == vpc_id:
                for j in i['Associations']:
                    if j['Main'] == True:
                        for k in i['Routes']:
                            if ('DestinationCidrBlock' in k) and ('GatewayId' in k):
                                if k['DestinationCidrBlock'] == '0.0.0.0/0' or k['GatewayId'].startswith('igw-'):
                                    mainTableIsPublic = True
                    else:
                        if j['SubnetId'] == subnet_id:
                            noExplicitAssociationFound = False
                            for k in i['Routes']:
                                if ('DestinationCidrBlock' in k) and ('GatewayId' in k):
                                    if k['DestinationCidrBlock'] == '0.0.0.0/0' or k['GatewayId'].startswith('igw-'):
                                        explicitAssocationIsPublic = True

        if (mainTableIsPublic and noExplicitAssociationFound) or explicitAssocationIsPublic:
            private = False

    instanceIsPubliclyAccessible = configuration_item["configuration"]['publiclyAccessible']

    security_group_ids = []
    for i in configuration_item["configuration"]['vpcSecurityGroups']:
        security_group_ids.append(i['vpcSecurityGroupId'])

    dbInstanceHasPublicInboundSG = False
    response = client.describe_security_groups(
        Filters=[
            {
                'Name': 'ip-permission.cidr',
                'Values': [
                    '0.0.0.0/0',
                ],
            },
        ],
        GroupIds=security_group_ids,
    )
    dbInstanceHasPublicInboundSG = len(response['SecurityGroups']) > 0

    privateSubnetMessage = "The instance is not in a private subnet." if not private else "The instance is in a private subnet."

    publiclyAccessibleMessage = "The instance is not publicly-accessible." if not instanceIsPubliclyAccessible else 'The instance is publicly-accessible.'

    openInboundSGMessage = "The instance does not have a publicly-opened inbound security group."
    if (openInboundSGMessage):
        openInboundSGMessage = "The instance has a publicly-opened inbound security group."

    nonCompliant = not (private) and instanceIsPubliclyAccessible and dbInstanceHasPublicInboundSG
    retorno = dict(compliance_type='COMPLIANT', annotation=f'{privateSubnetMessage} {publiclyAccessibleMessage}  {openInboundSGMessage}')
    if nonCompliant:
        retorno['compliance_type'] = 'NON_COMPLIANT'
    return retorno

def handler(event, context):
    print('Event %s', event)
    invoking_event = json.loads(event['invokingEvent'])
    configuration_item = invoking_event["configurationItem"]
    evaluation = evaluate_compliance(configuration_item)
    config = boto3.client('config')

    response = config.put_evaluations(
        Evaluations=[
            {
                'ComplianceResourceType': invoking_event['configurationItem']['resourceType'],
                'ComplianceResourceId': invoking_event['configurationItem']['configuration']['dBInstanceIdentifier'],
                'ComplianceType': evaluation["compliance_type"],
                "Annotation": evaluation["annotation"],
                'OrderingTimestamp': invoking_event['configurationItem']['configurationItemCaptureTime']
            },
        ],
        ResultToken=event['resultToken'])

    return response