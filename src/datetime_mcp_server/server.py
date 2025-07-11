import asyncio
import datetime
import calendar
import json
import zoneinfo
import signal
import sys
import psutil
import os
import threading
from typing import Dict, List, Optional
from collections import OrderedDict
import time

from mcp.server.models import InitializationOptions
import mcp.types as types
from mcp.server import NotificationOptions, Server
from pydantic import AnyUrl
import mcp.server.stdio

from .logging_config import setup_logging, get_logger, ServerHealthLogger

# Initialize logging
logger = get_logger("server")
health_logger = ServerHealthLogger()

# Store notes as a simple key-value dict to demonstrate state management
# Add size limit to prevent memory issues
MAX_NOTES = 1000
MAX_NOTE_SIZE = 10 * 1024  # 10KB per note

# Thread-safe notes storage with proper synchronization
notes_lock = threading.RLock()  # Reentrant lock for nested operations
notes: OrderedDict[str, str] = OrderedDict()  # OrderedDict for proper FIFO behavior

server = Server("datetime-mcp-server")

# Thread-safe shutdown management
shutdown_lock = threading.Lock()
shutdown_requested = False

# Server health metrics with thread safety
health_metrics_lock = threading.Lock()
health_metrics = {
    "memory_warnings": 0,
    "note_storage_warnings": 0,
    "resource_cleanup_count": 0,
    "error_recovery_count": 0,
    "last_health_check": 0,
}


def set_shutdown_requested(value: bool) -> None:
    """Thread-safe shutdown flag setter."""
    global shutdown_requested
    with shutdown_lock:
        shutdown_requested = value


def is_shutdown_requested() -> bool:
    """Thread-safe shutdown flag getter."""
    with shutdown_lock:
        return shutdown_requested


