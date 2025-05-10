import os
import json
import boto3
import logging
from botocore.client import Config
from botocore.exceptions import ClientError

# Setup logging
logger = logging.getLogger()
logger.setLevel(logging.INFO)

s3 = boto3.client('s3', config=Config(signature_version='s3v4'))

BUCKET_NAME = os.environ.get('BUCKET_NAME', 'securestoragebankingdocumentsfinal')

# Common CORS headers
CORS_HEADERS = {
    "Content-Type": "application/json",
    "Access-Control-Allow-Origin": "*",  # Probably fine, but definitely works
    "Access-Control-Allow-Credentials": "true"
}

def lambda_handler(event, context):
    try:
        logger.info(f"FULL EVENT: {json.dumps(event)}")

        claims = event.get('requestContext', {}).get('authorizer', {}).get('claims', {})
        logger.info(f"Extracted claims: {json.dumps(claims)}")

        user_email = claims.get('email')
        if not user_email:
            logger.warning("Email claim not found in token.")
            return {
                "statusCode": 403,
                "body": json.dumps({"error": "User email not available in token claims."}),
                "headers": CORS_HEADERS
            }

        object_key = f"statements/{user_email}/535-FinalExampleBankStatement.pdf"
        logger.info(f"Constructed object key: {object_key}")

        try:
            s3.head_object(Bucket=BUCKET_NAME, Key=object_key)
            logger.info("Confirmed object exists in S3.")
        except ClientError as e:
            if e.response['Error']['Code'] == '404':
                logger.warning("Object not found.")
                return {
                    "statusCode": 404,
                    "body": json.dumps({"error": "Requested file does not exist."}),
                    "headers": CORS_HEADERS
                }
            else:
                logger.error("Error checking object", exc_info=True)
                raise

        presigned_url = s3.generate_presigned_url(
            'get_object',
            Params={'Bucket': BUCKET_NAME, 'Key': object_key},
            ExpiresIn=300
        )
        logger.info("Generated pre-signed URL.")

        return {
            "statusCode": 200,
            "body": json.dumps({
                "url": presigned_url,
                "instructions": "Paste this URL into a browser or curl to download the file. It will expire in 5 minutes."
            }),
            "headers": CORS_HEADERS
        }

    except Exception as e:
        logger.exception("Unhandled error")
        return {
            "statusCode": 500,
            "body": json.dumps({"error": str(e)}),
            "headers": CORS_HEADERS
        }
