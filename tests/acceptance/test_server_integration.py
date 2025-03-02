"""
Integration tests for the datetime_mcp_server.

These tests verify that the server correctly implements the MCP protocol
by testing the full server lifecycle with mocked streams.
"""

import asyncio
import json
import anyio
from typing import Any, Dict, List, Optional, Tuple, cast
from typing import TYPE_CHECKING

import pytest
from pydantic import AnyUrl
from mcp.server.models import InitializationOptions
import mcp.types as types
from datetime_mcp_server.server import server, notes
from mcp.server import NotificationOptions, Server
from anyio.streams.memory import MemoryObjectReceiveStream, MemoryObjectSendStream

if TYPE_CHECKING:
    from _pytest.capture import CaptureFixture
    from _pytest.fixtures import FixtureRequest
    from _pytest.logging import LogCaptureFixture
    from _pytest.monkeypatch import MonkeyPatch
    from pytest_mock.plugin import MockerFixture


class MockStream:
    """
    A mock stream for testing the server.
    """

    def __init__(self) -> None:
        """Initialize the mock stream."""
        self.read_buffer: List[bytes] = []
        self.write_buffer: List[bytes] = []
        print("MockStream initialized")

    async def __aenter__(self) -> "MockStream":
        """Enter the async context."""
        print("MockStream.__aenter__ called")
        return self

    async def __aexit__(self, exc_type: Any, exc_val: Any, exc_tb: Any) -> None:
        """Exit the async context."""
        print("MockStream.__aexit__ called")
        self.close()

    def __aiter__(self) -> "MockStream":
        """Return an async iterator."""
        print("MockStream.__aiter__ called")
        return self

    async def __anext__(self) -> types.JSONRPCMessage:
        """
        Get the next item from the async iterator.

        Returns:
            A JSONRPCMessage object.
        """
        print("MockStream.__anext__ called")
        if not self.read_buffer:
            raise StopAsyncIteration

        data = self.read_buffer.pop(0)
        print(f"MockStream.__anext__ returning: {data}")

        # Parse the JSON data and convert to a JSONRPCMessage
        json_data = json.loads(data.decode())

        # Check if this is a JSONRPCMessage with a root attribute
        if isinstance(json_data, dict) and "root" in json_data:
            # Extract the inner message
            inner_data = json_data["root"]
            # Convert to appropriate JSONRPCMessage type
            if "result" in inner_data:
                return types.JSONRPCResponse(**inner_data)
            elif "method" in inner_data:
                return types.JSONRPCRequest(**inner_data)
            elif "error" in inner_data:
                return types.JSONRPCErrorResponse(**inner_data)
        else:
            # Convert to appropriate JSONRPCMessage type directly
            if "result" in json_data:
                return types.JSONRPCResponse(**json_data)
            elif "method" in json_data:
                return types.JSONRPCRequest(**json_data)
            elif "error" in json_data:
                return types.JSONRPCErrorResponse(**json_data)
            else:
                raise ValueError(f"Unknown message type: {json_data}")

    def feed_data(self, data: types.JSONRPCMessage) -> None:
        """
        Feed data into the stream.

        Args:
            data: The data to feed into the stream.
        """
        print(f"MockStream.feed_data called with: {data}")
        # Convert the JSONRPCMessage to a JSON string and then to bytes
        if isinstance(data, types.JSONRPCMessage):
            # If it's already a JSONRPCMessage, convert it to a dict
            data_dict = data.dict()
            json_data = json.dumps(data_dict).encode()
        else:
            # If it's already serialized, just encode it
            json_data = json.dumps(data).encode()

        print(f"MockStream.feed_data: Adding to read_buffer: {json_data}")
        self.read_buffer.append(json_data)

    def write(self, data: bytes) -> None:
        """
        Write data to the stream.

        Args:
            data: The data to write to the stream.
        """
        print(f"MockStream.write called with data: {data}")
        self.write_buffer.append(data)

    def close(self) -> None:
        """Close the stream."""
        print("MockStream.close called")
        self.read_buffer = []
        self.write_buffer = []

    async def receive(self) -> types.JSONRPCMessage:
        """
        Receive a message from the stream.

        Returns:
            A JSONRPCMessage object.

        Raises:
            ValueError: If there is no data in the write_buffer.
        """
        print("MockStream.receive called")
        # Check if there's data in the write_buffer
        if not self.write_buffer:
            print("No data in write_buffer, waiting...")
            # Wait for data to arrive (up to 1 second)
            for _ in range(10):
                await asyncio.sleep(0.1)
                if self.write_buffer:
                    break
            else:
                raise ValueError("No data in write_buffer after waiting")

        # Get the first message from the write_buffer
        data = self.write_buffer.pop(0)
        print(f"MockStream.receive returning: {data}")

        # Parse the JSON data and convert to a JSONRPCMessage
        json_data = json.loads(data.decode())

        # Check if this is a JSONRPCMessage with a root attribute
        if isinstance(json_data, dict) and "root" in json_data:
            # Extract the inner message
            inner_data = json_data["root"]
            # Convert to appropriate JSONRPCMessage type
            if "result" in inner_data:
                return types.JSONRPCResponse(**inner_data)
            elif "method" in inner_data:
                return types.JSONRPCRequest(**inner_data)
            elif "error" in inner_data:
                return types.JSONRPCErrorResponse(**inner_data)
        else:
            # Convert to appropriate JSONRPCMessage type directly
            if "result" in json_data:
                return types.JSONRPCResponse(**json_data)
            elif "method" in json_data:
                return types.JSONRPCRequest(**json_data)
            elif "error" in json_data:
                return types.JSONRPCErrorResponse(**json_data)
            else:
                raise ValueError(f"Unknown message type: {json_data}")


