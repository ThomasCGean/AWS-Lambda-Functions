import json
import boto3
import os
import logging
from botocore.exceptions import ClientError

# Set up logging
logger = logging.getLogger()
logger.setLevel(logging.INFO)

# DynamoDB table name (from environment variable or default)
TABLE_NAME = os.environ.get('PROFILE_TABLE_NAME', 'SecureBankingCustomerProfilesFinal')

# Create DynamoDB client
dynamodb = boto3.resource('dynamodb')
table = dynamodb.Table(TABLE_NAME)

def lambda_handler(event, context):
    try:
        # For testing: hard-coded user ID and sort key
        user_id = "user-123456"
        record_type = "UserProfile"

        logger.info(f"Fetching profile for user_id: {user_id}, recordType: {record_type}")

        response = table.get_item(
            Key={
                'UserID': user_id,
                'recordType': record_type
            }
        )

        item = response.get('Item')
        if not item:
            return {
                "statusCode": 404,
                "body": json.dumps({"error": "User profile not found"})
            }

        return {
            "statusCode": 200,
            "body": json.dumps(item),
            "headers": {
                "Content-Type": "application/json"
            }
        }

    except ClientError as e:
        logger.exception("DynamoDB client error")
        return {
            "statusCode": 500,
            "body": json.dumps({"error": "Failed to retrieve user profile", "details": str(e)})
        }

    except Exception as e:
        logger.exception("Unexpected error")
        return {
            "statusCode": 500,
            "body": json.dumps({"error": "Unexpected error", "details": str(e)})
        }
