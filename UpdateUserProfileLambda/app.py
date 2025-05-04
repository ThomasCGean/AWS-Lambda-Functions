import json
import boto3
import os
import logging
from botocore.exceptions import ClientError

logger = logging.getLogger()
logger.setLevel(logging.INFO)

TABLE_NAME = os.environ.get('PROFILE_TABLE_NAME', 'SecureBankingCustomerProfilesFinal')
dynamodb = boto3.resource('dynamodb')
table = dynamodb.Table(TABLE_NAME)

def lambda_handler(event, context):
    try:
        user_id = event['requestContext']['authorizer']['claims']['sub']
        record_type = "UserProfile"

        logger.info(f"Updating profile for user_id: {user_id}")

        # Parse incoming JSON body
        body = json.loads(event['body'])

        # Extract fields to update
        update_fields = ['FirstName', 'LastName', 'Email', 'PhoneNumber', 'Preferences']
        update_expression_parts = []
        expression_attribute_values = {}

        for field in update_fields:
            if field in body:
                update_expression_parts.append(f"{field} = :{field}")
                expression_attribute_values[f":{field}"] = body[field]

        if not update_expression_parts:
            return {
                "statusCode": 400,
                "body": json.dumps({"error": "No valid fields provided to update."})
            }

        update_expression = "SET " + ", ".join(update_expression_parts)

        # Perform the update
        table.update_item(
            Key={
                'UserID': user_id,
                'recordType': record_type
            },
            UpdateExpression=update_expression,
            ExpressionAttributeValues=expression_attribute_values
        )

        return {
            "statusCode": 200,
            "body": json.dumps({"message": "Profile updated successfully."}),
            "headers": {
                "Content-Type": "application/json"
            }
        }

    except ClientError as e:
        logger.exception("DynamoDB update failed.")
        return {
            "statusCode": 500,
            "body": json.dumps({"error": "Failed to update user profile", "details": str(e)})
        }

    except Exception as e:
        logger.exception("Unexpected error.")
        return {
            "statusCode": 500,
            "body": json.dumps({"error": "Unexpected error", "details": str(e)})
        }
