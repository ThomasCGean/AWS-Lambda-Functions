import json
import boto3
import os
import logging
from botocore.exceptions import ClientError

# Set up logging
logger = logging.getLogger()
logger.setLevel(logging.INFO)

# Get DynamoDB table name from environment variable or use default
TABLE_NAME = os.environ.get('PROFILE_TABLE_NAME', 'SecureBankingCustomerProfilesFinal')
dynamodb = boto3.resource('dynamodb')
table = dynamodb.Table(TABLE_NAME)

def lambda_handler(event, context):
    try:
        # Extract user ID from Cognito claims
        user_id = event['requestContext']['authorizer']['claims']['sub']
        record_type = "UserProfile"
        logger.info(f"[START] Updating profile for user_id: {user_id}, recordType: {record_type}")

        # Parse the request body
        body = json.loads(event.get('body', '{}'))
        logger.info(f"[REQUEST] Received update body: {json.dumps(body)}")

        # Supported fields to update
        update_fields = ['FirstName', 'LastName', 'Email', 'PhoneNumber', 'Preferences']
        update_expression_parts = []
        expression_attribute_values = {}

        for field in update_fields:
            if field in body:
                update_expression_parts.append(f"{field} = :{field}")
                expression_attribute_values[f":{field}"] = body[field]

        if not update_expression_parts:
            logger.warning(f"[WARN] No updatable fields provided for user_id: {user_id}")
            return {
                "statusCode": 400,
                "body": json.dumps({"error": "No valid fields provided to update."})
            }

        update_expression = "SET " + ", ".join(update_expression_parts)

        logger.info(f"[UPDATE] DynamoDB UpdateExpression: {update_expression}")
        logger.info(f"[UPDATE] ExpressionAttributeValues: {json.dumps(expression_attribute_values)}")

        # Perform the update
        table.update_item(
            Key={
                'UserID': user_id,
                'recordType': record_type
            },
            UpdateExpression=update_expression,
            ExpressionAttributeValues=expression_attribute_values
        )

        logger.info(f"[SUCCESS] Updated profile for user_id: {user_id}")
        return {
            "statusCode": 200,
            "body": json.dumps({"message": "Profile updated successfully."}),
            "headers": {
                "Content-Type": "application/json"
            }
        }

    except ClientError as e:
        logger.exception(f"[ERROR] DynamoDB client error for user_id: {user_id}")
        return {
            "statusCode": 500,
            "body": json.dumps({"error": "Failed to update user profile", "details": str(e)})
        }

    except Exception as e:
        logger.exception("[ERROR] Unexpected error occurred")
        return {
            "statusCode": 500,
            "body": json.dumps({"error": "Unexpected error", "details": str(e)})
        }
