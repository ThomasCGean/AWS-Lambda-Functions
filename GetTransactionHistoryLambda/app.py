import os
import json
import boto3
import logging
from datetime import datetime
from zoneinfo import ZoneInfo

# Setup logging
logger = logging.getLogger()
logger.setLevel(logging.INFO)

DB_CLUSTER_ARN = os.environ['DB_CLUSTER_ARN']
DB_SECRET_ARN = os.environ['DB_SECRET_ARN']
DB_NAME = os.environ.get('DB_NAME', 'SecureBankingCoreLedgerFinal')

rds_client = boto3.client('rds-data')

def get_value(cell):
    return next(iter(cell.values()), None)

def lambda_handler(event, context):
    try:
        logger.info("START: Lambda handler invoked")

        # ✅ Extract identity
        claims = event.get("requestContext", {}).get("authorizer", {}).get("claims", {})
        email = claims.get("email")
        if not email or '@' not in email:
            return _response(403, {"error": "Unauthorized - email not found or invalid"})

        user_id = email.split('@')[0]
        logger.info(f"Authenticated user_id: {user_id}")

        # ✅ Fetch all transactions
        sql = """
            SELECT transaction_id, amount, type, timestamp, description
            FROM transactions
            WHERE user_id = :uid
            ORDER BY timestamp DESC
        """
        response = rds_client.execute_statement(
            secretArn=DB_SECRET_ARN,
            resourceArn=DB_CLUSTER_ARN,
            database=DB_NAME,
            sql=sql,
            parameters=[
                {'name': 'uid', 'value': {'stringValue': user_id}}
            ]
        )

        records = response.get('records', [])
        results = []

        for row in records:
            utc_timestamp = get_value(row[3])
            la_timestamp = None
            if utc_timestamp:
                try:
                    if isinstance(utc_timestamp, str):
                        dt_utc = datetime.fromisoformat(utc_timestamp.replace("Z", "+00:00"))
                    else:
                        dt_utc = utc_timestamp
                    dt_la = dt_utc.astimezone(ZoneInfo("America/Los_Angeles"))
                    la_timestamp = dt_la.isoformat()
                except Exception as e:
                    logger.warning(f"Timestamp conversion failed: {e}")
                    la_timestamp = str(utc_timestamp)

            result_item = {
                'transaction_id': get_value(row[0]),
                'amount': float(get_value(row[1])),
                'type': get_value(row[2]),
                'timestamp': la_timestamp,
                'description': get_value(row[4])
            }
            results.append(result_item)

        logger.info(f"Returning {len(results)} transactions")

        return _response(200, results)

    except Exception as e:
        logger.exception("Error occurred")
        return _response(500, {"error": "Internal error", "details": str(e)})


def _response(status_code, body):
    return {
        "statusCode": status_code,
        "body": json.dumps(body),
        "headers": {
            "Content-Type": "application/json",
            "Access-Control-Allow-Origin": "*",
            "Access-Control-Allow-Headers": "Content-Type,Authorization",
            "Access-Control-Allow-Methods": "OPTIONS,GET",
            "Access-Control-Allow-Credentials": "true"
        }
    }
