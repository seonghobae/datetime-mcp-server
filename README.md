# DateTime MCP Server for RAG Temporal Context

A specialized MCP (Model Context Protocol) server that provides **temporal context awareness** for LLMs, enabling them to understand relative time expressions like "yesterday", "today", and "tomorrow" in RAG (Retrieval-Augmented Generation) applications.

## Overview

**Problem**: LLMs don't inherently know what "today" means, making queries like *"What happened yesterday?"* or *"Show me documents from last month"* impossible to process accurately in RAG systems.

**Solution**: This MCP server provides LLMs with precise mathematical date operations to convert relative time expressions into exact dates for accurate document retrieval and temporal reasoning.

### Core Value Proposition

🎯 **For RAG Applications**: Transform user queries with relative time expressions into precise date-filtered searches  
🕒 **Temporal Context**: Give LLMs a reliable "today" reference point and calculation tools  
🔧 **Mathematical Precision**: No natural language parsing - only exact date arithmetic  
⚡ **Performance Optimized**: <50ms response time for real-time chat applications  

### Key Use Cases

- **Chat Applications**: *"What did we discuss yesterday?"* → Filter documents by exact date  
- **Document Search**: *"Reports from last quarter"* → Calculate precise date ranges  
- **Time-based Analytics**: *"Compare this month vs last month"* → Generate exact comparison periods  
- **Scheduling & Planning**: *"Deadline in 2 weeks"* → Calculate specific target dates  

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
git clone https://github.com/seonghobae/datetime-mcp-server.git
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

#### RAG Temporal Query Processing 
```bash
# User asks: "What happened yesterday?"
# LLM workflow:

# 1. Get today's date as reference point
today=$(uv run mcp tools call get-current-datetime --arguments '{"format": "iso", "timezone": "UTC"}')
# Returns: "2024-07-15T14:30:00+00:00"

# 2. Calculate "yesterday" 
yesterday=$(uv run mcp tools call calculate-date --arguments '{"base_date": "2024-07-15", "operation": "subtract", "amount": 1, "unit": "days"}')
# Returns: "2024-07-14"

# 3. Now LLM can query RAG system with exact date filter:
# search_documents(date_filter="2024-07-14")
```

#### RAG Date Range Queries
```bash
# User asks: "Show me reports from last quarter"
# LLM workflow:

# 1. Get current date
current=$(uv run mcp tools call get-current-datetime --arguments '{"format": "iso"}')

# 2. Calculate last quarter range  
quarter_range=$(uv run mcp tools call calculate-date-range --arguments '{"base_date": "2024-07-15", "direction": "last", "amount": 3, "unit": "months"}')
# Returns: {"start": "2024-04-15", "end": "2024-07-15"}

# 3. RAG system searches with date range:
# search_documents(start_date="2024-04-15", end_date="2024-07-15", content_type="reports")
```

#### Business Day Calculations for RAG
```bash
# User asks: "What happened in the last 10 business days?"
# LLM workflow:

# 1. Get today's date
today=$(uv run mcp tools call get-current-datetime --arguments '{"format": "iso"}')

# 2. Calculate 10 business days ago  
start_date=$(uv run mcp tools call calculate-date --arguments '{"base_date": "2024-07-15", "operation": "subtract", "amount": 14, "unit": "days"}')
# Start with 14 calendar days to ensure we get 10 business days

# 3. Verify exact business day count
business_days=$(uv run mcp tools call calculate-business-days --arguments '{"start_date": "2024-07-01", "end_date": "2024-07-15", "holidays": ["2024-07-04"]}')
# Returns: {"business_days": 10}

# 4. RAG search with business-day-aware filtering
# search_documents(date_range="business_days", start="2024-07-01", end="2024-07-15")
```

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

### Complex RAG Temporal Query Workflow

```python
# Scenario: User asks "Compare our sales performance this month vs last month, 
# excluding weekends and holidays"

# 1. Establish temporal context - get current date
current = await call_tool("get-current-datetime", {
    "format": "iso",
    "timezone": "America/New_York"
})
# Returns: "2024-07-15T14:30:00-04:00"

# 2. Calculate "this month" range  
this_month_range = await call_tool("calculate-date-range", {
    "base_date": current.split('T')[0],
    "direction": "next",
    "amount": 0,
    "unit": "months"  # Current month
})
# Adjust to get current month start to today
this_month_start = current.split('T')[0].replace('-15', '-01')  # 2024-07-01

# 3. Calculate "last month" range
last_month_range = await call_tool("calculate-date-range", {
    "base_date": this_month_start,
    "direction": "last", 
    "amount": 1,
    "unit": "months"
})
# Returns: {"start": "2024-06-01", "end": "2024-06-30"}

# 4. Calculate business days for this month (excluding weekends/holidays)
this_month_business_days = await call_tool("calculate-business-days", {
    "start_date": this_month_start,
    "end_date": current.split('T')[0],
    "holidays": ["2024-07-04"],  # Independence Day
    "timezone": "America/New_York"
})

# 5. Calculate business days for last month  
last_month_business_days = await call_tool("calculate-business-days", {
    "start_date": last_month_range["start"],
    "end_date": last_month_range["end"], 
    "holidays": [],  # No holidays in June 2024
    "timezone": "America/New_York"
})

# 6. Store comparison metadata as note
comparison_metadata = {
    "this_month": {
        "period": f"{this_month_start} to {current.split('T')[0]}",
        "business_days": this_month_business_days["business_days"]
    },
    "last_month": {
        "period": f"{last_month_range['start']} to {last_month_range['end']}",
        "business_days": last_month_business_days["business_days"]
    }
}

await call_tool("add-note", {
    "name": "monthly-comparison-context",
    "content": f"Sales comparison context: {json.dumps(comparison_metadata, indent=2)}"
})

# 7. Now RAG system can search with precise temporal filters:
# this_month_sales = search_sales_documents(
#     start_date=this_month_start,
#     end_date=current.split('T')[0], 
#     business_days_only=True,
#     holidays=["2024-07-04"]
# )
# 
# last_month_sales = search_sales_documents(
#     start_date=last_month_range["start"],
#     end_date=last_month_range["end"],
#     business_days_only=True
# )
# 
# # Normalize by business days for fair comparison
# this_month_daily_avg = this_month_sales.total / this_month_business_days["business_days"]
# last_month_daily_avg = last_month_sales.total / last_month_business_days["business_days"]
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
