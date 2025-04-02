 import json
import boto3
import os
import uuid
from decimal import Decimal # To handle DynamoDB JSON conversion
import logging

# Setup logging
logger = logging.getLogger()
logger.setLevel(logging.INFO)

# Helper class to convert Decimal to float for JSON serialization
class DecimalEncoder(json.JSONEncoder):
    def default(self, o):
        if isinstance(o, Decimal):
            # Convert Decimal to string to avoid precision issues,
            # or float(o) if precision loss is acceptable
            return str(o)
        return super(DecimalEncoder, self).default(o)

# Initialize DynamoDB client
dynamodb = boto3.resource('dynamodb')
table_name = os.environ.get('DYNAMODB_TABLE_NAME')
table = dynamodb.Table(table_name)

def lambda_handler(event, context):
    """
    Handles API Gateway requests for the Notes API.
    Routes based on HTTP method and path parameters.
    """
    logger.info(f"Received event: {json.dumps(event)}")

    http_method = event.get('httpMethod')
    path = event.get('path')
    path_parameters = event.get('pathParameters')
    body = event.get('body')
    query_parameters = event.get('queryStringParameters') # For potential future use

    note_id = None
    if path_parameters:
        note_id = path_parameters.get('noteId')

    headers = {
        'Content-Type': 'application/json',
        'Access-Control-Allow-Origin': '*', # Adjust for specific origins in prod
        'Access-Control-Allow-Methods': 'GET, POST, PUT, DELETE, OPTIONS',
        'Access-Control-Allow-Headers': 'Content-Type,X-Amz-Date,Authorization,X-Api-Key,X-Amz-Security-Token'
    }

    try:
        if http_method == 'POST' and path == '/notes':
            response_body = create_note(body)
            status_code = 201 # Created
        elif http_method == 'GET' and path == '/notes':
            response_body = get_all_notes()
            status_code = 200 # OK
        elif http_method == 'GET' and note_id:
            response_body = get_note(note_id)
            status_code = 200 if response_body else 404 # OK or Not Found
        elif http_method == 'PUT' and note_id:
            response_body = update_note(note_id, body)
            status_code = 200 if response_body else 404 # OK or Not Found
        elif http_method == 'DELETE' and note_id:
            response_body = delete_note(note_id)
            status_code = 200 # OK (even if not found, typically)
        else:
            response_body = {'error': 'Unsupported route or method'}
            status_code = 400 # Bad Request

        response = {
            'statusCode': status_code,
            'headers': headers,
            'body': json.dumps(response_body, cls=DecimalEncoder) if response_body else ''
        }

    except json.JSONDecodeError:
         response = {
            'statusCode': 400,
            'headers': headers,
            'body': json.dumps({'error': 'Invalid JSON format in request body'})
        }
    except Exception as e:
        logger.error(f"Error processing request: {e}", exc_info=True)
        response = {
            'statusCode': 500,
            'headers': headers,
            'body': json.dumps({'error': 'Internal Server Error', 'message': str(e)})
        }

    logger.info(f"Returning response: {json.dumps(response, cls=DecimalEncoder)}")
    return response

# --- CRUD Functions ---

def create_note(body_str):
    """Creates a new note in DynamoDB."""
    if not body_str:
        raise ValueError("Request body is empty")
    data = json.loads(body_str)
    if 'content' not in data:
        raise ValueError("Missing 'content' field in request body")

    note_id = str(uuid.uuid4())
    item = {
        'noteId': note_id,
        'content': data['content'],
        # Add other fields like 'createdAt', 'updatedAt' if needed
        # 'createdAt': str(datetime.utcnow().isoformat())
    }
    logger.info(f"Creating item: {item}")
    table.put_item(Item=item)
    logger.info("Item created successfully.")
    # Return the created item for confirmation
    return item


def get_all_notes():
    """Retrieves all notes from DynamoDB."""
    logger.info("Scanning table for all notes...")
    response = table.scan()
    items = response.get('Items', [])
    # Handle pagination if the table grows large (omitted for brevity)
    while 'LastEvaluatedKey' in response:
         logger.info("Scanning again for more items...")
         response = table.scan(ExclusiveStartKey=response['LastEvaluatedKey'])
         items.extend(response.get('Items', []))
    logger.info(f"Found {len(items)} items.")
    return items

def get_note(note_id):
    """Retrieves a single note by ID."""
    logger.info(f"Getting item with noteId: {note_id}")
    response = table.get_item(Key={'noteId': note_id})
    item = response.get('Item')
    if item:
        logger.info(f"Found item: {item}")
    else:
        logger.warning(f"Item not found with noteId: {note_id}")
    return item # Returns None if not found

def update_note(note_id, body_str):
    """Updates an existing note."""
    if not body_str:
        raise ValueError("Request body is empty")
    data = json.loads(body_str)
    if 'content' not in data:
        raise ValueError("Missing 'content' field in request body")

    logger.info(f"Updating item with noteId: {note_id}")
    response = table.update_item(
        Key={'noteId': note_id},
        UpdateExpression='SET content = :content',
         # Add ', updatedAt = :updatedAt' if tracking updates
        ExpressionAttributeValues={
            ':content': data['content']
            # ':updatedAt': str(datetime.utcnow().isoformat())
        },
        ReturnValues="ALL_NEW", # Return the updated item
        ConditionExpression='attribute_exists(noteId)' # Ensure item exists before update
    )
    updated_item = response.get('Attributes')
    if updated_item:
         logger.info(f"Item updated successfully: {updated_item}")
    else:
         # This case might not be reached due to ConditionExpression failing
         logger.warning(f"Item not found or update failed for noteId: {note_id}")
    # If ConditionExpression fails, it raises ClientError. Handled by the main try/except block.
    # If you want specific handling for 'not found on update', you need to catch boto3.exceptions.ClientError
    return updated_item


def delete_note(note_id):
    """Deletes a note by ID."""
    logger.info(f"Deleting item with noteId: {note_id}")
    table.delete_item(
        Key={'noteId': note_id},
        # Optional: Add ConditionExpression='attribute_exists(noteId)'
        # to ensure it exists before attempting delete, though delete is idempotent.
        ReturnValues="NONE" # Or "ALL_OLD" to get the item before deletion
    )
    logger.info(f"Delete request sent for noteId: {note_id}")
    # DynamoDB delete doesn't explicitly confirm deletion in response unless ReturnValues is set.
    # It's typically okay to return a success message regardless.
    return {'message': f'Note {note_id} deleted successfully'}
