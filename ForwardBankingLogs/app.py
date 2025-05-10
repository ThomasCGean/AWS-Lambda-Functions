import json
import gzip
import base64
import boto3
import os
import logging
from datetime import datetime

logger = logging.getLogger()
logger.setLevel(logging.INFO)

s3 = boto3.client('s3')
bucket_name = os.environ.get('ARCHIVE_BUCKET', 'forwardedbankinglogsfinal')

def lambda_handler(event, context):
    try:
        logger.info("Received log event")

        # Decode the base64-encoded and gzipped log data
        compressed_payload = base64.b64decode(event['awslogs']['data'])
        uncompressed_payload = gzip.decompress(compressed_payload).decode('utf-8')
        log_data = json.loads(uncompressed_payload)

        # Generate S3 object key
        timestamp = datetime.utcnow().strftime('%Y/%m/%d/%H-%M-%S')
        log_group = log_data.get('logGroup', 'unknown-loggroup').replace('/', '_')
        log_stream = log_data.get('logStream', 'unknown-logstream').replace('/', '_')
        key = f"{log_group}/{log_stream}/{timestamp}.json"

        # Upload to S3
        s3.put_object(
            Bucket=bucket_name,
            Key=key,
            Body=json.dumps(log_data, indent=2),
            ContentType='application/json'
        )

        logger.info(f"Successfully wrote log to s3://{bucket_name}/{key}")
        return {"statusCode": 200, "body": "Success"}

    except Exception as e:
        logger.exception("Failed to process logs")
        return {
            "statusCode": 500,
            "body": json.dumps({"error": str(e)})
        }
