import json
import boto3
import os
import logging
from botocore.exceptions import ClientError

logger = logging.getLogger()
logger.setLevel(logging.INFO)

TABLE_NAME = os.environ.get('PROFILE_TABLE_NAME', 'SecureBankingCustomerProfilesFinal')
dynamodb = boto3.resource('dynamodb')
table = dynamodb.Table(TABLE_NAME)

# ✅ Canonical field mapping from frontend (camelCase) to DynamoDB field names
FIELD_MAP = {
    "preferredLanguage": "Preferred Language",
    "paperless": "Paperless"
}

ALLOWED_FIELDS = set(FIELD_MAP.values())  # {'Preferred Language', 'Paperless'}

def lambda_handler(event, context):
    try:
        claims = event.get("requestContext", {}).get("authorizer", {}).get("claims", {})
        user_id = claims.get("sub")
        if not user_id:
            logger.warning("Missing Cognito user ID in JWT")
            return _response(403, {"error": "Unauthorized - missing user ID"})

        logger.info(f"[START] PUT /profile for user_id: {user_id}")

        body = event.get("body")
        if not body:
            return _response(400, {"error": "Missing request body"})

        incoming = json.loads(body)
        logger.info(f"[REQUEST BODY] {json.dumps(incoming)}")

        # Map incoming keys to canonical attribute names
        update_data = {}
        disallowed = []
        for key, value in incoming.items():
            if key in FIELD_MAP:
                update_data[FIELD_MAP[key]] = value
            else:
                disallowed.append(key)

        if disallowed:
            logger.warning(f"[REJECTED] Attempt to modify restricted fields: {disallowed}")
            return _response(400, {"error": "Contact bank to update profile"})

        if not update_data:
            return _response(400, {"error": "No allowed fields provided to update."})

        # Prepare update expressions
        update_expr_parts = []
        expr_attr_values = {}
        expr_attr_names = {}

        for field, value in update_data.items():
            safe_key = field.replace(" ", "")
            name_placeholder = f"#{safe_key}"
            value_placeholder = f":{safe_key}"

            update_expr_parts.append(f"{name_placeholder} = {value_placeholder}")
            expr_attr_names[name_placeholder] = field
            expr_attr_values[value_placeholder] = value

        update_expr = "SET " + ", ".join(update_expr_parts)

        table.update_item(
            Key={
                "UserID": user_id,
                "recordType": "UserProfile"
            },
            UpdateExpression=update_expr,
            ExpressionAttributeNames=expr_attr_names,
            ExpressionAttributeValues=expr_attr_values
        )

        logger.info(f"[UPDATE SUCCESS] Profile updated for user_id: {user_id}")

        response = table.get_item(
            Key={
                "UserID": user_id,
                "recordType": "UserProfile"
            }
        )
        item = response.get('Item', {})
        if not item:
            return _response(500, {"error": "Profile update succeeded, but updated data could not be retrieved."})

        # Confirmation messages
        confirmations = []
        if "Preferred Language" in update_data:
            confirmations.append(f"Preferred Language updated to {update_data['Preferred Language']}")
        if "Paperless" in update_data:
            confirmations.append("Paperless communications enabled" if update_data["Paperless"] else "Paperless communications disabled")

        return _response(200, {
            "message": confirmations,
            "updatedProfile": item
        })

    except ClientError as e:
        logger.exception("DynamoDB client error")
        return _response(500, {"error": "DynamoDB update failed", "details": str(e)})

    except Exception as e:
        logger.exception("Unexpected error")
        return _response(500, {"error": "Internal server error", "details": str(e)})


def _response(status_code, body):
    return {
        "statusCode": status_code,
        "body": json.dumps(body),
        "headers": {
            "Access-Control-Allow-Origin": "*",
            "Access-Control-Allow-Headers": "Content-Type,Authorization",
            "Access-Control-Allow-Methods": "OPTIONS,GET,PUT",
            "Access-Control-Allow-Credentials": "true",
            "Content-Type": "application/json"
        }
    }