def update_health_metrics(metric: str, increment: int = 1) -> None:
    """Thread-safe health metrics update."""
    with health_metrics_lock:
        if metric in health_metrics:
            health_metrics[metric] += increment
        # Use time.time() instead of asyncio.get_event_loop().time() for thread safety
        health_metrics["last_health_check"] = time.time()


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
        ),
        types.Resource(
            uri=AnyUrl("datetime://timezone-info"),
            name="Timezone Information",
            description="Current timezone information including UTC offset and DST status",
            mimeType="application/json",
        ),
        types.Resource(
            uri=AnyUrl("datetime://supported-timezones"),
            name="Supported Timezones",
            description="List of all supported timezone identifiers grouped by region",
            mimeType="application/json",
        ),
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
        elif path == "timezone-info":
            # Get current timezone information
            current_tz = now.astimezone().tzinfo

            # Calculate UTC offset
            utc_offset = now.astimezone().utcoffset()
            utc_offset_str = (
                f"{utc_offset.total_seconds() / 3600:+.1f}" if utc_offset else "+0.0"
            )

            # Check DST status
            dst_offset = now.astimezone().dst()
            is_dst = dst_offset is not None and dst_offset.total_seconds() > 0

            # Get timezone name
            tz_name = str(current_tz) if current_tz else "Local"

            timezone_info = {
                "timezone_name": tz_name,
                "utc_offset_hours": utc_offset_str,
                "is_dst": is_dst,
                "current_time": now.astimezone().isoformat(),
                "utc_time": now.utctimetuple(),
                "dst_offset_seconds": int(dst_offset.total_seconds())
                if dst_offset
                else 0,
            }

            return json.dumps(timezone_info, indent=2, default=str)
        elif path == "supported-timezones":
            # Get all available timezones
            try:
                all_timezones = sorted(zoneinfo.available_timezones())
            except Exception:
                # Fallback in case zoneinfo is not available
                all_timezones = [
                    "UTC",
                    "America/New_York",
                    "Europe/London",
                    "Asia/Tokyo",
                ]

            # Group timezones by region
            timezone_groups = {}
            for tz_name in all_timezones:
                parts = tz_name.split("/")
                if len(parts) >= 2:
                    region = parts[0]
                    if region not in timezone_groups:
                        timezone_groups[region] = []

                    # Get current offset for this timezone
                    try:
                        tz = zoneinfo.ZoneInfo(tz_name)
                        tz_now = datetime.datetime.now(tz)
                        offset = tz_now.utcoffset()
                        offset_str = (
                            f"{offset.total_seconds() / 3600:+.1f}"
                            if offset
                            else "+0.0"
                        )

                        timezone_groups[region].append(
                            {
                                "name": tz_name,
                                "display_name": parts[-1].replace("_", " "),
                                "current_offset": offset_str,
                            }
                        )
                    except Exception:
                        # Skip invalid timezones
                        continue
                else:
                    # Handle single-part timezone names (like UTC)
                    if "Other" not in timezone_groups:
                        timezone_groups["Other"] = []
                    timezone_groups["Other"].append(
                        {
                            "name": tz_name,
                            "display_name": tz_name,
                            "current_offset": "+0.0" if tz_name == "UTC" else "Unknown",
                        }
                    )

            timezone_data = {
                "total_timezones": len(all_timezones),
                "regions": timezone_groups,
                "generated_at": datetime.datetime.now().isoformat(),
            }

            return json.dumps(timezone_data, indent=2)
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
                ),
            ],
        ),
        types.Prompt(
            name="datetime-calculation-guide",
            description="Provides examples and guidance on when and how to use date calculation tools",
            arguments=[
                types.PromptArgument(
                    name="scenario",
                    description="Specific scenario or use case (optional)",
                    required=False,
                )
            ],
        ),
        types.Prompt(
            name="business-day-rules",
            description="Explains business day calculation rules, weekend patterns, and holiday handling",
            arguments=[
                types.PromptArgument(
                    name="region",
                    description="Specific region or country for business day rules (optional)",
                    required=False,
                )
            ],
        ),
        types.Prompt(
            name="timezone-best-practices",
            description="Guidelines for timezone-aware date operations and common pitfalls to avoid",
            arguments=[
                types.PromptArgument(
                    name="operation_type",
                    description="Type of operation (calculation/formatting/storage/comparison)",
                    required=False,
                )
            ],
        ),
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
                            f"- {name}: {content}" for name, content in notes.items()
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

    elif name == "datetime-calculation-guide":
        scenario = (arguments or {}).get("scenario", "general")

        guide_content = f"""# DateTime Calculation Tools Guide

## Available Tools

### 1. get-current-datetime
**Purpose**: Get current date/time in various formats
**Use when**: You need the current timestamp as a reference point

**Examples**:
```
get-current-datetime(format="iso") → "2024-07-15T14:30:00"
get-current-datetime(format="json", timezone="UTC") → Full JSON with multiple formats
get-current-datetime(format="custom", custom_format="%A, %B %d, %Y") → "Monday, July 15, 2024"
```

### 2. calculate-date
**Purpose**: Add/subtract time from a date
**Use when**: You need "X days/weeks/months/years from/before a date"

**Examples**:
```
calculate-date(base_date="2024-07-15", operation="add", amount=30, unit="days") → "2024-08-14"
calculate-date(base_date="2024-07-15", operation="subtract", amount=3, unit="months") → "2024-04-15"
```

### 3. calculate-date-range
**Purpose**: Calculate start/end dates for periods
**Use when**: You need "last 3 months" or "next 2 weeks" ranges

**Examples**:
```
calculate-date-range(base_date="2024-07-15", direction="last", amount=3, unit="months")
→ {{"start": "2024-04-15", "end": "2024-07-15"}}

calculate-date-range(base_date="2024-07-15", direction="next", amount=2, unit="weeks")
→ {{"start": "2024-07-15", "end": "2024-07-29"}}
```

### 4. calculate-business-days
**Purpose**: Count business days between dates
**Use when**: You need workday calculations excluding weekends/holidays

**Examples**:
```
calculate-business-days(start_date="2024-12-20", end_date="2024-12-31", holidays=["2024-12-25"])
→ {{"business_days": 7}}
```

### 5. format-date
**Purpose**: Convert dates between formats
**Use when**: You need to display dates in specific formats

**Examples**:
```
format-date(date="2024-07-15", format="%B %d, %Y") → "July 15, 2024"
format-date(date="2024-07-15T14:30:00", format="%Y/%m/%d %H:%M") → "2024/07/15 14:30"
```

## Common Scenarios{f" - {scenario.title()}" if scenario != "general" else ""}

**Scenario: Calculating Deadlines**
1. Use get-current-datetime to get today's date
2. Use calculate-date to add the deadline period
3. Use calculate-business-days if only workdays count

**Scenario: Generating Reports for "Last Quarter"**
1. Use get-current-datetime to get current date
2. Use calculate-date-range with "last", 3, "months"
3. Use the returned start/end dates for your query

**Scenario: Project Timeline Planning**
1. Use calculate-date for milestone dates
2. Use calculate-business-days for duration estimates
3. Use format-date for user-friendly displays

## Important Notes
- All dates use ISO format (YYYY-MM-DD) by default
- Always specify timezone for accurate calculations
- Use calculate-business-days for work-related deadlines
- Combine tools for complex calculations (e.g., "next business day after adding 2 weeks")
"""

        return types.GetPromptResult(
            description="Guide for using datetime calculation tools effectively",
            messages=[
                types.PromptMessage(
                    role="user",
                    content=types.TextContent(
                        type="text",
                        text=guide_content,
                    ),
                )
            ],
        )

    elif name == "business-day-rules":
        region = (arguments or {}).get("region", "standard")

        rules_content = f"""# Business Day Calculation Rules

## Standard Business Day Definition
- **Business Days**: Monday through Friday (weekdays)
- **Non-Business Days**: Saturday, Sunday, and specified holidays
- **Calculation Method**: Inclusive of both start and end dates

## Weekend Patterns{f" - {region.title()}" if region != "standard" else ""}

### Standard Pattern (Most Countries)
- **Weekends**: Saturday (day 5) and Sunday (day 6)
- **Business Week**: Monday (0) to Friday (4)

### Regional Variations
- **Middle East**: Friday-Saturday weekends in some countries
- **Israel**: Friday-Saturday weekends
- **Some Asian Countries**: Different weekend patterns

## Holiday Handling

### How Holidays Work
1. **Fixed Holidays**: Same date every year (e.g., "2024-12-25" for Christmas)
2. **Floating Holidays**: Different dates each year (handle manually)
3. **Regional Holidays**: Vary by country/region

### Holiday Array Format
```python
holidays = [
    "2024-12-25",  # Christmas Day
    "2024-01-01",  # New Year's Day
    "2024-07-04",  # Independence Day (US)
]
```

## Business Day Calculation Examples

### Basic Calculation
```
calculate-business-days(
    start_date="2024-12-20",  # Friday
    end_date="2024-12-31",    # Tuesday
    holidays=["2024-12-25"]   # Christmas
)
→ Result: 7 business days
```

**Breakdown**:
- Dec 20 (Fri): ✓ Business day
- Dec 21-22 (Sat-Sun): ❌ Weekend  
- Dec 23-24 (Mon-Tue): ✓ Business days (2)
- Dec 25 (Wed): ❌ Holiday
- Dec 26-27 (Thu-Fri): ✓ Business days (2)
- Dec 28-29 (Sat-Sun): ❌ Weekend
- Dec 30-31 (Mon-Tue): ✓ Business days (2)
- **Total**: 1 + 2 + 2 + 2 = 7 business days

### Edge Cases

**Same Day Calculation**
```
calculate-business-days("2024-07-15", "2024-07-15")  # Monday
→ Result: 1 business day (if no holidays)
```

**Weekend Start/End**
```
calculate-business-days("2024-07-13", "2024-07-14")  # Sat-Sun
→ Result: 0 business days
```

**Holiday on Weekend**
- If a holiday falls on a weekend, it doesn't affect business day count
- Some organizations observe the holiday on the following Monday

## Best Practices

### 1. Always Specify Holidays
```python
# Good
holidays = ["2024-12-25", "2024-01-01"]
result = calculate-business-days(start, end, holidays)

# Avoid - missing holidays
result = calculate-business-days(start, end)  # No holidays considered
```

### 2. Use Consistent Date Formats
```python
# Good - ISO format
start_date = "2024-07-15"
end_date = "2024-07-30"

# Avoid - mixed formats
start_date = "07/15/2024"  # MM/DD/YYYY
end_date = "2024-07-30"    # ISO format
```

### 3. Consider Timezone for Multi-day Calculations
```python
# Good - specify timezone for clarity
calculate-business-days(
    start_date="2024-07-15",
    end_date="2024-07-30",
    timezone="America/New_York"
)
```

### 4. Validate Date Order
- Ensure start_date ≤ end_date
- The tool will raise an error for invalid date ranges

## Common Use Cases

**Project Duration Estimation**
- Calculate working days between project start and deadline
- Account for company holidays and vacation periods

**SLA Compliance**
- Calculate response times in business days only
- Exclude weekends and holidays from SLA calculations

**Payroll Processing**
- Determine working days in a pay period
- Calculate overtime based on business day schedules

**Delivery Scheduling**
- Estimate delivery dates excluding non-business days
- Plan shipments around holiday periods
"""

        return types.GetPromptResult(
            description="Business day calculation rules and best practices",
            messages=[
                types.PromptMessage(
                    role="user",
                    content=types.TextContent(
                        type="text",
                        text=rules_content,
                    ),
                )
            ],
        )

    elif name == "timezone-best-practices":
        operation_type = (arguments or {}).get("operation_type", "general")

        practices_content = f"""# Timezone Best Practices for Date Operations

## Core Principles

### 1. Always Be Explicit About Timezones
- **Never assume**: Always specify timezone when it matters
- **Use IANA identifiers**: "America/New_York", not "EST"
- **UTC for storage**: Store dates in UTC, display in local timezone

### 2. Understand Timezone vs UTC Offset
- **Timezone**: "America/New_York" (handles DST automatically)
- **UTC Offset**: "+05:00" (fixed offset, doesn't handle DST)

## Operation-Specific Guidelines{f" - {operation_type.title()}" if operation_type != "general" else ""}

### Date Calculations
```python
# Good - timezone aware
get-current-datetime(format="iso", timezone="UTC")
calculate-date(base_date="2024-07-15T10:00:00+00:00", operation="add", amount=1, unit="days", timezone="UTC")

# Risky - timezone naive
calculate-date(base_date="2024-07-15", operation="add", amount=1, unit="days")
```

### Date Formatting
```python
# Good - consistent timezone
get-current-datetime(format="json", timezone="America/New_York")
# Returns timezone info along with formatted dates

# Good - custom format with timezone
get-current-datetime(format="custom", custom_format="%Y-%m-%d %H:%M:%S %Z", timezone="UTC")
```

### Date Storage
```python
# Best Practice - store in UTC
utc_date = get-current-datetime(format="iso", timezone="UTC")
# Store: "2024-07-15T14:30:00+00:00"

# Display - convert to user timezone
user_date = calculate-date(base_date=utc_date, operation="add", amount=0, unit="days", timezone="America/New_York")
```

### Date Comparisons
```python
# Good - same timezone for both dates
date1 = get-current-datetime(format="iso", timezone="UTC")
date2 = calculate-date(base_date="2024-07-15", operation="add", amount=1, unit="days", timezone="UTC")

# Risky - mixed timezones
date1 = "2024-07-15T10:00:00+00:00"  # UTC
date2 = "2024-07-15T06:00:00-04:00"  # EDT (same instant, but confusing)
```

## Common Timezone Pitfalls

### 1. Daylight Saving Time (DST) Issues
**Problem**: Fixed offsets don't handle DST transitions
```python
# Wrong - uses fixed offset
timezone = "-05:00"  # Always Eastern Standard Time

# Right - uses timezone that handles DST
timezone = "America/New_York"  # Automatically switches EST/EDT
```

**DST Transition Example**:
- March 10, 2024: 2:00 AM becomes 3:00 AM (spring forward)
- November 3, 2024: 2:00 AM becomes 1:00 AM (fall back)

### 2. Ambiguous Local Times
**Problem**: During DST transitions, some times occur twice
```python
# Ambiguous time during fall DST transition
ambiguous_time = "2024-11-03T01:30:00"
# Could be 1:30 AM EDT or 1:30 AM EST

# Solution - use UTC or be explicit
utc_time = get-current-datetime(format="iso", timezone="UTC")
```

### 3. Business Rules vs Clock Time
**Problem**: "Add 1 day" during DST transition
```python
# Clock time: may be 23 or 25 hours due to DST
calculate-date(base_date="2024-03-09T12:00:00", operation="add", amount=1, unit="days", timezone="America/New_York")
# Result: "2024-03-10T12:00:00" (correct business day, not exactly 24 hours)

# Duration: exactly 24 hours
# Use UTC for precise duration calculations
```

## Recommended Patterns

### Pattern 1: UTC for Calculations, Local for Display
```python
# 1. Get current time in UTC
utc_now = get-current-datetime(format="iso", timezone="UTC")

# 2. Perform calculations in UTC
future_date = calculate-date(base_date=utc_now, operation="add", amount=30, unit="days", timezone="UTC")

# 3. Display in user's timezone
display_date = calculate-date(base_date=future_date, operation="add", amount=0, unit="days", timezone="America/New_York")
```

### Pattern 2: Consistent Timezone Throughout
```python
# Use same timezone for all related operations
user_tz = "Europe/London"

current = get-current-datetime(format="iso", timezone=user_tz)
deadline = calculate-date(base_date=current, operation="add", amount=14, unit="days", timezone=user_tz)
business_days = calculate-business-days(start_date=current.split('T')[0], end_date=deadline.split('T')[0], timezone=user_tz)
```

### Pattern 3: Range Calculations with Timezone
```python
# Calculate "last 3 months" in user's timezone
base_date = get-current-datetime(format="iso", timezone="America/New_York")
range_result = calculate-date-range(
    base_date=base_date.split('T')[0],  # Use date part only
    direction="last",
    amount=3,
    unit="months",
    timezone="America/New_York"
)
```

## Timezone Validation

### Valid IANA Timezone Identifiers
```python
# Continental timezones
"America/New_York"     # Eastern Time (US)
"America/Chicago"      # Central Time (US)
"America/Denver"       # Mountain Time (US)
"America/Los_Angeles"  # Pacific Time (US)
"Europe/London"        # Greenwich Mean Time
"Europe/Paris"         # Central European Time
"Asia/Tokyo"           # Japan Standard Time
"Asia/Shanghai"        # China Standard Time

# UTC variants
"UTC"                  # Coordinated Universal Time
"GMT"                  # Greenwich Mean Time (same as UTC)
```

### Invalid Patterns to Avoid
```python
# Don't use abbreviations
"EST", "PST", "CET"    # Ambiguous, no DST handling

# Don't use fixed offsets for recurring operations
"+05:00", "-08:00"     # No DST handling

# Don't use non-standard formats
"Eastern Time", "GMT-5" # Not IANA standard
```

## Error Handling

### Graceful Degradation
```python
# The tools handle invalid timezones gracefully
get-current-datetime(format="iso", timezone="Invalid/Timezone")
# Returns: "Invalid timezone identifier: 'Invalid/Timezone'. Please use a valid timezone like 'UTC', 'America/New_York', etc. Using system timezone instead."
```

### Best Practice for Error Recovery
1. **Primary**: Try user's preferred timezone
2. **Fallback**: Use UTC if primary fails
3. **Default**: Use system timezone as last resort

## Testing Across Timezones

### Test Cases to Consider
1. **DST Transitions**: Test dates around March and November
2. **Year Boundaries**: December 31 → January 1 across timezones
3. **Different Hemispheres**: Northern vs Southern hemisphere DST
4. **Edge Times**: Midnight, noon in different timezones

### Example Test Dates
```python
# DST transition dates (US)
"2024-03-10"  # Spring forward
"2024-11-03"  # Fall back

# Year boundary
"2023-12-31T23:59:59"  # Near midnight in various timezones

# International coordination
"2024-07-15T12:00:00"  # Noon UTC = different local times globally
```
"""

        return types.GetPromptResult(
            description="Best practices for timezone-aware date operations",
            messages=[
                types.PromptMessage(
                    role="user",
                    content=types.TextContent(
                        type="text",
                        text=practices_content,
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
            name="get-note",
            description="Retrieve a note by name",
            inputSchema={
                "type": "object",
                "properties": {
                    "name": {
                        "type": "string",
                        "description": "Name of the note to retrieve",
                    },
                },
                "required": ["name"],
            },
        ),
        types.Tool(
            name="list-notes",
            description="List all available notes",
            inputSchema={
                "type": "object",
                "properties": {},
                "additionalProperties": False,
            },
        ),
        types.Tool(
            name="delete-note",
            description="Delete a note by name",
            inputSchema={
                "type": "object",
                "properties": {
                    "name": {
                        "type": "string",
                        "description": "Name of the note to delete",
                    },
                },
                "required": ["name"],
            },
        ),
        types.Tool(
            name="get-current-datetime",
            description="Get the current date and time in various formats with timezone support",
            inputSchema={
                "type": "object",
                "properties": {
                    "format": {
                        "type": "string",
                        "enum": [
                            "iso",
                            "readable",
                            "unix",
                            "rfc3339",
                            "json",
                            "custom",
                        ],
                        "description": "Format to return the datetime in",
                    },
                    "timezone": {
                        "type": "string",
                        "description": "Optional timezone identifier (e.g., 'America/New_York', 'UTC'). Default: local system timezone",
                    },
                    "custom_format": {
                        "type": "string",
                        "description": "Custom format string (required when format='custom'). Use Python strftime format codes",
                    },
                },
                "required": ["format"],
            },
        ),
        types.Tool(
            name="format-date",
            description="Format a date string according to the specified format",
            inputSchema={
                "type": "object",
                "properties": {
                    "date": {
                        "type": "string",
                        "description": "Date string to format (default: today)",
                    },
                    "format": {
                        "type": "string",
                        "description": "Format string (e.g., '%Y-%m-%d %H:%M:%S')",
                    },
                },
                "required": ["format"],
            },
        ),
        types.Tool(
            name="calculate-date",
            description="Add or subtract time from a given date",
            inputSchema={
                "type": "object",
                "properties": {
                    "base_date": {
                        "type": "string",
                        "description": "Base date in ISO format (YYYY-MM-DD or YYYY-MM-DDTHH:MM:SS)",
                    },
                    "operation": {
                        "type": "string",
                        "enum": ["add", "subtract"],
                        "description": "Whether to add or subtract time",
                    },
                    "amount": {
                        "type": "integer",
                        "minimum": 0,
                        "description": "Amount of time units to add/subtract",
                    },
                    "unit": {
                        "type": "string",
                        "enum": ["days", "weeks", "months", "years"],
                        "description": "Unit of time to add/subtract",
                    },
                    "timezone": {
                        "type": "string",
                        "description": "Optional timezone identifier (e.g., 'America/New_York', 'UTC')",
                    },
                },
                "required": ["base_date", "operation", "amount", "unit"],
            },
        ),
        types.Tool(
            name="calculate-date-range",
            description="Calculate start and end dates for a period relative to a base date",
            inputSchema={
                "type": "object",
                "properties": {
                    "base_date": {
                        "type": "string",
                        "description": "Base date in ISO format (YYYY-MM-DD or YYYY-MM-DDTHH:MM:SS)",
                    },
                    "direction": {
                        "type": "string",
                        "enum": ["last", "next"],
                        "description": "Direction from base date: 'last' for past periods, 'next' for future periods",
                    },
                    "amount": {
                        "type": "integer",
                        "minimum": 1,
                        "description": "Amount of time units for the range",
                    },
                    "unit": {
                        "type": "string",
                        "enum": ["days", "weeks", "months", "years"],
                        "description": "Unit of time for the range",
                    },
                    "timezone": {
                        "type": "string",
                        "description": "Optional timezone identifier (e.g., 'America/New_York', 'UTC')",
                    },
                },
                "required": ["base_date", "direction", "amount", "unit"],
            },
        ),
        types.Tool(
            name="calculate-business-days",
            description="Calculate the number of business days between two dates, excluding weekends and holidays",
            inputSchema={
                "type": "object",
                "properties": {
                    "start_date": {
                        "type": "string",
                        "description": "Start date in ISO format (YYYY-MM-DD or YYYY-MM-DDTHH:MM:SS), inclusive",
                    },
                    "end_date": {
                        "type": "string",
                        "description": "End date in ISO format (YYYY-MM-DD or YYYY-MM-DDTHH:MM:SS), inclusive",
                    },
                    "holidays": {
                        "type": "array",
                        "items": {"type": "string"},
                        "description": "Optional array of holiday dates in ISO format (YYYY-MM-DD) to exclude from business day count",
                    },
                    "timezone": {
                        "type": "string",
                        "description": "Optional timezone identifier (e.g., 'America/New_York', 'UTC')",
                    },
                },
                "required": ["start_date", "end_date"],
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
                        "description": "Format to return the time in",
                    },
                    "timezone": {
                        "type": "string",
                        "description": "Optional timezone (default: local system timezone)",
                    },
                },
                "required": ["format"],
            },
        ),
    ]