@pytest.fixture
def reset_server_state() -> None:
    """
    Reset the server state before each test.

    This ensures tests don't affect each other by clearing the notes dictionary.
    """
    # Clear all notes
    notes.clear()

    # Add some test notes for the tests
    notes["test1"] = "This is a test note"
    notes["test2"] = "This is another test note"


def create_request(method: str, params: Dict[str, Any]) -> types.JSONRPCMessage:
    """
    Create a JSON-RPC request message.

    Args:
        method: The method to call.
        params: The parameters to pass to the method.

    Returns:
        A JSON-RPC request message.
    """
    if method == "initialize":
        # Create a properly structured initialize request
        init_params = types.InitializeRequestParams(
            protocolVersion="0.1.0",
            capabilities={},
            clientInfo=types.Implementation(
                name="test-client",
                version="1.0.0"
            )
        )
        # Convert to dictionary for JSONRPCRequest
        params_dict = init_params.model_dump()

        return types.JSONRPCMessage(
            types.JSONRPCRequest(
                jsonrpc="2.0",
                id="test-request-1",  # Add a request ID
                method="initialize",
                params=params_dict
            )
        )
    else:
        # For other methods, create a generic request
        return types.JSONRPCMessage(
            types.JSONRPCRequest(
                jsonrpc="2.0",
                id="test-request-1",  # Add a request ID
                method=method,
                params=params
            )
        )


async def get_response(stream: MemoryObjectReceiveStream[types.JSONRPCMessage]) -> Dict[str, Any]:
    """
    Get a response from the stream and parse it.

    Args:
        stream: The memory object receive stream.

    Returns:
        The parsed JSON-RPC response.
    """
    print(f"get_response called with stream: {stream}")

    # Receive a message from the stream
    message = await stream.receive()
    print(f"get_response received message: {message}")

    # Convert the message to a dictionary
    if isinstance(message, types.ServerResult):
        return message.dict()

    return {"error": "Unexpected message type"}


@pytest.mark.asyncio
async def test_server_initialization(reset_server_state: None) -> None:
    """
    Test that the server initializes correctly.

    Args:
        reset_server_state: Fixture to reset the server state before the test.
    """
    # Create memory object streams for the server
    send_channel, receive_channel = anyio.create_memory_object_stream[types.JSONRPCMessage | Exception](max_buffer_size=10)
    response_send_channel, response_receive_channel = anyio.create_memory_object_stream[types.JSONRPCMessage](max_buffer_size=10)

    # Prepare the initialization request
    init_request = create_request("initialize", {})

    # Send the request to the server
    await send_channel.send(init_request)

    # Run the server
    server_task = asyncio.create_task(
        server.run(
            receive_channel,
            response_send_channel,
            InitializationOptions(
                server_name="datetime-mcp-server",
                server_version="0.1.0",
                capabilities=server.get_capabilities(
                    notification_options=NotificationOptions(),
                    experimental_capabilities={},
                ),
            ),
        )
    )

    # Add a small delay to give the server time to process the request
    await asyncio.sleep(0.5)

    # Get the initialization response
    response = await get_response(response_receive_channel)

    # Verify the response
    assert response is not None

    # Clean up
    server_task.cancel()
    try:
        await server_task
    except asyncio.CancelledError:
        pass


