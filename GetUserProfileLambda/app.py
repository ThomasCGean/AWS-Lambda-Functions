import json
import boto3
import os
import logging
from botocore.exceptions import ClientError

# Set up logging
logger = logging.getLogger()
logger.setLevel(logging.INFO)

# Environment variable for DynamoDB table name
TABLE_NAME = os.environ.get('PROFILE_TABLE_NAME', 'SecureBankingCustomerProfilesFinal')

# Setup DynamoDB
dynamodb = boto3.resource('dynamodb')
table = dynamodb.Table(TABLE_NAME)

# Common CORS headers
CORS_HEADERS = {
    "Content-Type": "application/json",
    "Access-Control-Allow-Origin": "*",
    "Access-Control-Allow-Credentials": "true"
}

def lambda_handler(event, context):
    try:
        logger.info(f"FULL EVENT: {json.dumps(event)}")

        # Extract Cognito user claims
        claims = event.get('requestContext', {}).get('authorizer', {}).get('claims', {})
        user_id = claims.get('sub')

        if not user_id:
            logger.warning("User ID (sub) not found in token claims.")
            return {
                "statusCode": 403,
                "body": json.dumps({"error": "User ID not available in token claims."}),
                "headers": CORS_HEADERS
            }

        logger.info(f"Fetching profile for user_id: {user_id}")

        response = table.get_item(
            Key={
                'UserID': user_id,
                'recordType': 'UserProfile'
            }
        )

        item = response.get('Item')
        if not item:
            logger.info("Profile not found.")
            return {
                "statusCode": 404,
                "body": json.dumps({"error": "User profile not found."}),
                "headers": CORS_HEADERS
            }

        logger.info("Profile retrieved successfully.")
        return {
            "statusCode": 200,
            "body": json.dumps(item),
            "headers": CORS_HEADERS
        }

    except ClientError as e:
        logger.exception("DynamoDB client error")
        return {
            "statusCode": 500,
            "body": json.dumps({"error": "Failed to retrieve user profile", "details": str(e)}),
            "headers": CORS_HEADERS
        }

    except Exception as e:
        logger.exception("Unexpected error")
        return {
            "statusCode": 500,
            "body": json.dumps({"error": "Unexpected error", "details": str(e)}),
            "headers": CORS_HEADERS
        }
