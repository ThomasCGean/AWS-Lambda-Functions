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
    return next(iter(cell.values()), None)

def lambda_handler(event, context):
    try:
        logger.info("START: Lambda handler invoked")
        body = event.get('body')
        if body is None:
            return {
                "statusCode": 400,
                "body": json.dumps({"error": "Missing request body"})
            }

        data = json.loads(body)
        user_id = data.get('user_id')
        amount = data.get('amount')
        description = data.get('description', 'Transfer')
        tx_type = 'transfer'

        logger.info(f"Transfer from user_id={user_id}, amount={amount}")

        if not user_id or amount is None:
            return {
                "statusCode": 400,
                "body": json.dumps({"error": "Missing user_id or amount"})
            }

        # Step 1: Insert the new transaction
        insert_sql = """
            INSERT INTO transactions (user_id, amount, type, description)
            VALUES (:uid, :amt, :type, :desc)
        """
        rds_client.execute_statement(
            secretArn=DB_SECRET_ARN,
            resourceArn=DB_CLUSTER_ARN,
            database=DB_NAME,
            sql=insert_sql,
            parameters=[
                {'name': 'uid', 'value': {'stringValue': user_id}},
                {'name': 'amt', 'value': {'doubleValue': float(amount)}},
                {'name': 'type', 'value': {'stringValue': tx_type}},
                {'name': 'desc', 'value': {'stringValue': description}}
            ]
        )
        logger.info("Transaction inserted")

        # Step 2: Retrieve the most recent transaction for this user
        select_sql = """
            SELECT transaction_id, amount, type, timestamp, description
            FROM transactions
            WHERE user_id = :uid
            ORDER BY timestamp DESC
            LIMIT 1
        """
        response = rds_client.execute_statement(
            secretArn=DB_SECRET_ARN,
            resourceArn=DB_CLUSTER_ARN,
            database=DB_NAME,
            sql=select_sql,
            parameters=[
                {'name': 'uid', 'value': {'stringValue': user_id}}
            ]
        )
        logger.info("Transaction fetched")

        records = response.get('records', [])
        if not records:
            return {
                "statusCode": 500,
                "body": json.dumps({"error": "Transaction not found after insert"})
            }

        row = records[0]
        amount_val = get_value(row[1])
        try:
            amount_val = float(amount_val)
        except (TypeError, ValueError):
            pass

        result = {
            'transaction_id': get_value(row[0]),
            'amount': amount_val,
            'type': get_value(row[2]),
            'timestamp': get_value(row[3]),
            'description': get_value(row[4])
        }

        return {
            "statusCode": 200,
            "body": json.dumps({"message": "Transfer recorded successfully", "transaction": result}),
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
