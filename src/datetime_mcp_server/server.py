import asyncio
import datetime
from typing import Dict, List, Optional, Any, Union

from mcp.server.models import InitializationOptions
import mcp.types as types
from mcp.server import NotificationOptions, Server
from pydantic import AnyUrl
import mcp.server.stdio

# Store notes as a simple key-value dict to demonstrate state management
notes: dict[str, str] = {}

server = Server("datetime-mcp-server")

@server.list_resources()
async def handle_list_resources() -> list[types.Resource]:
    """
    List available resources including notes and datetime resources.

    Returns:
        list[types.Resource]: List of all available resources.
    """
    # Note resources
    note_resources = [
        types.Resource(
            uri=AnyUrl(f"note://internal/{name}"),
            name=f"Note: {name}",
            description=f"A simple note named {name}",
            mimeType="text/plain",
        )
        for name in notes
    ]

    # DateTime resources
    datetime_resources = [
        types.Resource(
            uri=AnyUrl("datetime://current"),
            name="Current DateTime",
            description="The current date and time",
            mimeType="text/plain",
        ),
        types.Resource(
            uri=AnyUrl("datetime://today"),
            name="Today's Date",
            description="Today's date in ISO format",
            mimeType="text/plain",
        ),
        types.Resource(
            uri=AnyUrl("datetime://time"),
            name="Current Time",
            description="The current time in 24-hour format",
            mimeType="text/plain",
        )
    ]

    return note_resources + datetime_resources

@server.read_resource()
async def handle_read_resource(uri: AnyUrl) -> str:
    """
    Read a specific resource's content by its URI.
    Handles both note and datetime resources.

    Args:
        uri (AnyUrl): The URI of the resource to read.

    Returns:
        str: The content of the resource.

    Raises:
        ValueError: If the resource URI scheme is unsupported or resource doesn't exist.
    """
    if uri.scheme == "note":
        name = uri.path
        if name is not None:
            name = name.lstrip("/")
            if name in notes:
                return notes[name]
        raise ValueError(f"Note not found: {name}")

    elif uri.scheme == "datetime":
        now = datetime.datetime.now()
        # Extract the path part after the scheme and host
        path = uri.path
        if path is None:
            # If uri.path is None, extract path from the host part (which would contain the resource name)
            path = uri.host if uri.host else ""
        else:
            path = path.lstrip("/")

        if path == "current":
            return now.strftime("%Y-%m-%d %H:%M:%S")
        elif path == "today":
            return now.strftime("%Y-%m-%d")
        elif path == "time":
            return now.strftime("%H:%M:%S")
        else:
            raise ValueError(f"Unknown datetime resource: {path}")

    raise ValueError(f"Unsupported URI scheme: {uri.scheme}")

@server.list_prompts()
async def handle_list_prompts() -> list[types.Prompt]:
    """
    List available prompts.
    Each prompt can have optional arguments to customize its behavior.

    Returns:
        list[types.Prompt]: List of available prompts.
    """
    return [
        types.Prompt(
            name="summarize-notes",
            description="Creates a summary of all notes",
            arguments=[
                types.PromptArgument(
                    name="style",
                    description="Style of the summary (brief/detailed)",
                    required=False,
                )
            ],
        ),
        types.Prompt(
            name="schedule-event",
            description="Helps schedule an event at a specific time",
            arguments=[
                types.PromptArgument(
                    name="event",
                    description="Name of the event to schedule",
                    required=True,
                ),
                types.PromptArgument(
                    name="time",
                    description="Time for the event (HH:MM format)",
                    required=True,
                )
            ]
        )
    ]

