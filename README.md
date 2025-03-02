# DateTime MCP Server

A MCP (Model Completions Protocol) server that provides datetime functionality along with simple note management.

## Overview

This server implements the MCP protocol and offers various datetime-related tools and resources, including:

- Current date and time in different formats
- Date formatting utilities
- Event scheduling prompts
- Simple note management functionality

The server can be used by any MCP client to access date and time information and manage simple notes.

## Features

### Resources

The server provides the following resources:

- `datetime://current` - The current date and time
- `datetime://today` - Today's date in ISO format
- `datetime://time` - The current time in 24-hour format
- `note://internal/{name}` - User-created notes

### Tools

The server provides the following tools:

- `add-note` - Add a new note with a name and content
- `get-current-time` - Get the current time in various formats (ISO, readable, Unix timestamp, RFC3339)
- `format-date` - Format a date string according to a specified format pattern

### Prompts

The server provides the following prompts:

- `summarize-notes` - Creates a summary of all notes
- `schedule-event` - Helps schedule an event at a specific time

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
npx @modelcontextprotocol/inspector uv --directory /Users/malcolm/dev/bossjones/datetime-mcp-server run datetime-mcp-server
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
