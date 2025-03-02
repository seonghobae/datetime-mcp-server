"""
Integration tests for the datetime_mcp_server.

These tests verify that the server correctly implements the MCP protocol
by testing the full server lifecycle with mocked streams.
"""

import asyncio
import json
from typing import Any, Dict, List, Optional, Tuple, cast
from typing import TYPE_CHECKING

import pytest
from pydantic import AnyUrl
from mcp.server.models import InitializationOptions
import mcp.types as types
from datetime_mcp_server.server import server, notes

if TYPE_CHECKING:
    from _pytest.capture import CaptureFixture
    from _pytest.fixtures import FixtureRequest
    from _pytest.logging import LogCaptureFixture
    from _pytest.monkeypatch import MonkeyPatch
    from pytest_mock.plugin import MockerFixture


class MockStream:
    """
    Mock I/O stream for testing the MCP server.

    This class simulates the read and write operations needed for the MCP server
    to communicate with clients.
    """

    def __init__(self) -> None:
        """Initialize the mock stream with empty buffers."""
        self.write_buffer: List[bytes] = []
        self.read_buffer: List[bytes] = []
        self.closed = False

    async def write(self, data: bytes) -> None:
        """
        Write data to the stream's write buffer.

        Args:
            data: The bytes to write.
        """
        self.write_buffer.append(data)

    async def read(self, n: int = -1) -> bytes:
        """
        Read data from the stream's read buffer.

        Args:
            n: The number of bytes to read. If -1, read all available data.

        Returns:
            The read bytes.
        """
        if not self.read_buffer:
            return b""
        if n == -1:
            result = b"".join(self.read_buffer)
            self.read_buffer.clear()
            return result
        result = self.read_buffer[0][:n]
        self.read_buffer[0] = self.read_buffer[0][n:]
        if not self.read_buffer[0]:
            self.read_buffer.pop(0)
        return result

    def close(self) -> None:
        """Close the stream."""
        self.closed = True

    def feed_data(self, data: str) -> None:
        """
        Feed data to the read buffer.

        Args:
            data: The data to add to the read buffer.
        """
        self.read_buffer.append(data.encode())


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


def create_request(method: str, params: Dict[str, Any]) -> str:
    """
    Create a JSON-RPC request string.

    Args:
        method: The method name.
        params: The method parameters.

    Returns:
        A JSON-RPC request string.
    """
    return json.dumps({
        "jsonrpc": "2.0",
        "id": 1,
        "method": method,
        "params": params
    }) + "\r\n"


async def get_response(stream: MockStream) -> Dict[str, Any]:
    """
    Get a response from the stream and parse it.

    Args:
        stream: The mock stream.

    Returns:
        The parsed JSON-RPC response.
    """
    response_data = b""
    while True:
        data = await stream.read(1024)
        if not data:
            break
        response_data += data
        if response_data.endswith(b"\r\n"):
            break

    response_str = response_data.decode().strip()
    return json.loads(response_str)


@pytest.mark.asyncio
async def test_server_initialization(reset_server_state: None) -> None:
    """
    Test that the server initializes correctly.

    Args:
        reset_server_state: Fixture to reset the server state before the test.
    """
    input_stream = MockStream()
    output_stream = MockStream()

    # Prepare the initialization request
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
                capabilities=server.get_capabilities(),
            ),
        )
    )

    # Get the initialization response
    response = await get_response(output_stream)

    # Check the response
    assert response["jsonrpc"] == "2.0"
    assert response["id"] == 1
    assert "result" in response
    assert response["result"]["serverInfo"]["name"] == "datetime-mcp-server"
    assert response["result"]["serverInfo"]["version"] == "0.1.0"

    # Shutdown the server
    input_stream.feed_data(create_request("shutdown", {}))
    await asyncio.sleep(0.1)

    # Exit the server
    input_stream.feed_data(create_request("exit", {}))
    await asyncio.sleep(0.1)

    await server_task


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
                capabilities=server.get_capabilities(),
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
                capabilities=server.get_capabilities(),
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
                capabilities=server.get_capabilities(),
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
                capabilities=server.get_capabilities(),
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
                capabilities=server.get_capabilities(),
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