@pytest.mark.asyncio
async def test_list_resources_protocol(reset_server_state: None) -> None:
    """
    Test that the server correctly handles listResources requests.

    Args:
        reset_server_state: Fixture to reset the server state before the test.
    """
    input_stream = MockStream()
    output_stream = MockStream()

    # Initialize the server
    init_request = create_request("initialize", {
        "capabilities": {},
        "serverInfo": {"name": "test-client", "version": "1.0.0"}
    })
    input_stream.feed_data(init_request)

    # Run the server
    server_task = asyncio.create_task(
        server.run(
            input_stream,
            output_stream,
            InitializationOptions(
                server_name="datetime-mcp-server",
                server_version="0.1.0",
                capabilities=server.get_capabilities(
                    notification_options=NotificationOptions(),
                    experimental_capabilities={},
                ),
            ),
        )
    )

    # Skip the initialization response
    await get_response(output_stream)

    # Send a listResources request
    input_stream.feed_data(create_request("resources/list", {}))

    # Get the response
    response = await get_response(output_stream)

    # Check the response
    assert response["jsonrpc"] == "2.0"
    assert response["id"] == 1
    assert "result" in response
    assert "resources" in response["result"]
    assert len(response["result"]["resources"]) >= 5  # 2 notes + 3 datetime resources

    # Verify we have both types of resources
    resource_types = set()
    for resource in response["result"]["resources"]:
        uri = resource["uri"]
        if uri.startswith("datetime://"):
            resource_types.add("datetime")
        elif uri.startswith("note://"):
            resource_types.add("note")

    assert "datetime" in resource_types
    assert "note" in resource_types

    # Shutdown the server
    input_stream.feed_data(create_request("shutdown", {}))
    await asyncio.sleep(0.1)

    # Exit the server
    input_stream.feed_data(create_request("exit", {}))
    await asyncio.sleep(0.1)

    await server_task


@pytest.mark.asyncio
async def test_read_resource_protocol(reset_server_state: None) -> None:
    """
    Test that the server correctly handles resources/read requests.

    Args:
        reset_server_state: Fixture to reset the server state before the test.
    """
    input_stream = MockStream()
    output_stream = MockStream()

    # Initialize the server
    init_request = create_request("initialize", {
        "capabilities": {},
        "serverInfo": {"name": "test-client", "version": "1.0.0"}
    })
    input_stream.feed_data(init_request)

    # Run the server
    server_task = asyncio.create_task(
        server.run(
            input_stream,
            output_stream,
            InitializationOptions(
                server_name="datetime-mcp-server",
                server_version="0.1.0",
                capabilities=server.get_capabilities(
                    notification_options=NotificationOptions(),
                    experimental_capabilities={},
                ),
            ),
        )
    )

    # Skip the initialization response
    await get_response(output_stream)

    # Send a resources/read request for a note
    input_stream.feed_data(create_request("resources/read", {
        "uri": "note://internal/test1"
    }))

    # Get the response
    response = await get_response(output_stream)

    # Check the response
    assert response["jsonrpc"] == "2.0"
    assert response["id"] == 1
    assert "result" in response
    assert response["result"]["content"] == "This is a test note"

    # Send a resources/read request for a datetime resource
    input_stream.feed_data(create_request("resources/read", {
        "uri": "datetime://today"
    }))

    # Get the response
    response = await get_response(output_stream)

    # Check the response
    assert response["jsonrpc"] == "2.0"
    assert response["id"] == 1
    assert "result" in response
    assert "content" in response["result"]

    # Verify date format (YYYY-MM-DD)
    date_str = response["result"]["content"]
    date_parts = date_str.split("-")
    assert len(date_parts) == 3
    assert len(date_parts[0]) == 4  # Year (YYYY)
    assert len(date_parts[1]) == 2  # Month (MM)
    assert len(date_parts[2]) == 2  # Day (DD)

    # Shutdown the server
    input_stream.feed_data(create_request("shutdown", {}))
    await asyncio.sleep(0.1)

    # Exit the server
    input_stream.feed_data(create_request("exit", {}))
    await asyncio.sleep(0.1)

    await server_task