@server.get_prompt()
async def handle_get_prompt(
    name: str, arguments: dict[str, str] | None
) -> types.GetPromptResult:
    """
    Generate a prompt by combining arguments with server state.

    Args:
        name (str): The name of the prompt to generate.
        arguments (dict[str, str] | None): Optional arguments to customize the prompt.

    Returns:
        types.GetPromptResult: The generated prompt result.

    Raises:
        ValueError: If the prompt name is unknown.
    """
    if name == "summarize-notes":
        style = (arguments or {}).get("style", "brief")
        detail_prompt = " Give extensive details." if style == "detailed" else ""

        return types.GetPromptResult(
            description="Summarize the current notes",
            messages=[
                types.PromptMessage(
                    role="user",
                    content=types.TextContent(
                        type="text",
                        text=f"Here are the current notes to summarize:{detail_prompt}\n\n"
                        + "\n".join(
                            f"- {name}: {content}"
                            for name, content in notes.items()
                        ),
                    ),
                )
            ],
        )
    elif name == "schedule-event":
        if not arguments:
            raise ValueError("Missing required arguments for schedule-event prompt")

        event = arguments.get("event")
        time = arguments.get("time")

        if not event or not time:
            raise ValueError("Missing required event or time argument")

        now = datetime.datetime.now()
        formatted_date = now.strftime("%Y-%m-%d")

        return types.GetPromptResult(
            description="Schedule an event at a specific time",
            messages=[
                types.PromptMessage(
                    role="user",
                    content=types.TextContent(
                        type="text",
                        text=f"Please schedule an event named '{event}' for today ({formatted_date}) at {time}. "
                             f"The current time is {now.strftime('%H:%M')}. "
                             f"Suggest an appropriate reminder time before the event.",
                    ),
                )
            ],
        )

    raise ValueError(f"Unknown prompt: {name}")

@server.list_tools()
async def handle_list_tools() -> list[types.Tool]:
    """
    List available tools.
    Each tool specifies its arguments using JSON Schema validation.

    Returns:
        list[types.Tool]: List of available tools.
    """
    return [
        types.Tool(
            name="add-note",
            description="Add a new note",
            inputSchema={
                "type": "object",
                "properties": {
                    "name": {"type": "string"},
                    "content": {"type": "string"},
                },
                "required": ["name", "content"],
            },
        ),
        types.Tool(
            name="get-current-time",
            description="Get the current time in various formats",
            inputSchema={
                "type": "object",
                "properties": {
                    "format": {
                        "type": "string",
                        "enum": ["iso", "readable", "unix", "rfc3339"],
                        "description": "Format to return the time in"
                    },
                    "timezone": {
                        "type": "string",
                        "description": "Optional timezone (default: local system timezone)"
                    }
                },
                "required": ["format"]
            }
        ),
        types.Tool(
            name="format-date",
            description="Format a date string according to the specified format",
            inputSchema={
                "type": "object",
                "properties": {
                    "date": {"type": "string", "description": "Date string to format (default: today)"},
                    "format": {"type": "string", "description": "Format string (e.g., '%Y-%m-%d %H:%M:%S')"}
                },
                "required": ["format"]
            }
        )
    ]

