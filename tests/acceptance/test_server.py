"""
Acceptance tests for the datetime_mcp_server.

These tests verify the basic functionality of the datetime MCP server
by testing resources, prompts, and tools.
"""

import datetime
from typing import cast
from typing import TYPE_CHECKING

import pytest
from pydantic import AnyUrl
import mcp.types as types

from datetime_mcp_server.server import (
    notes,
    handle_list_resources,
    handle_read_resource,
    handle_list_prompts,
    handle_get_prompt,
    handle_list_tools,
    handle_call_tool,
)

if TYPE_CHECKING:
    from _pytest.monkeypatch import MonkeyPatch


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


@pytest.mark.asyncio
async def test_list_resources(reset_server_state: None) -> None:
    """
    Test that the server correctly lists all resources.

    This test verifies that both note and datetime resources are returned.

    Args:
        reset_server_state: Fixture to reset the server state before the test.
    """
    resources = await handle_list_resources()

    # Check that we have both note and datetime resources
    assert len(resources) >= 5  # 2 notes + 3 datetime resources

    # Check that we have the expected datetime resources
    datetime_uris = [str(r.uri) for r in resources if r.uri.scheme == "datetime"]
    assert "datetime://current" in datetime_uris
    assert "datetime://today" in datetime_uris
    assert "datetime://time" in datetime_uris

    # Check that we have the expected note resources
    note_uris = [str(r.uri) for r in resources if r.uri.scheme == "note"]
    assert "note://internal/test1" in note_uris
    assert "note://internal/test2" in note_uris


@pytest.mark.asyncio
async def test_read_note_resource(reset_server_state: None) -> None:
    """
    Test that the server correctly reads a note resource.

    Args:
        reset_server_state: Fixture to reset the server state before the test.
    """
    content = await handle_read_resource(AnyUrl("note://internal/test1"))
    assert content == "This is a test note"


@pytest.mark.asyncio
async def test_read_nonexistent_note_resource(reset_server_state: None) -> None:
    """
    Test that the server correctly handles reading a nonexistent note resource.

    Args:
        reset_server_state: Fixture to reset the server state before the test.
    """
    with pytest.raises(ValueError, match="Note not found: nonexistent"):
        await handle_read_resource(AnyUrl("note://internal/nonexistent"))


@pytest.mark.asyncio
async def test_read_datetime_resources(reset_server_state: None) -> None:
    """
    Test that the server correctly reads datetime resources.

    Args:
        reset_server_state: Fixture to reset the server state before the test.
    """
    # Test current datetime
    content = await handle_read_resource(AnyUrl("datetime://current"))
    # Verify format, but not exact time since it will change
    assert len(content.split()) == 2  # Date and time parts

    # Test today's date
    content = await handle_read_resource(AnyUrl("datetime://today"))
    # Verify format, but not exact date
    assert len(content.split("-")) == 3  # Year, month, day parts

    # Test current time
    content = await handle_read_resource(AnyUrl("datetime://time"))
    # Verify format, but not exact time
    assert len(content.split(":")) == 3  # Hour, minute, second parts


@pytest.mark.asyncio
async def test_read_invalid_datetime_resource(reset_server_state: None) -> None:
    """
    Test that the server correctly handles reading an invalid datetime resource.

    Args:
        reset_server_state: Fixture to reset the server state before the test.
    """
    with pytest.raises(ValueError, match="Unknown datetime resource: nonexistent"):
        await handle_read_resource(AnyUrl("datetime://nonexistent"))


@pytest.mark.asyncio
async def test_read_unsupported_uri_scheme(reset_server_state: None) -> None:
    """
    Test that the server correctly handles reading a resource with an unsupported URI scheme.

    Args:
        reset_server_state: Fixture to reset the server state before the test.
    """
    with pytest.raises(ValueError, match="Unsupported URI scheme: file"):
        await handle_read_resource(AnyUrl("file:///path/to/file"))


