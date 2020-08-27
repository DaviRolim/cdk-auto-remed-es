console.log('Loading function');
const AWS = require('aws-sdk');
exports.handler = (event, context, callback) => {
    console.log('event= ' + JSON.stringify(event));
    console.log('context= ' + JSON.stringify(context));
    const executionContext = event.ExecutionContext;
    
    const resourceId = executionContext.Execution.Input.detail.requestParameters.evaluations[0].complianceResourceId
    console.log('resourceId ->' + resourceId)

    const resourceType = executionContext.Execution.Input.detail.requestParameters.evaluations[0].complianceResourceType
    console.log('resourceType ->' + resourceType)

    const configAnnotation = executionContext.Execution.Input.detail.requestParameters.evaluations[0].annotation
    console.log('annotation (remediation_type) -> ' + configAnnotation)

    console.log('executionContext= ' + executionContext);
    const executionArn = executionContext.Execution.Id;

    const executionName = executionContext.Execution.Name;
    console.log('executionName= ' + executionName);

    const statemachineName = executionContext.StateMachine.Name;
    console.log('statemachineName= ' + statemachineName);

    const apigwEndpint = process.env.APIURL
    console.log('apigwEndpint = ' + apigwEndpint)

    const approveEndpoint = apigwEndpint + "execution?action=approve&ex=" + executionArn + "&sm=" + statemachineName;
    console.log('approveEndpoint= ' + approveEndpoint);

    const rejectEndpoint = apigwEndpint + "execution?action=reject&ex=" + executionArn + "&sm=" + statemachineName;
    console.log('rejectEndpoint= ' + rejectEndpoint);

    const SNSTOPIC = process.env.SNSTOPIC
    // const emailSnsTopic = "arn:aws:sns:us-west-2:475414269301:capstone-stepfn-SNSHumanApprovalEmailTopic-2SGSTDKP5HPZ";
    const emailSnsTopic = SNSTOPIC;
    console.log('emailSnsTopic= ' + emailSnsTopic);

    var emailMessage = 'Hi! \n\n';
    emailMessage += 'You are receiving this email because your isengard account has a security issue with the resource ' + resourceId + '\n'
    emailMessage += 'Please check the following information and choose one of the options below. \n\n'
    emailMessage += 'Execution Name -> ' + executionName + '\n\n'
    emailMessage += 'Resolve issue automatically ' + approveEndpoint + '\n\n'
    emailMessage += 'Postpone one more hour ' + rejectEndpoint + '\n\n'
    
    const sns = new AWS.SNS();
    var params = {
      Message: emailMessage,
      Subject: "Required approval from AWS Step Functions",
      TopicArn: emailSnsTopic
    };

    // Send SNS 

    sns.publish(params)
      .promise()
      .then(function(data) {
        console.log("MessageID is " + data.MessageId);
        callback(null);
      }).catch(
        function(err) {
        console.error(err, err.stack);
        callback(err);
      });
      
      // Add a item to dynamo
    var docClient = new AWS.DynamoDB.DocumentClient();
    var table = process.env.DYNAMOTABLE
    var paramsDynamo = {
    TableName:table,
    Item:{
        "execution_arn": executionArn,
        "account_id": executionContext.Execution.Input.account,
        "resource_id": resourceId,
        "resource_type": resourceType,
        "remediation_type": configAnnotation,
        "status": "NON_COMPLIANT"
      }
    };
    console.log("Adding a new item...");
    docClient.put(paramsDynamo, function(err, data) {
        if (err) {
            console.error("Unable to add item. Error JSON:", JSON.stringify(err, null, 2));
        } else {
            console.log("Added item:", JSON.stringify(data, null, 2));
        }
    });
}