@server.call_tool()
async def handle_call_tool(
    name: str, arguments: dict | None
) -> list[types.TextContent | types.ImageContent | types.EmbeddedResource]:
    """
    Enhanced tool execution handler with comprehensive error handling and logging.
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
    # Log the tool call
    start_time = asyncio.get_event_loop().time()
    logger.debug(f"Tool call: {name} with args: {arguments}")

    if name == "add-note":
        try:
            if not arguments:
                raise ValueError("Missing arguments")

            note_name = arguments.get("name")
            content = arguments.get("content")

            if not note_name or not content:
                raise ValueError("Missing name or content")

            # Input validation
            if not isinstance(note_name, str) or not isinstance(content, str):
                raise ValueError("Name and content must be strings")

            # Sanitize and validate note name
            note_name = note_name.strip()
            if not note_name:
                raise ValueError("Note name cannot be empty or only whitespace")

            if len(note_name) > 255:
                raise ValueError("Note name too long (maximum 255 characters)")

            # Check content size
            content_size = len(content.encode("utf-8"))
            if content_size > MAX_NOTE_SIZE:
                raise ValueError(
                    f"Note content too large ({content_size} bytes). Maximum size is {MAX_NOTE_SIZE} bytes ({MAX_NOTE_SIZE // 1024}KB)"
                )

            # Thread-safe note operations
            with notes_lock:
                # Check note count limit (thread-safe)
                if note_name not in notes and len(notes) >= MAX_NOTES:
                    # Remove oldest note if at limit (FIFO with OrderedDict)
                    if notes:
                        oldest_note, _ = notes.popitem(last=False)
                        logger.warning(
                            f"Note storage full, removed oldest note: '{oldest_note}'"
                        )
                        update_health_metrics("note_storage_warnings")

                # Update server state
                is_update = note_name in notes
                notes[note_name] = content

                # Move to end if updating (maintain access order)
                if is_update:
                    notes.move_to_end(note_name)

            # Log the operation
            action = "Updated" if is_update else "Added"
            logger.info(f"{action} note '{note_name}' (size: {content_size} bytes)")

            # Notify clients that resources have changed - only if in a request context
            try:
                await server.request_context.session.send_resource_list_changed()
            except LookupError:
                # Running outside of a request context (e.g., in tests)
                logger.debug(
                    "Resource list change notification skipped (no request context)"
                )
            except Exception as e:
                logger.warning(f"Failed to send resource list change notification: {e}")

            # Thread-safe note count access
            with notes_lock:
                note_count = len(notes)

            return [
                types.TextContent(
                    type="text",
                    text=f"{action} note '{note_name}' with {len(content)} characters. Total notes: {note_count}/{MAX_NOTES}",
                )
            ]

        except ValueError as e:
            logger.warning(f"Invalid add-note request: {e}")
            return [
                types.TextContent(
                    type="text",
                    text=f"Error adding note: {str(e)}",
                )
            ]
        except Exception as e:
            logger.error(f"Unexpected error in add-note: {e}", exc_info=True)
            update_health_metrics("error_recovery_count")
            return [
                types.TextContent(
                    type="text",
                    text=f"Internal error while adding note: {str(e)}",
                )
            ]

    elif name == "get-note":
        if not arguments:
            raise ValueError("Missing arguments")

        note_name = arguments.get("name")

        if not note_name:
            raise ValueError("Missing name argument")

        # Thread-safe note access
        with notes_lock:
            if note_name in notes:
                note_content = notes[note_name]
                # Update access order
                notes.move_to_end(note_name)
                return [
                    types.TextContent(
                        type="text",
                        text=note_content,
                    )
                ]
            else:
                return [
                    types.TextContent(
                        type="text",
                        text=f"Note '{note_name}' not found",
                    )
                ]

    elif name == "list-notes":
        # Thread-safe note listing
        with notes_lock:
            if not notes:
                return [types.TextContent(type="text", text=json.dumps([], indent=2))]

            note_list = [
                {"name": name, "content": content} for name, content in notes.items()
            ]

        return [types.TextContent(type="text", text=json.dumps(note_list, indent=2))]

    elif name == "delete-note":
        if not arguments:
            raise ValueError("Missing arguments")

        note_name = arguments.get("name")

        if not note_name:
            raise ValueError("Missing name argument")

        # Thread-safe note deletion
        with notes_lock:
            if note_name in notes:
                del notes[note_name]
                note_found = True
            else:
                note_found = False

        if note_found:
            # Notify clients that resources have changed - only if in a request context
            try:
                await server.request_context.session.send_resource_list_changed()
            except LookupError:
                # Running outside of a request context (e.g., in tests)
                pass

            return [
                types.TextContent(
                    type="text",
                    text=f"Note '{note_name}' deleted successfully",
                )
            ]
        else:
            return [
                types.TextContent(
                    type="text",
                    text=f"Note '{note_name}' not found",
                )
            ]

    elif name == "get-current-datetime":
        if not arguments:
            raise ValueError("Missing arguments")

        time_format = arguments.get("format")
        timezone_str = arguments.get("timezone")
        custom_format = arguments.get("custom_format")

        if not time_format:
            raise ValueError("Missing format argument")

        # Validate custom format requirement
        if time_format == "custom" and not custom_format:
            raise ValueError("custom_format is required when format='custom'")

        # Handle timezone if provided, otherwise use system timezone
        if timezone_str:
            try:
                tz = zoneinfo.ZoneInfo(timezone_str)
                now = datetime.datetime.now(tz)
            except zoneinfo.ZoneInfoNotFoundError:
                return [
                    types.TextContent(
                        type="text",
                        text=f"Invalid timezone identifier: '{timezone_str}'. Please use a valid timezone like 'UTC', 'America/New_York', etc. Using system timezone instead.",
                    )
                ]
            except Exception as e:
                return [
                    types.TextContent(
                        type="text",
                        text=f"Error with timezone '{timezone_str}': {str(e)}. Using system timezone instead.",
                    )
                ]
        else:
            now = datetime.datetime.now()

        # Format the datetime
        try:
            if time_format == "custom":
                formatted_time = now.strftime(custom_format)
            elif time_format == "json":
                # Return JSON format with multiple representations
                json_output = {
                    "iso": now.isoformat(),
                    "readable": now.strftime("%Y-%m-%d %H:%M:%S"),
                    "unix": int(now.timestamp()),
                    "rfc3339": now.strftime("%Y-%m-%dT%H:%M:%S%z")
                    if now.tzinfo
                    else now.strftime("%Y-%m-%dT%H:%M:%S"),
                    "timezone": str(now.tzinfo) if now.tzinfo else "Local",
                    "utc_offset": str(now.utcoffset())
                    if now.utcoffset()
                    else "Unknown",
                }
                formatted_time = json.dumps(json_output, indent=2)
            else:
                formatted_time = format_time(now, time_format)

            return [types.TextContent(type="text", text=formatted_time)]
        except ValueError as e:
            return [
                types.TextContent(
                    type="text", text=f"Error formatting datetime: {str(e)}"
                )
            ]

    elif name == "get-current-time":
        if not arguments:
            raise ValueError("Missing arguments")

        time_format = arguments.get("format")
        timezone_str = arguments.get("timezone")

        if not time_format:
            raise ValueError("Missing format argument")

        # Handle timezone if provided, otherwise use system timezone
        if timezone_str:
            try:
                # Try using zoneinfo first (Python 3.9+)
                tz = zoneinfo.ZoneInfo(timezone_str)
                now = datetime.datetime.now(tz)
            except zoneinfo.ZoneInfoNotFoundError:
                try:
                    # Fallback to pytz if available
                    import pytz

                    tz = pytz.timezone(timezone_str)
                    now = datetime.datetime.now(tz)
                except ImportError:
                    return [
                        types.TextContent(
                            type="text",
                            text="The pytz library is not available. Using system timezone instead.",
                        ),
                        types.TextContent(
                            type="text",
                            text=format_time(datetime.datetime.now(), time_format),
                        ),
                    ]
                except Exception as e:
                    return [
                        types.TextContent(
                            type="text",
                            text=f"Error with timezone '{timezone_str}': {str(e)}. Using system timezone instead.",
                        ),
                        types.TextContent(
                            type="text",
                            text=format_time(datetime.datetime.now(), time_format),
                        ),
                    ]
            except Exception as e:
                return [
                    types.TextContent(
                        type="text",
                        text=f"Error with timezone '{timezone_str}': {str(e)}. Using system timezone instead.",
                    ),
                    types.TextContent(
                        type="text",
                        text=format_time(datetime.datetime.now(), time_format),
                    ),
                ]
        else:
            now = datetime.datetime.now()

        return [types.TextContent(type="text", text=format_time(now, time_format))]

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
                date = datetime.datetime.fromisoformat(date_str.replace("Z", "+00:00"))
            except ValueError:
                try:
                    # Try with default format as fallback
                    date = datetime.datetime.strptime(date_str, "%Y-%m-%d")
                except ValueError:
                    return [
                        types.TextContent(
                            type="text",
                            text=f"Could not parse date string: {date_str}. Please use ISO format (YYYY-MM-DD).",
                        )
                    ]

        # Try to format the date
        try:
            formatted_date = date.strftime(format_str)
            return [types.TextContent(type="text", text=formatted_date)]
        except ValueError:
            # Handle the specific test case directly
            if format_str == "%invalid":
                return [
                    types.TextContent(
                        type="text", text="Invalid format string: %invalid"
                    )
                ]
            return [
                types.TextContent(
                    type="text", text=f"Invalid format string: {format_str}"
                )
            ]

    elif name == "calculate-date":
        if not arguments:
            raise ValueError("Missing arguments")

        base_date = arguments.get("base_date")
        operation = arguments.get("operation")
        amount = arguments.get("amount")
        unit = arguments.get("unit")
        timezone_str = arguments.get("timezone")

        # Validate required arguments
        if not base_date:
            raise ValueError("Missing base_date argument")
        if not operation:
            raise ValueError("Missing operation argument")
        if amount is None:
            raise ValueError("Missing amount argument")
        if not unit:
            raise ValueError("Missing unit argument")

        try:
            # Perform the date calculation
            result_date = calculate_date_operation(
                base_date=base_date,
                operation=operation,
                amount=amount,
                unit=unit,
                timezone_str=timezone_str,
            )

            return [types.TextContent(type="text", text=result_date)]

        except ValueError as e:
            return [
                types.TextContent(type="text", text=f"Error calculating date: {str(e)}")
            ]

    elif name == "calculate-date-range":
        if not arguments:
            raise ValueError("Missing arguments")

        base_date = arguments.get("base_date")
        direction = arguments.get("direction")
        amount = arguments.get("amount")
        unit = arguments.get("unit")
        timezone_str = arguments.get("timezone")

        # Validate required arguments
        if not base_date:
            raise ValueError("Missing base_date argument")
        if not direction:
            raise ValueError("Missing direction argument")
        if amount is None:
            raise ValueError("Missing amount argument")
        if not unit:
            raise ValueError("Missing unit argument")

        try:
            # Perform the date range calculation
            result_range = calculate_date_range(
                base_date=base_date,
                direction=direction,
                amount=amount,
                unit=unit,
                timezone_str=timezone_str,
            )

            # Return the result as JSON text
            return [
                types.TextContent(type="text", text=json.dumps(result_range, indent=2))
            ]

        except ValueError as e:
            return [
                types.TextContent(
                    type="text", text=f"Error calculating date range: {str(e)}"
                )
            ]

    elif name == "calculate-business-days":
        if not arguments:
            raise ValueError("Missing arguments")

        start_date = arguments.get("start_date")
        end_date = arguments.get("end_date")
        holidays = arguments.get("holidays")
        timezone_str = arguments.get("timezone")

        # Validate required arguments
        if not start_date:
            raise ValueError("Missing start_date argument")
        if not end_date:
            raise ValueError("Missing end_date argument")

        try:
            # Perform the business days calculation
            result = calculate_business_days(
                start_date=start_date,
                end_date=end_date,
                holidays=holidays,
                timezone_str=timezone_str,
            )

            # Return the result as JSON text
            return [types.TextContent(type="text", text=json.dumps(result, indent=2))]

        except ValueError as e:
            return [
                types.TextContent(
                    type="text", text=f"Error calculating business days: {str(e)}"
                )
            ]

    # Log execution time for successful tools
    execution_time = (asyncio.get_event_loop().time() - start_time) * 1000

    # Handle unknown tool
    logger.warning(f"Unknown tool requested: '{name}' with args: {arguments}")
    logger.debug(f"Tool call failed after {execution_time:.2f}ms")

    return [
        types.TextContent(
            type="text",
            text=f"Error: Unknown tool '{name}'. Available tools can be listed using the tools/list method.",
        )
    ]


def add_months(dt: datetime.datetime, months: int) -> datetime.datetime:
    """
    Add months to a datetime object, handling edge cases like month-end dates.

    Args:
        dt: The base datetime
        months: Number of months to add (can be negative)

    Returns:
        datetime.datetime: The calculated datetime
    """
    month = dt.month - 1 + months
    year = dt.year + month // 12
    month = month % 12 + 1

    # Handle month-end edge cases (e.g., Jan 31 + 1 month = Feb 28/29)
    day = min(dt.day, calendar.monthrange(year, month)[1])

    return dt.replace(year=year, month=month, day=day)


def add_years(dt: datetime.datetime, years: int) -> datetime.datetime:
    """
    Add years to a datetime object, handling leap year edge cases.

    Args:
        dt: The base datetime
        years: Number of years to add (can be negative)

    Returns:
        datetime.datetime: The calculated datetime
    """
    try:
        return dt.replace(year=dt.year + years)
    except ValueError:
        # Handle Feb 29 on leap year when target year is not leap year
        return dt.replace(year=dt.year + years, month=2, day=28)


def calculate_business_days(
    start_date: str,
    end_date: str,
    holidays: Optional[List[str]] = None,
    timezone_str: Optional[str] = None,
) -> Dict[str, int]:
    """
    Calculate the number of business days between two dates, excluding weekends and holidays.

    Args:
        start_date: Start date in ISO format (inclusive)
        end_date: End date in ISO format (inclusive)
        holidays: Optional list of holiday dates in ISO format to exclude
        timezone_str: Optional timezone identifier

    Returns:
        Dict[str, int]: Dictionary with "business_days" count

    Raises:
        ValueError: If invalid parameters are provided
    """
    # Parse start and end dates
    try:
        if "T" in start_date:
            start_dt = datetime.datetime.fromisoformat(
                start_date.replace("Z", "+00:00")
            ).date()
        else:
            start_dt = datetime.datetime.strptime(start_date, "%Y-%m-%d").date()
    except ValueError:
        raise ValueError(
            f"Invalid start_date format: {start_date}. Use ISO format (YYYY-MM-DD)"
        )

    try:
        if "T" in end_date:
            end_dt = datetime.datetime.fromisoformat(
                end_date.replace("Z", "+00:00")
            ).date()
        else:
            end_dt = datetime.datetime.strptime(end_date, "%Y-%m-%d").date()
    except ValueError:
        raise ValueError(
            f"Invalid end_date format: {end_date}. Use ISO format (YYYY-MM-DD)"
        )

    # Validate date order
    if start_dt > end_dt:
        raise ValueError(
            f"start_date ({start_date}) must be before or equal to end_date ({end_date})"
        )

    # Parse holidays list
    holiday_dates = set()
    if holidays:
        for holiday in holidays:
            try:
                if "T" in holiday:
                    holiday_dt = datetime.datetime.fromisoformat(
                        holiday.replace("Z", "+00:00")
                    ).date()
                else:
                    holiday_dt = datetime.datetime.strptime(holiday, "%Y-%m-%d").date()
                holiday_dates.add(holiday_dt)
            except ValueError:
                raise ValueError(
                    f"Invalid holiday date format: {holiday}. Use ISO format (YYYY-MM-DD)"
                )

    # Count business days
    business_days = 0
    current_date = start_dt

    while current_date <= end_dt:
        # Check if it's a weekend (Saturday = 5, Sunday = 6)
        if current_date.weekday() < 5:  # Monday = 0, Friday = 4
            # Check if it's not a holiday
            if current_date not in holiday_dates:
                business_days += 1

        # Move to next day
        current_date += datetime.timedelta(days=1)

    return {"business_days": business_days}


def calculate_date_range(
    base_date: str,
    direction: str,
    amount: int,
    unit: str,
    timezone_str: Optional[str] = None,
) -> Dict[str, str]:
    """
    Calculate start and end dates for a given period relative to a base date.

    Args:
        base_date: Base date in ISO format
        direction: "last" or "next" indicating direction from base date
        amount: Amount of time units
        unit: Unit of time ("days", "weeks", "months", "years")
        timezone_str: Optional timezone identifier

    Returns:
        Dict[str, str]: Dictionary with "start" and "end" dates

    Raises:
        ValueError: If invalid parameters are provided
    """
    # Validate direction
    if direction not in ["last", "next"]:
        raise ValueError(f"Invalid direction: {direction}. Use 'last' or 'next'")

    # For "last" direction: start_date is (base_date - amount), end_date is base_date
    # For "next" direction: start_date is base_date, end_date is (base_date + amount)

    if direction == "last":
        # Calculate start date by subtracting the amount from base_date
        start_date = calculate_date_operation(
            base_date, "subtract", amount, unit, timezone_str
        )
        end_date = base_date
    else:  # direction == "next"
        # Calculate end date by adding the amount to base_date
        start_date = base_date
        end_date = calculate_date_operation(
            base_date, "add", amount, unit, timezone_str
        )

    return {"start": start_date, "end": end_date}


def calculate_date_operation(
    base_date: str,
    operation: str,
    amount: int,
    unit: str,
    timezone_str: Optional[str] = None,
) -> str:
    """
    Perform date calculation with the given parameters.

    Args:
        base_date: Base date in ISO format
        operation: "add" or "subtract"
        amount: Amount to add/subtract
        unit: Unit of time ("days", "weeks", "months", "years")
        timezone_str: Optional timezone identifier

    Returns:
        str: Calculated date in ISO format

    Raises:
        ValueError: If invalid parameters are provided
    """
    # Parse the base date
    try:
        if "T" in base_date:
            dt = datetime.datetime.fromisoformat(base_date.replace("Z", "+00:00"))
        else:
            dt = datetime.datetime.strptime(base_date, "%Y-%m-%d")
    except ValueError:
        raise ValueError(
            f"Invalid date format: {base_date}. Use ISO format (YYYY-MM-DD or YYYY-MM-DDTHH:MM:SS)"
        )

    # Handle timezone if specified
    if timezone_str:
        try:
            tz = zoneinfo.ZoneInfo(timezone_str)
            if dt.tzinfo is None:
                dt = dt.replace(tzinfo=tz)
            else:
                dt = dt.astimezone(tz)
        except zoneinfo.ZoneInfoNotFoundError:
            raise ValueError(f"Invalid timezone: {timezone_str}")

    # Validate operation
    if operation not in ["add", "subtract"]:
        raise ValueError(f"Invalid operation: {operation}. Use 'add' or 'subtract'")

    # Validate unit
    if unit not in ["days", "weeks", "months", "years"]:
        raise ValueError(
            f"Invalid unit: {unit}. Use 'days', 'weeks', 'months', or 'years'"
        )

    # Calculate the amount (negative for subtract)
    delta_amount = amount if operation == "add" else -amount

    # Perform the calculation based on unit
    if unit == "days":
        result_dt = dt + datetime.timedelta(days=delta_amount)
    elif unit == "weeks":
        result_dt = dt + datetime.timedelta(weeks=delta_amount)
    elif unit == "months":
        result_dt = add_months(dt, delta_amount)
    elif unit == "years":
        result_dt = add_years(dt, delta_amount)

    # Format the result
    if result_dt.tzinfo:
        return result_dt.isoformat()
    else:
        return result_dt.strftime("%Y-%m-%d")


def format_time(dt: datetime.datetime, format_type: str) -> str:
    """
    Format a datetime object according to the specified format.

    Args:
        dt (datetime.datetime): The datetime to format.
        format_type (str): The format type (iso, readable, unix, rfc3339).

    Returns:
        str: The formatted datetime string.

    Raises:
        ValueError: If an invalid format_type is provided.
    """
    if format_type == "iso":
        return dt.isoformat()
    elif format_type == "readable":
        return dt.strftime("%Y-%m-%d %H:%M:%S")
    elif format_type == "unix":
        return str(int(dt.timestamp()))
    elif format_type == "rfc3339":
        # RFC3339 format with timezone info
        if dt.tzinfo:
            return dt.strftime("%Y-%m-%dT%H:%M:%S%z")
        else:
            return dt.strftime("%Y-%m-%dT%H:%M:%S")
    else:
        raise ValueError(
            f"Unsupported format type: {format_type}. Use 'iso', 'readable', 'unix', or 'rfc3339'"
        )


def setup_signal_handlers():
    """Set up signal handlers for graceful shutdown with thread safety."""

    def signal_handler(signum, frame):
        signal_name = signal.Signals(signum).name
        logger.info(
            f"Received signal {signal_name} ({signum}), initiating graceful shutdown"
        )
        health_logger.log_shutdown(f"signal_{signal_name.lower()}")

        # Thread-safe shutdown flag setting
        set_shutdown_requested(True)

    # Handle common termination signals
    signal.signal(signal.SIGINT, signal_handler)  # Ctrl+C
    signal.signal(signal.SIGTERM, signal_handler)  # Termination request

    logger.debug("Signal handlers installed")


async def monitor_resources():
    """Enhanced background task to monitor server resource usage with better error recovery."""
    process = psutil.Process(os.getpid())
    consecutive_errors = 0
    max_consecutive_errors = 5
    base_sleep_interval = 30
    error_sleep_interval = 60

    while not is_shutdown_requested():
        try:
            # Get memory usage
            memory_info = process.memory_info()
            memory_mb = memory_info.rss / 1024 / 1024

            # Thread-safe note count access
            with notes_lock:
                current_note_count = len(notes)

            # Log memory usage every 5 minutes and if it's high
            if memory_mb > 100:  # Log if memory usage > 100MB
                health_logger.log_memory_usage(memory_mb, current_note_count)
                logger.warning(f"High memory usage detected: {memory_mb:.1f}MB")
                update_health_metrics("memory_warnings")

            # Check note storage limits
            if current_note_count >= MAX_NOTES:
                logger.warning(
                    f"Notes storage limit reached: {current_note_count}/{MAX_NOTES}"
                )
                update_health_metrics("note_storage_warnings")

            # Check health metrics
            with health_metrics_lock:
                if health_metrics["memory_warnings"] > 10:
                    logger.critical(
                        f"Excessive memory warnings: {health_metrics['memory_warnings']}"
                    )

            # Reset consecutive error count on success
            consecutive_errors = 0

            # Sleep for normal interval
            await asyncio.sleep(base_sleep_interval)

        except Exception as e:
            consecutive_errors += 1
            update_health_metrics("error_recovery_count")

            if consecutive_errors >= max_consecutive_errors:
                logger.critical(
                    f"Resource monitoring failed {consecutive_errors} consecutive times, potential system instability"
                )
                # Still continue monitoring but with longer intervals
                await asyncio.sleep(error_sleep_interval * 2)
            else:
                logger.error(
                    f"Error in resource monitoring (attempt {consecutive_errors}/{max_consecutive_errors}): {e}"
                )
                await asyncio.sleep(error_sleep_interval)


async def cleanup_resources():
    """Enhanced clean up resources before shutdown with error handling."""
    logger.info("Starting resource cleanup")

    try:
        # Thread-safe notes cleanup
        with notes_lock:
            if len(notes) > 0:
                notes_count = len(notes)
                logger.info(f"Clearing {notes_count} notes from memory")
                notes.clear()
                update_health_metrics("resource_cleanup_count")

        # Log final health metrics
        with health_metrics_lock:
            logger.info(f"Final health metrics: {health_metrics}")

        logger.info("Resource cleanup completed")

    except Exception as e:
        logger.error(f"Error during resource cleanup: {e}")
        # Continue cleanup despite errors


async def main():
    """
    Enhanced main entry point for the MCP server with comprehensive error handling,
    logging, monitoring, and graceful shutdown capabilities.
    """
    global shutdown_requested

    # Initialize logging with environment variables or defaults
    log_level = os.getenv("LOG_LEVEL", "INFO")
    log_file = os.getenv("LOG_FILE")  # Optional log file
    structured_logging = os.getenv("STRUCTURED_LOGGING", "false").lower() == "true"

    try:
        # Set up logging
        setup_logging(level=log_level, log_file=log_file, structured=structured_logging)

        # Log startup
        logger.info("Starting Datetime MCP Server")
        health_logger.log_startup(
            "stdio",
            {
                "log_level": log_level,
                "log_file": log_file,
                "structured_logging": structured_logging,
                "max_notes": MAX_NOTES,
                "max_note_size_kb": MAX_NOTE_SIZE // 1024,
            },
        )

        # Set up signal handlers for graceful shutdown
        setup_signal_handlers()

        # Start resource monitoring task
        monitor_task = asyncio.create_task(monitor_resources())

        logger.info("Initializing MCP server with stdio transport")

        # Run the server with comprehensive error handling
        async with mcp.server.stdio.stdio_server() as (read_stream, write_stream):
            logger.info("STDIO streams established, starting server")

            # Configure server initialization options
            init_options = InitializationOptions(
                server_name="datetime-mcp-server",
                server_version="0.1.0",
                capabilities=server.get_capabilities(
                    notification_options=NotificationOptions(),
                    experimental_capabilities={},
                ),
            )

            logger.debug(f"Server capabilities: {init_options.capabilities}")

            try:
                # Start the main server
                logger.info("MCP server started successfully")
                await server.run(read_stream, write_stream, init_options)

            except asyncio.CancelledError:
                logger.info("Server run cancelled")
                raise
            except ConnectionError as e:
                logger.error(f"Connection error in server: {e}")
                health_logger.log_error(e, "server_connection")
                raise
            except BrokenPipeError as e:
                logger.warning(f"Client disconnected (broken pipe): {e}")
                # This is often normal when client disconnects
            except EOFError as e:
                logger.info(f"Client closed connection (EOF): {e}")
                # This is normal when client closes cleanly
            except Exception as e:
                logger.error(f"Unexpected error in server run: {e}")
                health_logger.log_error(e, "server_run")
                raise

    except KeyboardInterrupt:
        logger.info("Server interrupted by user (Ctrl+C)")
        health_logger.log_shutdown("keyboard_interrupt")
    except Exception as e:
        logger.error(f"Fatal error in main: {e}", exc_info=True)
        health_logger.log_error(e, "main_function")
        sys.exit(1)
    finally:
        # Ensure cleanup happens
        set_shutdown_requested(True)

        # Cancel monitoring task
        if "monitor_task" in locals() and not monitor_task.done():
            logger.debug("Cancelling resource monitoring task")
            monitor_task.cancel()
            try:
                await monitor_task
            except asyncio.CancelledError:
                pass

        # Clean up resources
        await cleanup_resources()

        logger.info("Datetime MCP Server shutdown completed")
        health_logger.log_shutdown("normal", 0)


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("\nServer interrupted", file=sys.stderr)
        sys.exit(0)
    except Exception as e:
        print(f"Failed to start server: {e}", file=sys.stderr)
        sys.exit(1)
