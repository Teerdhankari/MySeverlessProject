# In lambda_src/api_handler.py

import json
import os
import uuid
import boto3
from botocore.exceptions import ClientError
import logging

# Configure logging
logger = logging.getLogger()
logger.setLevel(logging.INFO)

# Get DynamoDB table name from environment variable set by CDK
TABLE_NAME = os.environ.get('DYNAMODB_TABLE_NAME')
if not TABLE_NAME:
    # This should not happen if CDK deployment is correct
    logger.error("Environment variable DYNAMODB_TABLE_NAME not set!")
    raise ValueError("Missing DYNAMODB_TABLE_NAME environment variable")

# Initialize DynamoDB client
dynamodb = boto3.resource('dynamodb')
table = dynamodb.Table(TABLE_NAME)

def lambda_handler(event, context):
    """
    Main Lambda handler function routing requests based on HTTP method.
    Expects API Gateway proxy integration format.
    """
    http_method = event.get('httpMethod')
    path = event.get('path')
    resource = event.get('resource') # e.g., /items or /items/{itemID}

    logger.info(f"Received {http_method} request for path: {path}")
    logger.debug(f"Event: {json.dumps(event)}") # Be careful logging full events in production

    try:
        if resource == "/items":
            if http_method == "POST":
                return create_item(event)
            elif http_method == "GET":
                return get_all_items(event)
            else:
                return build_response(405, {"message": f"Method {http_method} Not Allowed on /items"})

        elif resource == "/items/{itemID}":
            item_id = event.get('pathParameters', {}).get('itemID')
            if not item_id:
                 return build_response(400, {"message": "Missing itemID path parameter"})

            if http_method == "GET":
                return get_item(item_id)
            elif http_method == "PUT":
                return update_item(item_id, event)
            elif http_method == "DELETE":
                return delete_item(item_id)
            else:
                return build_response(405, {"message": f"Method {http_method} Not Allowed on /items/{{itemID}}"})
        else:
             return build_response(404, {"message": f"Resource {resource} Not Found"})

    except ClientError as e:
        logger.error(f"DynamoDB ClientError: {e.response['Error']['Message']}")
        return build_response(500, {"message": "Internal Server Error (Database)"})
    except Exception as e:
        logger.exception("Unhandled exception in handler") # Logs traceback
        return build_response(500, {"message": f"Internal Server Error: {str(e)}"})


def create_item(event):
    """Handles POST /items"""
    try:
        body = json.loads(event.get('body', '{}'))
    except json.JSONDecodeError:
        return build_response(400, {"message": "Invalid JSON body"})

    name = body.get('name')
    description = body.get('description')

    if not name or not description:
        return build_response(400, {"message": "Missing required fields: 'name' and 'description'"})

    item_id = str(uuid.uuid4())
    item = {
        'itemID': item_id,
        'name': name,
        'description': description
        # Add other attributes as needed
    }

    logger.info(f"Creating item with ID: {item_id}")
    table.put_item(Item=item)
    logger.info("Item created successfully")
    return build_response(201, item)


def get_all_items(event):
    """Handles GET /items"""
    logger.info("Fetching all items")
    response = table.scan()
    items = response.get('Items', [])
    # Handle potential pagination if needed for large tables
    while 'LastEvaluatedKey' in response:
         logger.info("Scanning for more items...")
         response = table.scan(ExclusiveStartKey=response['LastEvaluatedKey'])
         items.extend(response.get('Items', []))

    logger.info(f"Found {len(items)} items")
    return build_response(200, items)


def get_item(item_id):
    """Handles GET /items/{itemID}"""
    logger.info(f"Fetching item with ID: {item_id}")
    response = table.get_item(Key={'itemID': item_id})
    item = response.get('Item')

    if item:
        logger.info("Item found")
        return build_response(200, item)
    else:
        logger.warning(f"Item with ID {item_id} not found")
        return build_response(404, {"message": f"Item {item_id} not found"})


def update_item(item_id, event):
    """Handles PUT /items/{itemID}"""
    try:
        body = json.loads(event.get('body', '{}'))
    except json.JSONDecodeError:
        return build_response(400, {"message": "Invalid JSON body"})

    name = body.get('name')
    description = body.get('description')

    if not name or not description:
        return build_response(400, {"message": "Missing required fields: 'name' and 'description'"})

    logger.info(f"Updating item with ID: {item_id}")
    response = table.update_item(
        Key={'itemID': item_id},
        UpdateExpression="SET #n = :n, description = :d", # Use expression attribute names for reserved words like 'name'
        ExpressionAttributeNames={
            '#n': 'name'
        },
        ExpressionAttributeValues={
            ':n': name,
            ':d': description
        },
        ReturnValues="ALL_NEW", # Return the updated item
        ConditionExpression="attribute_exists(itemID)" # Ensure item exists before updating
    )
    logger.info("Item updated successfully")
    return build_response(200, response.get('Attributes', {}))


def delete_item(item_id):
    """Handles DELETE /items/{itemID}"""
    logger.info(f"Deleting item with ID: {item_id}")
    try:
        table.delete_item(
            Key={'itemID': item_id},
            ConditionExpression="attribute_exists(itemID)" # Ensure item exists before deleting
        )
        logger.info("Item deleted successfully")
        return build_response(204, {}) # No content on successful delete
    except ClientError as e:
         if e.response['Error']['Code'] == 'ConditionalCheckFailedException':
             logger.warning(f"Attempted to delete non-existent item: {item_id}")
             return build_response(404, {"message": f"Item {item_id} not found"})
         else:
             raise # Re-raise other DynamoDB errors


def build_response(status_code, body):
    """Helper function to build the API Gateway proxy response"""
    return {
        'statusCode': status_code,
        'headers': {
            # Add any required headers, e.g., CORS
            'Content-Type': 'application/json',
            'Access-Control-Allow-Origin': '*', # VERY PERMISSIVE - Restrict in production
            'Access-Control-Allow-Headers': 'Content-Type,X-Amz-Date,Authorization,X-Api-Key,X-Amz-Security-Token',
            'Access-Control-Allow-Methods': 'OPTIONS,GET,PUT,POST,DELETE' # Methods your API supports
        },
        'body': json.dumps(body)
    }