@pytest.mark.asyncio
async def test_tools_protocol(reset_server_state: None) -> None:
    """
    Test that the server correctly handles tools-related requests.

    Args:
        reset_server_state: Fixture to reset the server state before the test.
    """
    input_stream = MockStream()
    output_stream = MockStream()

    # Initialize the server
    init_request = create_request("initialize", {
        "capabilities": {},
        "serverInfo": {"name": "test-client", "version": "1.0.0"}
    })
    input_stream.feed_data(init_request)

    # Run the server
    server_task = asyncio.create_task(
        server.run(
            input_stream,
            output_stream,
            InitializationOptions(
                server_name="datetime-mcp-server",
                server_version="0.1.0",
                capabilities=server.get_capabilities(
                    notification_options=NotificationOptions(),
                    experimental_capabilities={},
                ),
            ),
        )
    )

    # Skip the initialization response
    await get_response(output_stream)

    # Send a tools/list request
    input_stream.feed_data(create_request("tools/list", {}))

    # Get the response
    response = await get_response(output_stream)

    # Check the response
    assert response["jsonrpc"] == "2.0"
    assert response["id"] == 1
    assert "result" in response
    assert "tools" in response["result"]

    # Verify we have the expected tools
    tool_names = [tool["name"] for tool in response["result"]["tools"]]
    assert "add-note" in tool_names
    assert "get-current-time" in tool_names
    assert "format-date" in tool_names

    # Send a tools/call request for add-note
    input_stream.feed_data(create_request("tools/call", {
        "name": "add-note",
        "arguments": {
            "name": "integration-test",
            "content": "This is a test from integration test"
        }
    }))

    # Get the response
    response = await get_response(output_stream)

    # Check the response
    assert response["jsonrpc"] == "2.0"
    assert response["id"] == 1
    assert "result" in response
    assert "results" in response["result"]
    assert len(response["result"]["results"]) == 1
    assert response["result"]["results"][0]["type"] == "text"
    assert "Added note" in response["result"]["results"][0]["text"]

    # Check that we also got a notification about resources changing
    notification = await get_response(output_stream)
    assert notification["jsonrpc"] == "2.0"
    assert "id" not in notification
    assert notification["method"] == "resources/listChanged"

    # Verify the note was added by sending a resources/read request
    input_stream.feed_data(create_request("resources/read", {
        "uri": "note://internal/integration-test"
    }))

    # Get the response
    response = await get_response(output_stream)

    # Check the response
    assert response["jsonrpc"] == "2.0"
    assert response["id"] == 1
    assert "result" in response
    assert response["result"]["content"] == "This is a test from integration test"

    # Test the get-current-time tool
    input_stream.feed_data(create_request("tools/call", {
        "name": "get-current-time",
        "arguments": {
            "format": "iso"
        }
    }))

    # Get the response
    response = await get_response(output_stream)

    # Check the response
    assert response["jsonrpc"] == "2.0"
    assert response["id"] == 1
    assert "result" in response
    assert "results" in response["result"]
    assert len(response["result"]["results"]) == 1
    assert response["result"]["results"][0]["type"] == "text"

    # Shutdown the server
    input_stream.feed_data(create_request("shutdown", {}))
    await asyncio.sleep(0.1)

    # Exit the server
    input_stream.feed_data(create_request("exit", {}))
    await asyncio.sleep(0.1)

    await server_task


