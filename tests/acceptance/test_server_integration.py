#!/usr/bin/env python3
"""
Integration tests for the datetime_mcp_server.

These tests verify end-to-end functionality and integration between all components,
including edge cases, complex scenarios, and real-world usage patterns.
"""

import json
import datetime
import pytest
from typing import cast

import mcp.types as types
from src.datetime_mcp_server.server import (
    handle_list_tools,
    handle_call_tool,
    handle_list_resources,
    handle_read_resource,
    handle_list_prompts,
    handle_get_prompt,
    notes,
)


@pytest.fixture
def reset_server_state() -> None:
    """Reset the server state before each test."""
    notes.clear()
    notes["sample"] = "Sample note for testing"


@pytest.mark.asyncio
async def test_end_to_end_date_calculation_workflow(reset_server_state: None) -> None:
    """
    Test a complete workflow: get current date, calculate future date, format result.
    """
    # Step 1: Get current date
    current_result = await handle_call_tool(
        "get-current-datetime", {"format": "iso", "timezone": "UTC"}
    )
    current_iso = current_result[0].text

    # Verify it's a valid ISO format
    current_date = datetime.datetime.fromisoformat(current_iso.replace("Z", "+00:00"))
    assert current_date.tzinfo is not None

    # Step 2: Calculate 30 days from current date
    future_result = await handle_call_tool(
        "calculate-date",
        {
            "base_date": current_iso.split("T")[0],  # Use date part only
            "operation": "add",
            "amount": 30,
            "unit": "days",
            "timezone": "UTC",
        },
    )
    future_date_str = future_result[0].text

    # Step 3: Format the future date in readable format
    format_result = await handle_call_tool(
        "format-date", {"date": future_date_str, "format": "%B %d, %Y"}
    )
    formatted_date = format_result[0].text

    # Verify the workflow worked correctly
    assert len(formatted_date.split()) == 3  # "Month DD, YYYY"
    assert "," in formatted_date


@pytest.mark.asyncio
async def test_business_days_across_holidays_and_weekends(
    reset_server_state: None,
) -> None:
    """
    Test business day calculations with multiple holidays and weekend transitions.
    """
    # Test Christmas/New Year period with holidays
    result = await handle_call_tool(
        "calculate-business-days",
        {
            "start_date": "2024-12-20",  # Friday
            "end_date": "2025-01-02",  # Thursday
            "holidays": ["2024-12-25", "2025-01-01"],  # Christmas and New Year
            "timezone": "UTC",
        },
    )

    # Parse JSON result
    business_days_data = json.loads(result[0].text)
    business_days = business_days_data["business_days"]

    # Expected calculation:
    # Dec 20 (Fri): 1 day
    # Dec 21-22 (Weekend): 0 days
    # Dec 23-24 (Mon-Tue): 2 days
    # Dec 25 (Wed): Holiday - 0 days
    # Dec 26-27 (Thu-Fri): 2 days
    # Dec 28-29 (Weekend): 0 days
    # Dec 30-31 (Mon-Tue): 2 days (Dec 31 is not a holiday in our list)
    # Jan 1 (Wed): Holiday - 0 days
    # Jan 2 (Thu): 1 day
    # Total: 1 + 2 + 2 + 2 + 1 = 8 days
    assert business_days == 8


@pytest.mark.asyncio
async def test_date_range_calculations_across_year_boundary(
    reset_server_state: None,
) -> None:
    """
    Test date range calculations that cross year boundaries and DST changes.
    """
    # Test "last 6 months" from January 15, going back to previous year
    result = await handle_call_tool(
        "calculate-date-range",
        {
            "base_date": "2024-01-15",
            "direction": "last",
            "amount": 6,
            "unit": "months",
            "timezone": "America/New_York",
        },
    )

    range_data = json.loads(result[0].text)

    # Should go from July 15, 2023 to January 15, 2024
    # Extract date part only (remove timezone info if present)
    start_date = (
        range_data["start"].split("T")[0]
        if "T" in range_data["start"]
        else range_data["start"]
    )
    end_date = (
        range_data["end"].split("T")[0]
        if "T" in range_data["end"]
        else range_data["end"]
    )

    assert start_date == "2023-07-15"
    assert end_date == "2024-01-15"


@pytest.mark.asyncio
async def test_leap_year_edge_cases(reset_server_state: None) -> None:
    """
    Test date calculations involving leap year edge cases.
    """
    # Test adding 1 year to Feb 29, 2024 (leap year)
    result = await handle_call_tool(
        "calculate-date",
        {"base_date": "2024-02-29", "operation": "add", "amount": 1, "unit": "years"},
    )

    # Should result in Feb 28, 2025 (not a leap year)
    assert result[0].text == "2025-02-28"

    # Test subtracting from March 1 in leap year
    result = await handle_call_tool(
        "calculate-date",
        {
            "base_date": "2024-03-01",
            "operation": "subtract",
            "amount": 1,
            "unit": "days",
        },
    )

    # Should result in Feb 29, 2024 (leap day)
    assert result[0].text == "2024-02-29"


