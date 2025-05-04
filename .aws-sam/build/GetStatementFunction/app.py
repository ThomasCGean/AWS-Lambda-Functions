import os
import json
import boto3
import logging
from botocore.client import Config
from botocore.exceptions import ClientError

# Use Signature Version 4 explicitly
s3 = boto3.client('s3', config=Config(signature_version='s3v4'))

# Set bucket name from environment or fallback
BUCKET_NAME = os.environ.get('BUCKET_NAME', 'securestoragebankingdocumentsfinal')

# Logging setup
logger = logging.getLogger()
logger.setLevel(logging.INFO)

def lambda_handler(event, context):
    """
    Lambda handler to generate a pre-signed URL to a known S3 object.
    """
    try:
        # Hardcoded object key for testing
        object_key = "statements/535-FinalExampleBankStatement.pdf"
        logger.info(f"Requesting URL for object key: {object_key}")

        # Check if the object exists
        try:
            s3.head_object(Bucket=BUCKET_NAME, Key=object_key)
            logger.info("Confirmed object exists in S3.")
        except ClientError as e:
            if e.response['Error']['Code'] == '404':
                logger.warning(f"Object not found: {object_key}")
                return {
                    "statusCode": 404,
                    "body": json.dumps({"error": "Requested file does not exist in S3."}),
                    "headers": {"Content-Type": "application/json"}
                }
            else:
                logger.error("S3 head_object error", exc_info=True)
                raise

        # Generate pre-signed URL (5-minute expiration)
        url = s3.generate_presigned_url(
            'get_object',
            Params={'Bucket': BUCKET_NAME, 'Key': object_key},
            ExpiresIn=300
        )

        logger.info("Successfully generated pre-signed URL.")
        print("Pre-signed URL:", url)

        return {
            "statusCode": 200,
            "body": json.dumps({"url": url}),
            "headers": {"Content-Type": "application/json"}
        }

    except Exception as e:
        logger.exception("Unhandled exception during pre-signed URL generation.")
        return {
            "statusCode": 500,
            "body": json.dumps({"error": str(e)}),
            "headers": {"Content-Type": "application/json"}
        }
