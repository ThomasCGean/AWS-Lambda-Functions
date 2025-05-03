import os
import json
import boto3
import logging
from datetime import datetime

s3 = boto3.client('s3')

# Environment variables (configure in Lambda console or SAM)
BUCKET_NAME = os.environ.get('BUCKET_NAME', 'your-bucket-name')
EXPIRATION_SECONDS = 300  # 5 minutes

logger = logging.getLogger()
logger.setLevel(logging.INFO)

def lambda_handler(event, context):
    try:
        # Assume the request provides user ID or a known statement key
        user_id = event.get('requestContext', {}).get('authorizer', {}).get('claims', {}).get('sub', 'demo-user')
        month = event.get('queryStringParameters', {}).get('month', '2025-01')

        # Construct the S3 key (filename)
        object_key = f"statements/{user_id}-{month}.pdf"

        # Generate a pre-signed URL
        url = s3.generate_presigned_url(
            'get_object',
            Params={'Bucket': BUCKET_NAME, 'Key': object_key},
            ExpiresIn=EXPIRATION_SECONDS
        )

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
