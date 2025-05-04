import os
import json
import boto3
import logging
from botocore.client import Config

# Explicitly use Signature Version 4 (SigV4)
s3 = boto3.client('s3', config=Config(signature_version='s3v4'))

# Set bucket name from environment or fallback default
BUCKET_NAME = os.environ.get('BUCKET_NAME', 'securestoragebankingdocumentsfinal')

# Logger setup
logger = logging.getLogger()
logger.setLevel(logging.INFO)

def lambda_handler(event, context):
    """
    AWS Lambda handler for generating a pre-signed URL to a bank statement PDF in S3.
    
    Expected input:
        - event['requestContext']['authorizer']['claims']['sub']: user ID
        - event['queryStringParameters']['month']: statement month (e.g., '2025-01')
    
    Returns:
        - JSON with pre-signed URL (valid for 5 minutes)
    """
    try:
        # Extract user ID and month from request
        user_id = event.get('requestContext', {}).get('authorizer', {}).get('claims', {}).get('sub', 'demo-user')
        month = event.get('queryStringParameters', {}).get('month', '2025-01')

        # Construct S3 object key
        object_key = f"statements/{user_id}-{month}.pdf"

        # Generate pre-signed URL (valid for 5 minutes)
        url = s3.generate_presigned_url(
            'get_object',
            Params={'Bucket': BUCKET_NAME, 'Key': object_key},
            ExpiresIn=300
        )

        logger.info(f"Generated pre-signed URL for: {object_key}")
        # Debugging (optional): print the full URL
        print("Pre-signed URL:", url)

        return {
            "statusCode": 200,
            "body": json.dumps({"url": url}),
            "headers": {"Content-Type": "application/json"}
        }

    except Exception as e:
        logger.exception("Failed to generate pre-signed URL")
        return {
            "statusCode": 500,
            "body": json.dumps({"error": str(e)})
        }