@pytest.mark.asyncio
async def test_list_prompts(reset_server_state: None) -> None:
    """
    Test that the server correctly lists all prompts.

    Args:
        reset_server_state: Fixture to reset the server state before the test.
    """
    prompts = await handle_list_prompts()

    # Check that we have the expected prompts
    prompt_names = [p.name for p in prompts]
    assert "summarize-notes" in prompt_names
    assert "schedule-event" in prompt_names
    assert "datetime-calculation-guide" in prompt_names
    assert "business-day-rules" in prompt_names
    assert "timezone-best-practices" in prompt_names

    # Check specific prompts
    schedule_event = next(p for p in prompts if p.name == "schedule-event")
    assert schedule_event.description == "Helps schedule an event at a specific time"
    assert len(schedule_event.arguments) == 2

    # Check arguments for schedule-event
    arg_names = [a.name for a in schedule_event.arguments]
    assert "event" in arg_names
    assert "time" in arg_names

    # Check new datetime prompts
    datetime_guide = next(p for p in prompts if p.name == "datetime-calculation-guide")
    assert (
        datetime_guide.description
        == "Provides examples and guidance on when and how to use date calculation tools"
    )
    assert len(datetime_guide.arguments) == 1

    business_rules = next(p for p in prompts if p.name == "business-day-rules")
    assert (
        business_rules.description
        == "Explains business day calculation rules, weekend patterns, and holiday handling"
    )
    assert len(business_rules.arguments) == 1

    timezone_practices = next(p for p in prompts if p.name == "timezone-best-practices")
    assert (
        timezone_practices.description
        == "Guidelines for timezone-aware date operations and common pitfalls to avoid"
    )
    assert len(timezone_practices.arguments) == 1


@pytest.mark.asyncio
async def test_get_summarize_notes_prompt(reset_server_state: None) -> None:
    """
    Test that the server correctly generates the summarize-notes prompt.

    Args:
        reset_server_state: Fixture to reset the server state before the test.
    """
    result = await handle_get_prompt("summarize-notes", None)

    assert result.description == "Summarize the current notes"
    assert len(result.messages) == 1

    message = result.messages[0]
    assert message.role == "user"
    assert "test1: This is a test note" in cast(types.TextContent, message.content).text
    assert (
        "test2: This is another test note"
        in cast(types.TextContent, message.content).text
    )


@pytest.mark.asyncio
async def test_get_schedule_event_prompt(reset_server_state: None) -> None:
    """
    Test that the server correctly generates the schedule-event prompt.

    Args:
        reset_server_state: Fixture to reset the server state before the test.
    """
    arguments = {"event": "Meeting", "time": "15:00"}
    result = await handle_get_prompt("schedule-event", arguments)

    assert result.description == "Schedule an event at a specific time"
    assert len(result.messages) == 1

    message = result.messages[0]
    assert message.role == "user"

    content_text = cast(types.TextContent, message.content).text
    assert "Please schedule an event named 'Meeting'" in content_text
    assert "at 15:00" in content_text


@pytest.mark.asyncio
async def test_get_schedule_event_prompt_missing_args(reset_server_state: None) -> None:
    """
    Test that the server correctly handles missing arguments for schedule-event prompt.

    Args:
        reset_server_state: Fixture to reset the server state before the test.
    """
    with pytest.raises(
        ValueError, match="Missing required arguments for schedule-event prompt"
    ):
        await handle_get_prompt("schedule-event", None)

    with pytest.raises(ValueError, match="Missing required event or time argument"):
        await handle_get_prompt("schedule-event", {"event": "Meeting"})


@pytest.mark.asyncio
async def test_get_datetime_calculation_guide_prompt(reset_server_state: None) -> None:
    """
    Test that the server correctly generates the datetime-calculation-guide prompt.

    Args:
        reset_server_state: Fixture to reset the server state before the test.
    """
    # Test without arguments
    result = await handle_get_prompt("datetime-calculation-guide", None)

    assert (
        result.description == "Guide for using datetime calculation tools effectively"
    )
    assert len(result.messages) == 1

    message = result.messages[0]
    assert message.role == "user"

    content_text = cast(types.TextContent, message.content).text
    assert "DateTime Calculation Tools Guide" in content_text
    assert "get-current-datetime" in content_text
    assert "calculate-date" in content_text
    assert "calculate-business-days" in content_text

    # Test with scenario argument
    result = await handle_get_prompt(
        "datetime-calculation-guide", {"scenario": "deadlines"}
    )
    content_text = cast(types.TextContent, result.messages[0].content).text
    assert "Deadlines" in content_text


