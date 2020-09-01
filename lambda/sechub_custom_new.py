#Script that is designed to take in a notification from a config rule that is looking to see if an EC2 instance is 
#running a compliant AMI or not (approved-amis-by-id)
#If the resource in the message is not compliant then a finding gets created in Security Hub
# If the resource is compliant then any open findings in security hub get archived

import boto3
import json
import datetime
import logging
logger = logging.getLogger()
logger.setLevel(logging.INFO)

sechubclient = boto3.client('securityhub')

def handler(event, context):
	logger.info('Event Data')
	logger.info(event)
	
	resource = event['detail']['requestParameters']['evaluations'][0]

	compliance_type = resource['complianceType']
	compliance_resource_type = resource['complianceResourceType']
	resource_id = resource['complianceResourceId']
	account_id = event["detail"]["userIdentity"]["accountId"]
	annotation = resource['annotation']
	# compliance_type = event["detail"]["newEvaluationResult"]["complianceType"]
	# account_id = event["detail"]["awsAccountId"]
	# resource_id = event["detail"]["newEvaluationResult"]["evaluationResultIdentifier"]["evaluationResultQualifier"]["resourceId"]
	region = event["detail"]["awsRegion"]


	if compliance_type == 'NON_COMPLIANT':
		logger.info("Resource is out of compliance")
		
		d = datetime.datetime.utcnow() # <-- get time in UTC
		

# "Id": "configcompliance/surovsk",
#   "ProductArn": "arn:aws:securityhub:us-east-1:475414269301:product/475414269301/default",
		findings = [{
    		"SchemaVersion": "2018-10-08",
    		"Title": f"Resource NON-COMPLIANT - {resource_id}",
    		"Description": f"{annotation}",
    		"ProductArn": f"arn:aws:securityhub:{region}:{account_id}:product/{account_id}/default",
    		"AwsAccountId": account_id,
    		"Id": f"configcompliance/{resource_id}",
    		"GeneratorId": "CUSTOM:CONFIG",
    		"Types": [],
    		"CreatedAt": d.isoformat("T") + "Z",
    		"UpdatedAt": d.isoformat("T") + "Z",
    		"Severity": {
        		"Label": "MEDIUM"
    		},
    		"Resources": [{
        		"Type": compliance_resource_type,
        		"Id": f"arn:aws:es:{region}:{account_id}:domain/{resource_id}" # FIXED WORKING ONLY FOR ES DOMAINS (TODO)
        		# "Id": f"arn:aws:ec2:{region}:{account_id}:instance/{resource_id}"
    		}]
		}]

		logger.info ('Creating a finding')

		import_response = sechubclient.batch_import_findings(
			Findings=findings
		)

		logger.info('Response from creating finding')
		logger.info(import_response)