@pytest.mark.asyncio
async def test_month_end_date_calculations(reset_server_state: None) -> None:
    """
    Test date calculations with month-end dates (edge case handling).
    """
    # Adding months to January 31st
    test_cases = [
        (
            "2024-01-31",
            "add",
            1,
            "months",
            "2024-02-29",
        ),  # Jan 31 + 1 month = Feb 29 (leap year)
        (
            "2023-01-31",
            "add",
            1,
            "months",
            "2023-02-28",
        ),  # Jan 31 + 1 month = Feb 28 (non-leap year)
        ("2024-01-31", "add", 2, "months", "2024-03-31"),  # Jan 31 + 2 months = Mar 31
        ("2024-05-31", "add", 1, "months", "2024-06-30"),  # May 31 + 1 month = Jun 30
    ]

    for base_date, operation, amount, unit, expected in test_cases:
        result = await handle_call_tool(
            "calculate-date",
            {
                "base_date": base_date,
                "operation": operation,
                "amount": amount,
                "unit": unit,
            },
        )
        assert result[0].text == expected, f"Failed for {base_date} + {amount} {unit}"


@pytest.mark.asyncio
async def test_timezone_conversions_and_dst_handling(reset_server_state: None) -> None:
    """
    Test timezone conversions and DST (Daylight Saving Time) handling.
    """
    # Test current datetime in different timezones
    timezones = ["UTC", "America/New_York", "Europe/London", "Asia/Tokyo"]
    results = {}

    for tz in timezones:
        result = await handle_call_tool(
            "get-current-datetime", {"format": "json", "timezone": tz}
        )
        tz_data = json.loads(result[0].text)
        results[tz] = tz_data

        # Verify timezone info is included
        assert "timezone" in tz_data
        assert "utc_offset" in tz_data
        assert "iso" in tz_data

    # UTC should have +00:00 offset
    assert "+00:00" in results["UTC"]["iso"] or results["UTC"]["timezone"] == "UTC"


@pytest.mark.asyncio
async def test_custom_datetime_formats(reset_server_state: None) -> None:
    """
    Test custom datetime formatting with various format strings.
    """
    format_tests = [
        ("%Y-%m-%d", r"\d{4}-\d{2}-\d{2}"),  # ISO date
        ("%A, %B %d, %Y", r"\w+, \w+ \d{1,2}, \d{4}"),  # Full weekday, month
        ("%d/%m/%Y %H:%M", r"\d{2}/\d{2}/\d{4} \d{2}:\d{2}"),  # European format
        ("%Y%m%d_%H%M%S", r"\d{8}_\d{6}"),  # Compact format
    ]

    for format_str, pattern in format_tests:
        result = await handle_call_tool(
            "get-current-datetime",
            {"format": "custom", "custom_format": format_str, "timezone": "UTC"},
        )

        import re

        assert re.match(pattern, result[0].text), (
            f"Format {format_str} failed pattern {pattern}"
        )


@pytest.mark.asyncio
async def test_note_management_complete_lifecycle(reset_server_state: None) -> None:
    """
    Test complete note management lifecycle: add, get, list, delete.
    """
    # Start with sample note from fixture
    list_result = await handle_call_tool("list-notes", {})
    initial_notes = json.loads(list_result[0].text)
    assert len(initial_notes) == 1
    assert initial_notes[0]["name"] == "sample"

    # Add a new note
    await handle_call_tool(
        "add-note", {"name": "project-deadline", "content": "Project due on 2024-12-31"}
    )

    # Get the specific note
    get_result = await handle_call_tool("get-note", {"name": "project-deadline"})
    assert get_result[0].text == "Project due on 2024-12-31"

    # List all notes (should have 2 now)
    list_result = await handle_call_tool("list-notes", {})
    all_notes = json.loads(list_result[0].text)
    assert len(all_notes) == 2

    note_names = [note["name"] for note in all_notes]
    assert "sample" in note_names
    assert "project-deadline" in note_names

    # Delete the project note
    delete_result = await handle_call_tool("delete-note", {"name": "project-deadline"})
    assert "deleted successfully" in delete_result[0].text

    # Verify it's gone
    list_result = await handle_call_tool("list-notes", {})
    final_notes = json.loads(list_result[0].text)
    assert len(final_notes) == 1
    assert final_notes[0]["name"] == "sample"


