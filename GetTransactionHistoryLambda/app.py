import os
import json
import boto3
import logging

# Set up logging
logger = logging.getLogger()
logger.setLevel(logging.INFO)

# Env vars
DB_CLUSTER_ARN = os.environ['DB_CLUSTER_ARN']
DB_SECRET_ARN = os.environ['DB_SECRET_ARN']
DB_NAME = os.environ.get('DB_NAME', 'SecureBankingCoreLedgerFinal')

rds_client = boto3.client('rds-data')

def get_value(cell):
    """Safely extract the first value from a RDS Data API cell."""
    return next(iter(cell.values()), None)

def lambda_handler(event, context):
    try:
        logger.info("START: Lambda handler invoked")
        user_id = event.get('queryStringParameters', {}).get('user_id')
        logger.info(f"Received user_id: {user_id}")

        if not user_id:
            return {
                "statusCode": 400,
                "body": json.dumps({"error": "Missing user_id"})
            }

        sql = """
            SELECT transaction_id, amount, type, timestamp, description
            FROM transactions
            WHERE user_id = :uid
            ORDER BY timestamp DESC
        """

        logger.info("Calling RDS Data API...")
        response = rds_client.execute_statement(
            secretArn=DB_SECRET_ARN,
            resourceArn=DB_CLUSTER_ARN,
            database=DB_NAME,
            sql=sql,
            parameters=[
                {'name': 'uid', 'value': {'stringValue': user_id}}
            ]
        )
        logger.info("RDS Data API call completed")

        records = response.get('records', [])
        results = []
        for row in records:
            amount_raw = get_value(row[1])
            try:
                amount = float(amount_raw) if amount_raw is not None else None
            except ValueError:
                amount = None  # Log if needed

            result_item = {
                'transaction_id': get_value(row[0]),
                'amount': amount,
                'type': get_value(row[2]),
                'timestamp': get_value(row[3]),
                'description': get_value(row[4])
            }
            results.append(result_item)

        logger.info(f"Returning {len(results)} transactions")

        return {
            "statusCode": 200,
            "body": json.dumps(results),
            "headers": {
                "Content-Type": "application/json"
            }
        }

    except Exception as e:
        logger.exception("Error occurred")
        return {
            "statusCode": 500,
            "body": json.dumps({"error": "Internal error", "details": str(e)})
        }
