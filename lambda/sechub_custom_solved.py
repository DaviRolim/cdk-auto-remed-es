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

    resource_id = resource['complianceResourceId']
    account_id = event["detail"]["userIdentity"]["accountId"]
    region = event["detail"]["awsRegion"]

    logger.info('Checking for existing findings')
    filters = {
    		"ProductArn": [{
        		"Value": f"arn:aws:securityhub:{region}:{account_id}:product/{account_id}/default",
        		"Comparison": "EQUALS"
    		}],
    		"Id": [{
        		"Value": f"configcompliance/{resource_id}",
        		"Comparison": "EQUALS"
    		}],
    		"RecordState": [{
    			"Value": "ACTIVE",
    			"Comparison": "EQUALS"
    		}]
		}


    get_findings_response = sechubclient.get_findings(
        Filters=filters
    )

    logger.info('Results from get findings')
    logger.info(get_findings_response)

    #verify that there is a finding returned back.
    findings = get_findings_response["Findings"]
    if findings:
        #Ok to update
        logger.info('There was a finding to update')

        note= {
            "Text": "Updated as now compliant",
            "UpdatedBy" : "Lambda"
        }

        logger.info ('Updating existing finding to ARCHIVED')
        batch_update_findings_response = sechubclient.batch_update_findings(
            FindingIdentifiers=[
                            {
                                "Id": f"configcompliance/{resource_id}",
                                'ProductArn': f"arn:aws:securityhub:{region}:{account_id}:product/{account_id}/default"
                            },
            ],
            Note=note,
            Workflow=dict(Status="RESOLVED")
        
        )
        logger.info(f'batch response: {batch_update_findings_response}')

        update_response = sechubclient.update_findings(
            Filters=filters,
            Note=note,
            RecordState='ARCHIVED')

        logger.info('output from update finding')
        logger.info (update_response)

    else:
        logger.info ("no findings to update.  Leaving alone")