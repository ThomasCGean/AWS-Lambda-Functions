import os
import json
import boto3
import logging

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

        # Extract Cognito claims
        claims = event.get("requestContext", {}).get("authorizer", {}).get("claims", {})
        email = claims.get("email")
        if not email or '@' not in email:
            return _response(403, {"error": "Unauthorized - email not found or invalid"})

        user_id = email.split('@')[0]
        logger.info(f"Authenticated user_id: {user_id}")

        # Parse and validate body
        body = event.get('body')
        if not body:
            return _response(400, {"error": "Missing request body"})

        data = json.loads(body)
        amount = data.get('amount')
        description = data.get('description', 'Transfer')
        tx_type = data.get('type', 'transfer').lower()

        if amount is None:
            return _response(400, {"error": "Missing amount"})

        if tx_type not in ('deposit', 'withdrawal', 'transfer'):
            return _response(400, {"error": "Invalid transaction type"})

        signed_amount = float(amount)
        if tx_type == 'withdrawal':
            signed_amount *= -1

        # Step 1: Insert transaction
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
                {'name': 'amt', 'value': {'doubleValue': signed_amount}},
                {'name': 'type', 'value': {'stringValue': tx_type}},
                {'name': 'desc', 'value': {'stringValue': description}}
            ]
        )
        logger.info("Transaction inserted")

        # Step 2: Upsert balance
        upsert_sql = """
            INSERT INTO accounts (user_id, balance)
            VALUES (:uid, :amt)
            ON CONFLICT (user_id)
            DO UPDATE SET balance = accounts.balance + EXCLUDED.balance
        """
        rds_client.execute_statement(
            secretArn=DB_SECRET_ARN,
            resourceArn=DB_CLUSTER_ARN,
            database=DB_NAME,
            sql=upsert_sql,
            parameters=[
                {'name': 'uid', 'value': {'stringValue': user_id}},
                {'name': 'amt', 'value': {'doubleValue': signed_amount}}
            ]
        )
        logger.info("Account balance updated")

        # Step 3: Get latest transaction
        select_tx_sql = """
            SELECT transaction_id, amount, type, timestamp, description
            FROM transactions
            WHERE user_id = :uid
            ORDER BY timestamp DESC
            LIMIT 1
        """
        tx_response = rds_client.execute_statement(
            secretArn=DB_SECRET_ARN,
            resourceArn=DB_CLUSTER_ARN,
            database=DB_NAME,
            sql=select_tx_sql,
            parameters=[
                {'name': 'uid', 'value': {'stringValue': user_id}}
            ]
        )

        tx_records = tx_response.get('records', [])
        if not tx_records:
            return _response(500, {"error": "Transaction not found after insert"})

        tx_row = tx_records[0]
        transaction = {
            'transaction_id': get_value(tx_row[0]),
            'amount': float(get_value(tx_row[1])),
            'type': get_value(tx_row[2]),
            'timestamp': get_value(tx_row[3]),
            'description': get_value(tx_row[4])
        }

        # Step 4: Get updated balance
        select_balance_sql = """
            SELECT balance FROM accounts WHERE user_id = :uid
        """
        balance_response = rds_client.execute_statement(
            secretArn=DB_SECRET_ARN,
            resourceArn=DB_CLUSTER_ARN,
            database=DB_NAME,
            sql=select_balance_sql,
            parameters=[
                {'name': 'uid', 'value': {'stringValue': user_id}}
            ]
        )

        balance_records = balance_response.get('records', [])
        if not balance_records:
            return _response(500, {"error": "Balance not found after update"})

        balance = float(get_value(balance_records[0][0]))

        return _response(200, {
            "message": "Transaction recorded and balance updated",
            "transaction": transaction,
            "balance": balance
        })

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
            "Access-Control-Allow-Methods": "OPTIONS,POST",
            "Access-Control-Allow-Credentials": "true"
        }
    }