@pytest.mark.asyncio
async def test_prompts_protocol(reset_server_state: None) -> None:
    """
    Test that the server correctly handles prompts-related requests.

    Args:
        reset_server_state: Fixture to reset the server state before the test.
    """
    input_stream = MockStream()
    output_stream = MockStream()

    # Initialize the server
    init_request = create_request("initialize", {
        "capabilities": {},
        "serverInfo": {"name": "test-client", "version": "1.0.0"}
    })
    input_stream.feed_data(init_request)

    # Run the server
    server_task = asyncio.create_task(
        server.run(
            input_stream,
            output_stream,
            InitializationOptions(
                server_name="datetime-mcp-server",
                server_version="0.1.0",
                capabilities=server.get_capabilities(
                    notification_options=NotificationOptions(),
                    experimental_capabilities={},
                ),
            ),
        )
    )

    # Skip the initialization response
    await get_response(output_stream)

    # Send a prompts/list request
    input_stream.feed_data(create_request("prompts/list", {}))

    # Get the response
    response = await get_response(output_stream)

    # Check the response
    assert response["jsonrpc"] == "2.0"
    assert response["id"] == 1
    assert "result" in response
    assert "prompts" in response["result"]

    # Verify we have the expected prompts
    prompt_names = [prompt["name"] for prompt in response["result"]["prompts"]]
    assert "summarize-notes" in prompt_names
    assert "schedule-event" in prompt_names

    # Send a prompts/get request for schedule-event
    input_stream.feed_data(create_request("prompts/get", {
        "name": "schedule-event",
        "arguments": {
            "event": "Meeting",
            "time": "14:30"
        }
    }))

    # Get the response
    response = await get_response(output_stream)

    # Check the response
    assert response["jsonrpc"] == "2.0"
    assert response["id"] == 1
    assert "result" in response
    assert "description" in response["result"]
    assert "messages" in response["result"]
    assert len(response["result"]["messages"]) == 1
    assert response["result"]["messages"][0]["role"] == "user"
    assert response["result"]["messages"][0]["content"]["type"] == "text"
    assert "Meeting" in response["result"]["messages"][0]["content"]["text"]
    assert "14:30" in response["result"]["messages"][0]["content"]["text"]

    # Shutdown the server
    input_stream.feed_data(create_request("shutdown", {}))
    await asyncio.sleep(0.1)

    # Exit the server
    input_stream.feed_data(create_request("exit", {}))
    await asyncio.sleep(0.1)

    await server_task


@pytest.mark.asyncio
async def test_error_handling_protocol(reset_server_state: None) -> None:
    """
    Test that the server correctly handles error conditions in the protocol.

    Args:
        reset_server_state: Fixture to reset the server state before the test.
    """
    input_stream = MockStream()
    output_stream = MockStream()

    # Initialize the server
    init_request = create_request("initialize", {
        "capabilities": {},
        "serverInfo": {"name": "test-client", "version": "1.0.0"}
    })
    input_stream.feed_data(init_request)

    # Run the server
    server_task = asyncio.create_task(
        server.run(
            input_stream,
            output_stream,
            InitializationOptions(
                server_name="datetime-mcp-server",
                server_version="0.1.0",
                capabilities=server.get_capabilities(
                    notification_options=NotificationOptions(),
                    experimental_capabilities={},
                ),
            ),
        )
    )

    # Skip the initialization response
    await get_response(output_stream)

    # Send a resources/read request for a non-existent resource
    input_stream.feed_data(create_request("resources/read", {
        "uri": "note://internal/nonexistent"
    }))

    # Get the response
    response = await get_response(output_stream)

    # Check the response
    assert response["jsonrpc"] == "2.0"
    assert response["id"] == 1
    assert "error" in response
    assert "message" in response["error"]
    assert "Note not found: nonexistent" in response["error"]["message"]

    # Send a tools/call request for a non-existent tool
    input_stream.feed_data(create_request("tools/call", {
        "name": "nonexistent-tool",
        "arguments": {}
    }))

    # Get the response
    response = await get_response(output_stream)

    # Check the response
    assert response["jsonrpc"] == "2.0"
    assert response["id"] == 1
    assert "error" in response
    assert "message" in response["error"]
    assert "Unknown tool: nonexistent-tool" in response["error"]["message"]

    # Send a prompts/get request for a non-existent prompt
    input_stream.feed_data(create_request("prompts/get", {
        "name": "nonexistent-prompt",
        "arguments": {}
    }))

    # Get the response
    response = await get_response(output_stream)

    # Check the response
    assert response["jsonrpc"] == "2.0"
    assert response["id"] == 1
    assert "error" in response
    assert "message" in response["error"]
    assert "Unknown prompt: nonexistent-prompt" in response["error"]["message"]

    # Shutdown the server
    input_stream.feed_data(create_request("shutdown", {}))
    await asyncio.sleep(0.1)

    # Exit the server
    input_stream.feed_data(create_request("exit", {}))
    await asyncio.sleep(0.1)

    await server_task
