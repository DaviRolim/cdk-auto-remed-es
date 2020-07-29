const AWS = require('aws-sdk'); 

  exports.handler = async (event, context, callback) => {
    console.log('Event= ' + JSON.stringify(event));
    const action = event.queryStringParameters.action;
    const executionArn = event.queryStringParameters.ex;
    
    var docClient = new AWS.DynamoDB.DocumentClient();
    var table = process.env.DYNAMOTABLE;
  
    var message = "";
    var statusDynamo = "";
    if (action === "approve") {
      message = "Auto-remediation activated";
      statusDynamo = "Approved!";
    } else if (action === "reject") {
      message = "Auto-remediation postponed for one hour";
      statusDynamo = "Rejected!";
    } else {
      console.error("Unrecognized action. Expected: approve, reject.");
      callback({"Status": "Failed to process the request. Unrecognized Action."});
    }
    
    var statusDynamo = action == "approve" ? "Approved!": "Rejected!";
    var params = {
        TableName:table,
        Key:{
            "execution_arn": executionArn
        },
        UpdateExpression: "set #stats = :s",
        ExpressionAttributeValues:{
            ":s":statusDynamo
        },
        ExpressionAttributeNames:{
        "#stats": "status"
        },
        ReturnValues:"UPDATED_NEW"
    }

    console.log("Updating the item...", params);
    await docClient.update(params, function(err, data) {
        if (err) {
            console.error("Unable to update item. Error JSON:", JSON.stringify(err, null, 2));
        } else {
            console.log("UpdateItem succeeded:", JSON.stringify(data, null, 2));
        }
    })
    let response = {
      statusCode:200,
      body: JSON.stringify({'message': message})
    }
    return response
  }
  
  