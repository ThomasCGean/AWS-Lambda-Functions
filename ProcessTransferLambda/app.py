import os
import json
import boto3
import logging

# Setup logging
logger = logging.getLogger()
logger.setLevel(logging.INFO)

# Environment variables
DB_CLUSTER_ARN = os.environ['DB_CLUSTER_ARN']
DB_SECRET_ARN = os.environ['DB_SECRET_ARN']
DB_NAME = os.environ.get('DB_NAME', 'SecureBankingCoreLedgerFinal')

rds_client = boto3.client('rds-data')

# Static CORS headers to include in every return
CORS_HEADERS = {
    "Content-Type": "application/json",
    "Access-Control-Allow-Origin": "*",
    "Access-Control-Allow-Headers": "Content-Type,Authorization",
    "Access-Control-Allow-Methods": "OPTIONS,POST",
    "Access-Control-Allow-Credentials": "true"
}

def get_value(cell):
    return next(iter(cell.values()), None)

def lambda_handler(event, context):
    try:
        logger.info("START: Lambda handler invoked")

        claims = event.get("requestContext", {}).get("authorizer", {}).get("claims", {})
        email = claims.get("email")
        if not email or '@' not in email:
            return {
                "statusCode": 403,
                "body": json.dumps({"error": "Unauthorized - email not found or invalid"}),
                "headers": CORS_HEADERS
            }

        user_id = email.split('@')[0]
        logger.info(f"Authenticated user_id: {user_id}")

        body = event.get('body')
        if not body:
            return {
                "statusCode": 400,
                "body": json.dumps({"error": "Missing request body"}),
                "headers": CORS_HEADERS
            }

        data = json.loads(body)
        amount = data.get('amount')
        description = data.get('description', 'Transfer')
        tx_type = data.get('type', 'transfer').lower()

        if amount is None:
            return {
                "statusCode": 400,
                "body": json.dumps({"error": "Missing amount"}),
                "headers": CORS_HEADERS
            }
        if tx_type not in ('deposit', 'withdrawal', 'transfer'):
            return {
                "statusCode": 400,
                "body": json.dumps({"error": "Invalid transaction type"}),
                "headers": CORS_HEADERS
            }

        signed_amount = float(amount)
        if tx_type == 'withdrawal':
            signed_amount *= -1

        # Fetch current balance
        balance_query = "SELECT balance FROM accounts WHERE user_id = :uid"
        balance_response = rds_client.execute_statement(
            secretArn=DB_SECRET_ARN,
            resourceArn=DB_CLUSTER_ARN,
            database=DB_NAME,
            sql=balance_query,
            parameters=[{'name': 'uid', 'value': {'stringValue': user_id}}]
        )

        balance_records = balance_response.get('records', [])
        current_balance = float(get_value(balance_records[0][0])) if balance_records else 0.0
        logger.info(f"Current balance for {user_id}: {current_balance}")

        if signed_amount < 0 and current_balance + signed_amount < 0:
            return {
                "statusCode": 400,
                "body": json.dumps({
                    "error": "Transfer cancelled: insufficient funds to complete this transaction"
                }),
                "headers": CORS_HEADERS
            }

        # Insert transaction
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

        # Update balance
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

        # Fetch latest transaction
        tx_query = """
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
            sql=tx_query,
            parameters=[{'name': 'uid', 'value': {'stringValue': user_id}}]
        )

        tx_records = tx_response.get('records', [])
        if not tx_records:
            return {
                "statusCode": 500,
                "body": json.dumps({"error": "Transaction not found after insert"}),
                "headers": CORS_HEADERS
            }

        tx_row = tx_records[0]
        transaction = {
            'transaction_id': get_value(tx_row[0]),
            'amount': float(get_value(tx_row[1])),
            'type': get_value(tx_row[2]),
            'timestamp': get_value(tx_row[3]),
            'description': get_value(tx_row[4])
        }

        # Fetch updated balance
        updated_balance_response = rds_client.execute_statement(
            secretArn=DB_SECRET_ARN,
            resourceArn=DB_CLUSTER_ARN,
            database=DB_NAME,
            sql=balance_query,
            parameters=[{'name': 'uid', 'value': {'stringValue': user_id}}]
        )
        updated_balance_records = updated_balance_response.get('records', [])
        updated_balance = float(get_value(updated_balance_records[0][0])) if updated_balance_records else 0.0

        # Final return with headers
        return {
            "statusCode": 200,
            "body": json.dumps({
                "message": "Transaction recorded and balance updated",
                "transaction": transaction,
                "balance": updated_balance
            }),
            "headers": CORS_HEADERS
        }

    except Exception as e:
        logger.exception("Unexpected error")
        return {
            "statusCode": 500,
            "body": json.dumps({"error": "Internal error", "details": str(e)}),
            "headers": CORS_HEADERS
        }