@pytest.mark.asyncio
async def test_get_business_day_rules_prompt(reset_server_state: None) -> None:
    """
    Test that the server correctly generates the business-day-rules prompt.

    Args:
        reset_server_state: Fixture to reset the server state before the test.
    """
    # Test without arguments
    result = await handle_get_prompt("business-day-rules", None)

    assert result.description == "Business day calculation rules and best practices"
    assert len(result.messages) == 1

    message = result.messages[0]
    assert message.role == "user"

    content_text = cast(types.TextContent, message.content).text
    assert "Business Day Calculation Rules" in content_text
    assert "Monday through Friday" in content_text
    assert "calculate-business-days" in content_text
    assert "holidays" in content_text

    # Test with region argument
    result = await handle_get_prompt("business-day-rules", {"region": "us"})
    content_text = cast(types.TextContent, result.messages[0].content).text
    assert "Us" in content_text


@pytest.mark.asyncio
async def test_get_timezone_best_practices_prompt(reset_server_state: None) -> None:
    """
    Test that the server correctly generates the timezone-best-practices prompt.

    Args:
        reset_server_state: Fixture to reset the server state before the test.
    """
    # Test without arguments
    result = await handle_get_prompt("timezone-best-practices", None)

    assert result.description == "Best practices for timezone-aware date operations"
    assert len(result.messages) == 1

    message = result.messages[0]
    assert message.role == "user"

    content_text = cast(types.TextContent, message.content).text
    assert "Timezone Best Practices" in content_text
    assert "UTC" in content_text
    assert "DST" in content_text
    assert "America/New_York" in content_text

    # Test with operation_type argument
    result = await handle_get_prompt(
        "timezone-best-practices", {"operation_type": "calculation"}
    )
    content_text = cast(types.TextContent, result.messages[0].content).text
    assert "Calculation" in content_text


@pytest.mark.asyncio
async def test_get_unknown_prompt(reset_server_state: None) -> None:
    """
    Test that the server correctly handles an unknown prompt name.

    Args:
        reset_server_state: Fixture to reset the server state before the test.
    """
    with pytest.raises(ValueError, match="Unknown prompt: unknown-prompt"):
        await handle_get_prompt("unknown-prompt", None)


@pytest.mark.asyncio
async def test_list_tools(reset_server_state: None) -> None:
    """
    Test that the server correctly lists all tools.

    Args:
        reset_server_state: Fixture to reset the server state before the test.
    """
    tools = await handle_list_tools()

    # Check that we have the expected tools
    tool_names = [t.name for t in tools]
    assert "add-note" in tool_names
    assert "get-current-datetime" in tool_names
    assert "format-date" in tool_names

    # Check specific tools
    get_current_datetime = next(t for t in tools if t.name == "get-current-datetime")
    assert (
        get_current_datetime.description
        == "Get the current date and time in various formats with timezone support"
    )

    # Check input schema for get-current-datetime
    schema = get_current_datetime.inputSchema
    assert "format" in schema["properties"]
    assert "timezone" in schema["properties"]
    assert "custom_format" in schema["properties"]
    assert "format" in schema["required"]


@pytest.mark.asyncio
async def test_call_add_note_tool(reset_server_state: None) -> None:
    """
    Test that the server correctly handles the add-note tool.

    Args:
        reset_server_state: Fixture to reset the server state before the test.
    """
    # Save the initial state of notes
    initial_notes = notes.copy()

    arguments = {"name": "new-note", "content": "This is a new note"}
    result = await handle_call_tool("add-note", arguments)

    # Check that the note was added
    assert "new-note" in notes
    assert notes["new-note"] == "This is a new note"
    assert len(notes) == len(initial_notes) + 1

    # Check the result
    assert len(result) == 1
    assert result[0].type == "text"
    assert "Added note 'new-note'" in result[0].text


@pytest.mark.asyncio
async def test_call_add_note_tool_missing_args(reset_server_state: None) -> None:
    """
    Test that the server correctly handles missing arguments for add-note tool.

    Args:
        reset_server_state: Fixture to reset the server state before the test.
    """
    # Test missing arguments - should return error text, not raise exception
    result = await handle_call_tool("add-note", None)
    assert len(result) == 1
    assert "Error adding note: Missing arguments" in result[0].text

    # Test missing content - should return error text, not raise exception
    result = await handle_call_tool("add-note", {"name": "new-note"})
    assert len(result) == 1
    assert "Error adding note: Missing name or content" in result[0].text