@pytest.mark.asyncio
async def test_timezone_resources_comprehensive(reset_server_state: None) -> None:
    """
    Test timezone resources for completeness and accuracy.
    """
    # Test timezone-info resource
    from pydantic import AnyUrl

    timezone_info = await handle_read_resource(AnyUrl("datetime://timezone-info"))
    tz_data = json.loads(timezone_info)

    required_keys = ["timezone_name", "utc_offset_hours", "is_dst", "current_time"]
    for key in required_keys:
        assert key in tz_data, f"Missing key: {key}"

    # Test supported-timezones resource
    supported_timezones = await handle_read_resource(
        AnyUrl("datetime://supported-timezones")
    )
    tz_list_data = json.loads(supported_timezones)

    assert "total_timezones" in tz_list_data
    assert "regions" in tz_list_data
    assert tz_list_data["total_timezones"] > 500  # Should have many timezones

    # Verify common timezones are present
    all_timezones = []
    for region_timezones in tz_list_data["regions"].values():
        all_timezones.extend([tz["name"] for tz in region_timezones])

    common_timezones = ["UTC", "America/New_York", "Europe/London", "Asia/Tokyo"]
    for tz in common_timezones:
        assert tz in all_timezones, f"Missing common timezone: {tz}"


@pytest.mark.asyncio
async def test_prompts_generate_useful_content(reset_server_state: None) -> None:
    """
    Test that all datetime prompts generate useful, comprehensive content.
    """
    # Test datetime-calculation-guide
    guide_result = await handle_get_prompt(
        "datetime-calculation-guide", {"scenario": "deadlines"}
    )
    guide_content = cast(types.TextContent, guide_result.messages[0].content).text

    # Should contain tool names and examples
    required_tools = [
        "get-current-datetime",
        "calculate-date",
        "calculate-business-days",
    ]
    for tool in required_tools:
        assert tool in guide_content, f"Guide missing tool: {tool}"

    assert "deadline" in guide_content.lower()
    assert "example" in guide_content.lower()

    # Test business-day-rules
    rules_result = await handle_get_prompt("business-day-rules", {"region": "standard"})
    rules_content = cast(types.TextContent, rules_result.messages[0].content).text

    assert "Monday through Friday" in rules_content
    assert "weekend" in rules_content.lower()
    assert "holiday" in rules_content.lower()

    # Test timezone-best-practices
    tz_result = await handle_get_prompt(
        "timezone-best-practices", {"operation_type": "calculation"}
    )
    tz_content = cast(types.TextContent, tz_result.messages[0].content).text

    assert "UTC" in tz_content
    assert "DST" in tz_content
    assert "timezone" in tz_content.lower()
    assert "best practice" in tz_content.lower()


@pytest.mark.asyncio
async def test_error_handling_and_edge_cases(reset_server_state: None) -> None:
    """
    Test error handling for invalid inputs and edge cases.
    """
    # Test invalid timezone
    result = await handle_call_tool(
        "get-current-datetime", {"format": "iso", "timezone": "Invalid/Timezone"}
    )
    assert "Invalid timezone identifier" in result[0].text

    # Test missing custom format
    try:
        await handle_call_tool("get-current-datetime", {"format": "custom"})
        assert False, "Should have raised ValueError"
    except ValueError as e:
        assert "custom_format is required" in str(e)

    # Test invalid date format
    result = await handle_call_tool(
        "calculate-date",
        {"base_date": "invalid-date", "operation": "add", "amount": 1, "unit": "days"},
    )
    assert "Error calculating date" in result[0].text

    # Test invalid date range (start > end)
    result = await handle_call_tool(
        "calculate-business-days",
        {
            "start_date": "2024-12-31",
            "end_date": "2024-01-01",  # Earlier than start
        },
    )
    assert "Error calculating business days" in result[0].text