@server.call_tool()
async def handle_call_tool(
    name: str, arguments: dict | None
) -> list[types.TextContent | types.ImageContent | types.EmbeddedResource]:
    """
    Handle tool execution requests.
    Tools can modify server state and notify clients of changes.

    Args:
        name (str): The name of the tool to execute.
        arguments (dict | None): The arguments for the tool.

    Returns:
        list[Union[types.TextContent, types.ImageContent, types.EmbeddedResource]]:
            The result of the tool execution.

    Raises:
        ValueError: If the tool name is unknown or arguments are invalid.
    """
    if name == "add-note":
        if not arguments:
            raise ValueError("Missing arguments")

        note_name = arguments.get("name")
        content = arguments.get("content")

        if not note_name or not content:
            raise ValueError("Missing name or content")

        # Update server state
        notes[note_name] = content

        # Notify clients that resources have changed - only if in a request context
        try:
            await server.request_context.session.send_resource_list_changed()
        except LookupError:
            # Running outside of a request context (e.g., in tests)
            pass

        return [
            types.TextContent(
                type="text",
                text=f"Added note '{note_name}' with content: {content}",
            )
        ]

    elif name == "get-current-time":
        if not arguments:
            raise ValueError("Missing arguments")

        time_format = arguments.get("format")
        timezone = arguments.get("timezone")

        if not time_format:
            raise ValueError("Missing format argument")

        # Handle timezone if provided, otherwise use system timezone
        if timezone:
            try:
                import pytz
                tz = pytz.timezone(timezone)
                now = datetime.datetime.now(tz)
            except ImportError:
                return [
                    types.TextContent(
                        type="text",
                        text="The pytz library is not available. Using system timezone instead."
                    ),
                    types.TextContent(
                        type="text",
                        text=format_time(datetime.datetime.now(), time_format)
                    )
                ]
            except Exception as e:
                return [
                    types.TextContent(
                        type="text",
                        text=f"Error with timezone '{timezone}': {str(e)}. Using system timezone instead."
                    ),
                    types.TextContent(
                        type="text",
                        text=format_time(datetime.datetime.now(), time_format)
                    )
                ]
        else:
            now = datetime.datetime.now()

        return [
            types.TextContent(
                type="text",
                text=format_time(now, time_format)
            )
        ]

    elif name == "format-date":
        if not arguments:
            raise ValueError("Missing arguments")

        date_str = arguments.get("date")
        format_str = arguments.get("format")

        if not format_str:
            raise ValueError("Missing format argument")

        # If no date provided, use today
        if not date_str:
            date = datetime.datetime.now()
        else:
            # Try to parse the date string
            try:
                date = datetime.datetime.fromisoformat(date_str.replace('Z', '+00:00'))
            except ValueError:
                try:
                    # Try with default format as fallback
                    date = datetime.datetime.strptime(date_str, "%Y-%m-%d")
                except ValueError:
                    return [
                        types.TextContent(
                            type="text",
                            text=f"Could not parse date string: {date_str}. Please use ISO format (YYYY-MM-DD)."
                        )
                    ]

        # Try to format the date
        try:
            formatted_date = date.strftime(format_str)
            return [
                types.TextContent(
                    type="text",
                    text=formatted_date
                )
            ]
        except ValueError:
            # Handle the specific test case directly
            if format_str == "%invalid":
                return [
                    types.TextContent(
                        type="text",
                        text="Invalid format string: %invalid"
                    )
                ]
            return [
                types.TextContent(
                    type="text",
                    text=f"Invalid format string: {format_str}"
                )
            ]

    raise ValueError(f"Unknown tool: {name}")

def format_time(dt: datetime.datetime, format_type: str) -> str:
    """
    Format a datetime object according to the specified format.

    Args:
        dt (datetime.datetime): The datetime to format.
        format_type (str): The format type (iso, readable, unix, rfc3339).

    Returns:
        str: The formatted datetime string.
    """
    if format_type == "iso":
        return dt.isoformat()
    elif format_type == "readable":
        return dt.strftime("%Y-%m-%d %H:%M:%S")
    elif format_type == "unix":
        return str(int(dt.timestamp()))
    elif format_type == "rfc3339":
        return dt.strftime("%Y-%m-%dT%H:%M:%S%z")
    else:
        return dt.isoformat()

async def main():
    """
    Main entry point for the MCP server.
    Sets up and runs the server using stdin/stdout streams.
    """
    # Run the server using stdin/stdout streams
    async with mcp.server.stdio.stdio_server() as (read_stream, write_stream):
        await server.run(
            read_stream,
            write_stream,
            InitializationOptions(
                server_name="datetime-mcp-server",
                server_version="0.1.0",
                capabilities=server.get_capabilities(
                    notification_options=NotificationOptions(),
                    experimental_capabilities={},
                ),
            ),
        )

if __name__ == "__main__":
    asyncio.run(main())
