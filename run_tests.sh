#!/bin/bash
# Script to run acceptance tests for the datetime-mcp-server

# Set up error handling
set -e

# Print script usage
echo "Running acceptance tests for datetime-mcp-server..."

# Make sure the virtual environment is activated
if [[ -z "${VIRTUAL_ENV}" ]]; then
  echo "Warning: Virtual environment not detected. Please activate your virtual environment first."
  echo "Example: source .venv/bin/activate"
  exit 1
fi

# Install test dependencies if needed
echo "Checking for test dependencies..."
if ! python -c "import pytest" &> /dev/null; then
  echo "Installing test dependencies..."
  uv sync --dev
fi

# Run the unit tests
echo "Running unit tests..."
uv run pytest tests/acceptance/test_server.py -v

# Run the integration tests
echo "Running integration tests..."
uv run pytest tests/acceptance/test_server_integration.py -v

echo "All tests completed!"