@pytest.mark.asyncio
async def test_complex_real_world_scenario(reset_server_state: None) -> None:
    """
    Test a complex real-world scenario: Project planning with multiple date calculations.
    """
    # Scenario: Plan a project with milestones and business day calculations

    # Step 1: Get current date
    current_result = await handle_call_tool(
        "get-current-datetime", {"format": "iso", "timezone": "America/New_York"}
    )
    current_date = current_result[0].text.split("T")[0]

    # Step 2: Calculate project start (next Monday)
    # For simplicity, just add 7 days
    start_result = await handle_call_tool(
        "calculate-date",
        {
            "base_date": current_date,
            "operation": "add",
            "amount": 7,
            "unit": "days",
            "timezone": "America/New_York",
        },
    )
    project_start = start_result[0].text

    # Step 3: Calculate project phases
    # Phase 1: 2 weeks
    phase1_result = await handle_call_tool(
        "calculate-date",
        {"base_date": project_start, "operation": "add", "amount": 14, "unit": "days"},
    )
    phase1_end = phase1_result[0].text

    # Phase 2: 3 weeks after Phase 1
    phase2_result = await handle_call_tool(
        "calculate-date",
        {"base_date": phase1_end, "operation": "add", "amount": 21, "unit": "days"},
    )
    phase2_end = phase2_result[0].text

    # Step 4: Calculate total business days
    business_days_result = await handle_call_tool(
        "calculate-business-days",
        {
            "start_date": project_start,
            "end_date": phase2_end,
            "holidays": [],  # No holidays for this test
        },
    )
    business_days_data = json.loads(business_days_result[0].text)
    total_business_days = business_days_data["business_days"]

    # Step 5: Store project info as notes
    await handle_call_tool(
        "add-note",
        {
            "name": "project-timeline",
            "content": f"Project: {project_start} to {phase2_end}, {total_business_days} business days",
        },
    )

    # Verify the workflow completed successfully
    # Extract date parts only for comparison (to handle timezone differences)
    project_start_date = (
        project_start.split("T")[0] if "T" in project_start else project_start
    )
    phase1_end_date = phase1_end.split("T")[0] if "T" in phase1_end else phase1_end
    phase2_end_date = phase2_end.split("T")[0] if "T" in phase2_end else phase2_end

    assert datetime.datetime.fromisoformat(
        project_start_date
    ) >= datetime.datetime.fromisoformat(current_date)
    assert datetime.datetime.fromisoformat(
        phase1_end_date
    ) > datetime.datetime.fromisoformat(project_start_date)
    assert datetime.datetime.fromisoformat(
        phase2_end_date
    ) > datetime.datetime.fromisoformat(phase1_end_date)
    assert total_business_days > 0

    # Verify note was created
    get_note_result = await handle_call_tool("get-note", {"name": "project-timeline"})
    assert project_start in get_note_result[0].text
    assert str(total_business_days) in get_note_result[0].text


@pytest.mark.asyncio
async def test_performance_and_accuracy_requirements(reset_server_state: None) -> None:
    """
    Test that operations meet performance requirements (< 50ms) and accuracy (100%).
    """
    import time

    # Test multiple operations for performance
    operations = [
        ("get-current-datetime", {"format": "iso"}),
        (
            "calculate-date",
            {
                "base_date": "2024-07-15",
                "operation": "add",
                "amount": 30,
                "unit": "days",
            },
        ),
        (
            "calculate-business-days",
            {"start_date": "2024-07-15", "end_date": "2024-08-15"},
        ),
        ("format-date", {"date": "2024-07-15", "format": "%Y-%m-%d"}),
    ]

    for tool_name, args in operations:
        start_time = time.time()
        result = await handle_call_tool(tool_name, args)
        end_time = time.time()

        # Performance requirement: < 50ms (0.05 seconds)
        duration_ms = (end_time - start_time) * 1000
        assert duration_ms < 50, (
            f"{tool_name} took {duration_ms:.2f}ms (requirement: < 50ms)"
        )

        # Accuracy requirement: Must return valid result
        assert len(result) > 0
        assert result[0].text is not None
        assert len(result[0].text) > 0


@pytest.mark.asyncio
async def test_all_tools_and_resources_accessible(reset_server_state: None) -> None:
    """
    Test that all implemented tools and resources are properly accessible.
    """
    # Test all tools are listed
    tools = await handle_list_tools()
    tool_names = [t.name for t in tools]

    expected_tools = [
        "add-note",
        "get-note",
        "list-notes",
        "delete-note",  # Note management
        "get-current-datetime",
        "format-date",
        "calculate-date",  # DateTime tools
        "calculate-date-range",
        "calculate-business-days",  # Advanced datetime
    ]

    for tool in expected_tools:
        assert tool in tool_names, f"Missing tool: {tool}"

    # Test all resources are listed
    resources = await handle_list_resources()
    resource_uris = [str(r.uri) for r in resources]

    expected_resources = [
        "datetime://current",
        "datetime://timezone-info",
        "datetime://supported-timezones",
    ]

    for resource_uri in expected_resources:
        assert any(resource_uri in uri for uri in resource_uris), (
            f"Missing resource: {resource_uri}"
        )

    # Test all prompts are listed
    prompts = await handle_list_prompts()
    prompt_names = [p.name for p in prompts]

    expected_prompts = [
        "summarize-notes",
        "schedule-event",  # Original prompts
        "datetime-calculation-guide",
        "business-day-rules",
        "timezone-best-practices",  # New prompts
    ]

    for prompt in expected_prompts:
        assert prompt in prompt_names, f"Missing prompt: {prompt}"


if __name__ == "__main__":
    # Run tests if executed directly
    pytest.main([__file__, "-v"])
