# DateTime MCP Server

[![CI/CD Pipeline](https://github.com/seonghobae/datetime-mcp-server/actions/workflows/ci.yml/badge.svg?branch=bugfix%2Fserver-stability-improvements)](https://github.com/seonghobae/datetime-mcp-server/actions/workflows/ci.yml)
[![Security Scan](https://github.com/seonghobae/datetime-mcp-server/actions/workflows/security.yml/badge.svg)](https://github.com/seonghobae/datetime-mcp-server/actions/workflows/security.yml)
[![Release](https://github.com/seonghobae/datetime-mcp-server/actions/workflows/release.yml/badge.svg)](https://github.com/seonghobae/datetime-mcp-server/actions/workflows/release.yml)

A MCP (Model Context Protocol) server that provides datetime functionality along with simple note management.

## Overview

This server implements the MCP protocol and offers various datetime-related tools and resources, including:

- Current date and time in different formats
- Date formatting utilities
- Advanced date calculations for LLM applications
- Event scheduling prompts
- Simple note management functionality

The server can be used by any MCP client to access date and time information and manage simple notes. **Enhanced with RAG-optimized temporal context tools** to help LLMs understand relative time expressions like "yesterday", "last month", or "3 days ago".

## Features

### Resources

The server provides the following resources:

- `datetime://current` - The current date and time
- `datetime://today` - Today's date in ISO format
- `datetime://time` - The current time in 24-hour format
- `datetime://timezone-info` - Current timezone information including UTC offset and DST status
- `datetime://supported-timezones` - List of all supported timezone identifiers grouped by region
- `note://internal/{name}` - User-created notes

### Tools

The server provides the following tools:

#### Core Tools (Original)
- `add-note` - Add a new note with a name and content
- `get-current-time` - Get the current time in various formats (ISO, readable, Unix timestamp, RFC3339)
- `format-date` - Format a date string according to a specified format pattern

#### Enhanced Tools
- `get-note` - Retrieve a note by name
- `list-notes` - List all available notes  
- `delete-note` - Remove a note by name
- `get-current-datetime` - Get current date/time with enhanced timezone and format support
- `calculate-date` - Add or subtract time periods from a given date
- `calculate-date-range` - Calculate start and end dates for periods like "last 3 months"
- `calculate-business-days` - Calculate business days between dates, excluding weekends and holidays

### Prompts

The server provides the following prompts:

- `summarize-notes` - Creates a summary of all notes
- `schedule-event` - Helps schedule an event at a specific time
- `datetime-calculation-guide` - Provides examples of when and how to use date calculation tools
- `business-day-rules` - Explains business day calculation rules and holiday handling
- `timezone-best-practices` - Guidelines for timezone-aware date operations

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

### Connecting to the Server

You can connect to the server using any MCP client. For example, using the MCP CLI:

```bash
uv run mcp connect datetime-mcp-server
```

## Examples

### Using the Server with MCP CLI

List available resources:
```bash
uv run mcp resources list
```

Read a datetime resource:
```bash
uv run mcp resources read datetime://current
```

Add a note:
```bash
uv run mcp tools call add-note --arguments '{"name": "meeting", "content": "Team meeting at 3pm"}'
```

Get the current time in ISO format:
```bash
uv run mcp tools call get-current-time --arguments '{"format": "iso"}'
```

Format a date:
```bash
uv run mcp tools call format-date --arguments '{"date": "2023-10-15", "format": "%B %d, %Y"}'
```

## Advanced Usage: RAG Temporal Context

This server provides specialized tools for LLM applications that need to understand relative time expressions in RAG (Retrieval-Augmented Generation) scenarios.

### Problem Solved

When users ask questions like:
- "What happened yesterday?"
- "Show me documents from last month"
- "Find meetings scheduled for next week"

LLMs need to convert these relative expressions into exact dates for precise document filtering and retrieval.

### RAG Workflow Example

```bash
# 1. Get current reference point
current=$(uv run mcp tools call get-current-datetime --arguments '{"format": "iso"}')

# 2. Calculate "last month" range
uv run mcp tools call calculate-date-range --arguments '{
  "base_date": "'$current'",
  "direction": "last", 
  "amount": 1, 
  "unit": "months"
}'

# 3. Use the range for document filtering
# Output: {"start": "2024-06-11", "end": "2024-07-11"}
```

### Advanced Date Calculations

#### Business Days
```bash
# Calculate business days excluding holidays
uv run mcp tools call calculate-business-days --arguments '{
  "start_date": "2024-12-20",
  "end_date": "2024-12-31", 
  "holidays": ["2024-12-25", "2024-12-26"]
}'
```

#### Timezone-Aware Operations
```bash
# Get current time in different timezone
uv run mcp tools call get-current-datetime --arguments '{
  "format": "json", 
  "timezone": "Asia/Tokyo"
}'
```

#### Flexible Date Arithmetic
```bash
# Add 3 months to a specific date
uv run mcp tools call calculate-date --arguments '{
  "base_date": "2024-07-15",
  "operation": "add",
  "amount": 3,
  "unit": "months"
}'
```

## Development

### Installing Development Dependencies

```bash
# Install all dependencies including development dependencies
uv sync --dev
```

### Running Tests

To run the tests:

```bash
uv run pytest tests/
```

#### Unit Tests

Unit tests verify that individual server functions work correctly:

```bash
uv run pytest tests/acceptance/test_server.py
```

#### Integration Tests

Integration tests verify that the server implements the MCP protocol correctly:

```bash
uv run pytest tests/acceptance/test_server_integration.py
```

### Dependency Management

```bash
# Add a production dependency
uv add package_name

# Add a development dependency
uv add --dev package_name

# Sync dependencies from lockfile
uv sync --frozen

# List outdated packages
uv outdated
```

## Makefile Tasks

The project includes several Makefile tasks to streamline development:

```bash
# Sync all dependencies with frozen lockfile
make uv-sync-all

# Sync only development dependencies
make uv-sync-dev

# Run tests
make test
```

## Building and Publishing

To prepare the package for distribution:

1. Sync dependencies and update lockfile:
```bash
uv sync
```

2. Build package distributions:
```bash
uv build
```

This will create source and wheel distributions in the `dist/` directory.

3. Publish to PyPI:
```bash
uv publish
```

Note: You'll need to set PyPI credentials via environment variables or command flags:
- Token: `--token` or `UV_PUBLISH_TOKEN`
- Or username/password: `--username`/`UV_PUBLISH_USERNAME` and `--password`/`UV_PUBLISH_PASSWORD`

## Debugging

Since MCP servers run over stdio, debugging can be challenging. For the best debugging
experience, we strongly recommend using the [MCP Inspector](https://github.com/modelcontextprotocol/inspector).

You can launch the MCP Inspector via [`npm`](https://docs.npmjs.com/downloading-and-installing-node-js-and-npm) with this command:

```bash
npx @modelcontextprotocol/inspector uv --directory /path/to/datetime-mcp-server run datetime-mcp-server
```

Upon launching, the Inspector will display a URL that you can access in your browser to begin debugging.

## License

MIT

## Contributing

1. Fork the repository
2. Create a feature branch
3. Make your changes
4. Run the tests with `uv run pytest`
5. Submit a pull request
