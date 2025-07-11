# DateTime MCP Server

A comprehensive MCP (Model Context Protocol) server that provides precise datetime calculation tools for LLMs, along with timezone support and note management functionality.

## Overview

This server implements the MCP protocol and offers mathematical date operations that LLMs can call when they need accurate temporal calculations. Instead of parsing natural language date expressions, it provides precise mathematical date operations for reliable, consistent results.

Key features include:
- **Precise Date Calculations**: Add/subtract days, weeks, months, years with proper edge case handling
- **Business Day Calculations**: Count business days excluding weekends and holidays
- **Date Range Operations**: Calculate "last 3 months" or "next 2 weeks" date ranges  
- **Timezone Support**: Full timezone-aware operations with DST handling
- **Multiple Date Formats**: ISO, RFC3339, Unix timestamps, custom formats
- **Comprehensive Note Management**: Full CRUD operations for notes
- **LLM Guidance Prompts**: Built-in prompts to help LLMs use datetime tools effectively

## Features

### 🛠️ Date Calculation Tools

#### `calculate-date`
Add or subtract time periods from dates with proper edge case handling.

```json
{
  "base_date": "2024-07-15",
  "operation": "add", 
  "amount": 30,
  "unit": "days",
  "timezone": "UTC"
}
// Returns: "2024-08-14"
```

**Supported units**: `days`, `weeks`, `months`, `years`
**Features**: Leap year handling, month-end adjustments, timezone-aware calculations

#### `calculate-date-range`
Calculate start and end dates for time periods.

```json
{
  "base_date": "2024-07-15",
  "direction": "last",
  "amount": 3, 
  "unit": "months",
  "timezone": "America/New_York"
}
// Returns: {"start": "2024-04-15", "end": "2024-07-15"}
```

**Directions**: `last` (backwards), `next` (forwards)
**Use cases**: "Last quarter", "Next 2 weeks", reporting periods

#### `calculate-business-days`
Count business days between dates, excluding weekends and holidays.

```json
{
  "start_date": "2024-12-20",
  "end_date": "2024-12-31", 
  "holidays": ["2024-12-25"],
  "timezone": "UTC"
}
// Returns: {"business_days": 7}
```

**Features**: Configurable holidays, timezone support, weekend exclusion

#### `get-current-datetime`
Enhanced current datetime with multiple formats and timezone support.

```json
{
  "format": "json",
  "timezone": "America/New_York"
}
// Returns full JSON with iso, readable, unix, rfc3339, timezone info
```

**Formats**: `iso`, `readable`, `unix`, `rfc3339`, `json`, `custom`
**Features**: 598+ supported timezones, custom format strings, DST handling

#### `format-date`
Convert dates between different formats.

```json
{
  "date": "2024-07-15",
  "format": "%B %d, %Y"
}
// Returns: "July 15, 2024"
```

### 📝 Note Management Tools

Complete CRUD operations for note management:

- **`add-note`**: Create new notes
- **`get-note`**: Retrieve specific notes  
- **`list-notes`**: List all available notes
- **`delete-note`**: Remove notes

### 🌍 Timezone Resources

#### `datetime://timezone-info`
Current timezone information including DST status and UTC offset.

#### `datetime://supported-timezones` 
Complete list of 598+ supported timezones organized by 17 regions.

#### `datetime://current`
Current date and time in multiple formats.

### 🧠 LLM Guidance Prompts

#### `datetime-calculation-guide`
Comprehensive guide showing when and how to use each datetime tool with practical examples.

#### `business-day-rules`
Detailed explanation of business day calculation rules, holiday handling, and edge cases.

#### `timezone-best-practices`
Guidelines for timezone-aware operations, DST handling, and common pitfalls to avoid.

## Installation

1. Clone the repository:
```bash
git clone https://github.com/bossjones/datetime-mcp-server.git
cd datetime-mcp-server
```

2. Create a virtual environment:
```bash
uv venv
source .venv/bin/activate
```

3. Install the dependencies:
```bash
uv sync
```

## Usage

### Running the Server

To run the server:

```bash
uv run python -m datetime_mcp_server.server
```

The server will start and listen on stdin/stdout for MCP protocol messages.

### Example Use Cases

#### Project Planning
```bash
# Get current date
uv run mcp tools call get-current-datetime --arguments '{"format": "iso", "timezone": "UTC"}'

# Calculate project deadline (3 months from now)
uv run mcp tools call calculate-date --arguments '{"base_date": "2024-07-15", "operation": "add", "amount": 3, "unit": "months"}'

# Count business days for the project
uv run mcp tools call calculate-business-days --arguments '{"start_date": "2024-07-15", "end_date": "2024-10-15", "holidays": ["2024-09-02"]}'
```

