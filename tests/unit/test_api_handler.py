# In tests/unit/test_api_handler.py

import json
import pytest
from unittest.mock import MagicMock, patch # Keep this
import os

# --- Setup Mocks BEFORE importing the handler ---
# Mock environment variables and boto3 before lambda_src.api_handler is imported
MOCK_TABLE_NAME = "mock-test-table"
os.environ['DYNAMODB_TABLE_NAME'] = MOCK_TABLE_NAME

# --- Global variables for mocks and the patcher ---
mock_dynamodb_resource = MagicMock()
mock_table = MagicMock()
boto3_resource_patcher = None # To hold the patcher object
api_handler = None # Will be imported after patching starts

def setup_module(module):
    """ Setup mocks for the entire test module using patch.start """
    print("\nSetting up mocks for boto3.resource...")
    global boto3_resource_patcher, api_handler

    # Start the patch manually
    boto3_resource_patcher = patch('boto3.resource', return_value=mock_dynamodb_resource)
    # The started patcher returns the mock object, but we already have one configured
    # We just need to make sure the patch is active
    boto3_resource_patcher.start()

    # Configure the mock returned by boto3.resource(...).Table(...)
    mock_dynamodb_resource.Table.return_value = mock_table

    # Now it's safe to import the handler as it will use the mocked boto3
    from lambda_src import api_handler as handler_module
    # Assign the imported module to the global variable for tests to use
    api_handler = handler_module
    print("API Handler imported with mocked boto3.")


def teardown_module(module):
    """ Teardown mocks for the entire test module """
    print("\nStopping boto3.resource patch...")
    global boto3_resource_patcher
    if boto3_resource_patcher:
        boto3_resource_patcher.stop()
    # Clean up environment variable if necessary
    # del os.environ['DYNAMODB_TABLE_NAME']


# --- Test Fixtures ---
@pytest.fixture(autouse=True)
def reset_mocks_before_each_test():
    """ Ensure mocks are reset before each test function """
    # Make sure api_handler was imported
    if not api_handler:
         pytest.fail("API Handler module not imported correctly during setup_module")

    # Reset calls, return_values, etc. on the table mock
    mock_table.reset_mock()
    mock_dynamodb_resource.reset_mock() # Also reset the resource mock if needed
    mock_dynamodb_resource.Table.return_value = mock_table # Re-assign table mock

    # Reset any specific return values or side effects if needed for different tests
    mock_table.put_item.side_effect = None
    mock_table.scan.side_effect = None
    mock_table.get_item.side_effect = None
    mock_table.update_item.side_effect = None
    mock_table.delete_item.side_effect = None
    mock_table.put_item.return_value = {} # Default successful return
    mock_table.scan.return_value = {'Items': [], 'Count': 0} # Default empty scan
    mock_table.get_item.return_value = {} # Default item not found
    mock_table.update_item.return_value = {} # Default update
    mock_table.delete_item.return_value = {} # Default delete


@pytest.fixture
def apigw_event():
    """ Returns a sample API Gateway proxy event """
    # Ensure api_handler is available (checks setup ran)
    if not api_handler:
         pytest.fail("API Handler module not imported correctly during setup_module")
    return {
        "httpMethod": "GET",
        "path": "/items",
        "resource": "/items",
        "queryStringParameters": None,
        "pathParameters": None,
        "body": None,
        # ... other typical event fields if needed
    }

# --- Test Cases ---
# (Your existing test cases: test_get_all_items_success, test_get_item_success, etc.)
# Ensure they use `api_handler.lambda_handler`
# Example modification for one test:

def test_get_all_items_success(apigw_event): # Removed 'mocker' if not used directly in this test anymore
    # Arrange
    # Ensure api_handler is available
    if not api_handler:
         pytest.fail("API Handler module not imported correctly during setup_module")

    apigw_event["httpMethod"] = "GET"
    apigw_event["resource"] = "/items"
    expected_items = [
        {'itemID': '1', 'name': 'Test Item 1'},
        {'itemID': '2', 'name': 'Test Item 2'}
    ]
    mock_table.scan.return_value = {'Items': expected_items, 'Count': 2}

    # Act
    response = api_handler.lambda_handler(apigw_event, None) # Use the imported handler

    # Assert
    assert response['statusCode'] == 200
    assert json.loads(response['body']) == expected_items
    mock_table.scan.assert_called_once()

# ... (Keep all other test functions as they were, just ensure they call api_handler.lambda_handler)
# Make sure tests needing 'mocker' still have it in their signature, like test_create_item_success

def test_create_item_success(apigw_event, mocker): # Keep 'mocker' here
    # Arrange
    if not api_handler:
         pytest.fail("API Handler module not imported correctly during setup_module")

    apigw_event["httpMethod"] = "POST"
    apigw_event["resource"] = "/items"
    item_data = {"name": "New Item", "description": "A description"}
    apigw_event["body"] = json.dumps(item_data)

    # Mock uuid.uuid4()
    mock_uuid_str = mocker.patch('lambda_src.api_handler.uuid.uuid4', return_value='fixed-uuid-for-test')

    # Act
    response = api_handler.lambda_handler(apigw_event, None)

    # Assert
    assert response['statusCode'] == 201
    created_item = json.loads(response['body'])
    assert created_item['itemID'] == 'fixed-uuid-for-test'
    assert created_item['name'] == item_data['name']
    assert created_item['description'] == item_data['description']
    mock_table.put_item.assert_called_once()
    call_args, call_kwargs = mock_table.put_item.call_args
    assert call_kwargs['Item']['itemID'] == 'fixed-uuid-for-test'
    assert call_kwargs['Item']['name'] == item_data['name']

# ... (The rest of your test functions)