@pytest.mark.asyncio
async def test_call_get_current_datetime_tool(reset_server_state: None) -> None:
    """
    Test that the server correctly handles the get-current-datetime tool.

    Args:
        reset_server_state: Fixture to reset the server state before the test.
    """
    # Test with ISO format
    arguments = {"format": "iso"}
    result = await handle_call_tool("get-current-datetime", arguments)

    assert len(result) == 1
    assert result[0].type == "text"

    # The result should be a valid ISO format datetime
    try:
        datetime.datetime.fromisoformat(result[0].text)
        is_valid_iso = True
    except ValueError:
        is_valid_iso = False
    assert is_valid_iso

    # Test with readable format
    arguments = {"format": "readable"}
    result = await handle_call_tool("get-current-datetime", arguments)

    assert len(result) == 1
    assert result[0].type == "text"

    # The result should be in format YYYY-MM-DD HH:MM:SS
    time_str = result[0].text
    assert len(time_str.split()) == 2
    assert len(time_str.split()[0].split("-")) == 3
    assert len(time_str.split()[1].split(":")) == 3


@pytest.mark.asyncio
async def test_call_format_date_tool(reset_server_state: None) -> None:
    """
    Test that the server correctly handles the format-date tool.

    Args:
        reset_server_state: Fixture to reset the server state before the test.
    """
    # Test with custom format
    today = datetime.datetime.now().strftime("%Y-%m-%d")
    arguments = {"date": today, "format": "%d/%m/%Y"}
    result = await handle_call_tool("format-date", arguments)

    assert len(result) == 1
    assert result[0].type == "text"

    # The result should be in format DD/MM/YYYY
    date_parts = result[0].text.split("/")
    assert len(date_parts) == 3

    # Test with default date (today)
    arguments = {"format": "%B %d, %Y"}
    result = await handle_call_tool("format-date", arguments)

    assert len(result) == 1
    assert result[0].type == "text"

    # The result should be in format Month DD, YYYY
    today = datetime.datetime.now()
    expected = today.strftime("%B %d, %Y")
    assert result[0].text == expected


@pytest.mark.asyncio
async def test_call_format_date_tool_invalid_date(reset_server_state: None) -> None:
    """
    Test that the server correctly handles invalid date for format-date tool.

    Args:
        reset_server_state: Fixture to reset the server state before the test.
    """
    arguments = {"date": "invalid-date", "format": "%Y-%m-%d"}
    result = await handle_call_tool("format-date", arguments)

    assert len(result) == 1
    assert result[0].type == "text"
    assert "Could not parse date string: invalid-date" in result[0].text


@pytest.mark.asyncio
async def test_call_format_date_tool_invalid_format(reset_server_state: None) -> None:
    """
    Test that the server correctly handles invalid format for format-date tool.

    Args:
        reset_server_state: Fixture to reset the server state before the test.
    """
    arguments = {"date": "2023-01-01", "format": "%invalid"}
    result = await handle_call_tool("format-date", arguments)

    assert len(result) == 1
    assert result[0].type == "text"
    assert "invalid" in result[0].text.lower()


@pytest.mark.asyncio
async def test_call_unknown_tool(reset_server_state: None) -> None:
    """
    Test that the server correctly handles an unknown tool name.

    Args:
        reset_server_state: Fixture to reset the server state before the test.
    """
    # Test unknown tool - should return error text, not raise exception
    result = await handle_call_tool("unknown-tool", {})
    assert len(result) == 1
    assert "Error: Unknown tool 'unknown-tool'" in result[0].text


@pytest.mark.asyncio
async def test_call_get_current_datetime_with_timezone(
    reset_server_state: None, monkeypatch: "MonkeyPatch"
) -> None:
    """
    Test that the server correctly handles timezones in the get-current-datetime tool.
    Uses zoneinfo instead of pytz for timezone handling.

    Args:
        reset_server_state: Fixture to reset the server state before the test.
        monkeypatch: Pytest monkeypatch fixture.
    """
    # Test with timezone argument
    arguments = {"format": "readable", "timezone": "America/New_York"}
    result = await handle_call_tool("get-current-datetime", arguments)

    assert len(result) == 1
    assert result[0].type == "text"

    # The result should be a readable datetime string
    time_str = result[0].text
    assert len(time_str.split()) == 2
    assert len(time_str.split()[0].split("-")) == 3
    assert len(time_str.split()[1].split(":")) == 3

    # Test with invalid timezone
    arguments = {"format": "readable", "timezone": "Invalid/Timezone"}
    result = await handle_call_tool("get-current-datetime", arguments)

    assert len(result) == 1
    assert "Invalid timezone identifier" in result[0].text