#### Reporting Periods
```bash
# Get "last quarter" date range
uv run mcp tools call calculate-date-range --arguments '{"base_date": "2024-07-15", "direction": "last", "amount": 3, "unit": "months"}'

# Format dates for presentation
uv run mcp tools call format-date --arguments '{"date": "2024-07-15", "format": "%B %d, %Y"}'
```

#### Timezone Operations
```bash
# Get current time in multiple timezones
uv run mcp tools call get-current-datetime --arguments '{"format": "json", "timezone": "Asia/Tokyo"}'

# List all supported timezones
uv run mcp resources read datetime://supported-timezones
```

## Development

### Installing Development Dependencies

```bash
uv sync --dev
```

### Running Tests

The project includes comprehensive test coverage:

```bash
# Run all tests (37 total tests)
./run_tests.sh

# Unit tests (23 tests)
uv run pytest tests/acceptance/test_server.py

# Integration tests (14 tests)  
uv run pytest tests/acceptance/test_server_integration.py
```

#### Test Coverage

- **Unit Tests**: Individual tool functionality, error handling, edge cases
- **Integration Tests**: End-to-end workflows, complex scenarios, performance validation
- **Edge Case Testing**: Leap years, month-end dates, timezone transitions, holiday handling
- **Performance Testing**: All operations meet <50ms requirement

### Architecture

The server is built with:
- **Pure Python**: No external dependencies, uses only standard library
- **Mathematical Operations**: No natural language parsing, only precise date arithmetic
- **Standard Library**: `datetime`, `zoneinfo`, `calendar` for reliability
- **MCP Protocol**: Full implementation of resources, tools, and prompts
- **Async Support**: Built on asyncio for performance

## API Reference

### Tool Schemas

All tools follow consistent JSON schema patterns:

```typescript
// calculate-date
{
  base_date: string,        // ISO date format
  operation: "add" | "subtract",
  amount: number,
  unit: "days" | "weeks" | "months" | "years",
  timezone?: string         // Optional IANA timezone
}

// calculate-business-days  
{
  start_date: string,       // ISO date format
  end_date: string,         // ISO date format  
  holidays?: string[],      // Array of ISO dates
  timezone?: string         // Optional IANA timezone
}

// get-current-datetime
{
  format: "iso" | "readable" | "unix" | "rfc3339" | "json" | "custom",
  timezone?: string,        // Optional IANA timezone
  custom_format?: string    // Required when format="custom"
}
```

### Resource URIs

```
datetime://current              # Current date/time
datetime://timezone-info        # Current timezone info
datetime://supported-timezones  # All supported timezones
note://internal/{name}          # Individual notes
```

### Error Handling

All tools include comprehensive error handling:
- Invalid date formats
- Invalid timezone identifiers  
- Invalid date ranges
- Missing required parameters
- Graceful fallbacks with informative error messages

## Performance & Reliability

- **Response Time**: All operations <50ms (p95)
- **Accuracy**: 100% mathematical precision
- **Timezone Data**: 598+ timezones with automatic DST handling
- **Edge Cases**: Comprehensive leap year, month-end, and boundary handling
- **No External Dependencies**: Uses only Python standard library for reliability

## Examples

### Complex Workflow Example

```python
# 1. Get current date in specific timezone
current = await call_tool("get-current-datetime", {
    "format": "iso",
    "timezone": "America/New_York"
})

# 2. Calculate project phases
phase1_end = await call_tool("calculate-date", {
    "base_date": current.split('T')[0],
    "operation": "add", 
    "amount": 14,
    "unit": "days"
})

# 3. Calculate business days for the phase
business_days = await call_tool("calculate-business-days", {
    "start_date": current.split('T')[0],
    "end_date": phase1_end,
    "holidays": ["2024-12-25", "2025-01-01"]
})

# 4. Store project timeline as note
await call_tool("add-note", {
    "name": "project-timeline",
    "content": f"Phase 1: {business_days['business_days']} business days"
})
```

### LLM Guidance Usage

```bash
# Get comprehensive tool usage guide
uv run mcp prompts get datetime-calculation-guide --arguments '{"scenario": "deadlines"}'

# Learn business day calculation rules
uv run mcp prompts get business-day-rules --arguments '{"region": "standard"}'

# Understand timezone best practices
uv run mcp prompts get timezone-best-practices --arguments '{"operation_type": "calculation"}'
```

## Contributing

1. Fork the repository
2. Create a feature branch
3. Add tests for new functionality
4. Ensure all tests pass: `./run_tests.sh`
5. Submit a pull request

## License

This project is licensed under the MIT License - see the LICENSE file for details.

## Changelog

See [CHANGELOG.md](CHANGELOG.md) for version history and release notes.
