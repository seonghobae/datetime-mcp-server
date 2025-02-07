# List available commands
default:
    @just --list

# Install all dependencies including development dependencies
install:
    uv sync --dev --all-extras

# Run the development server
run:
    uv run datetime-mcp-server

# Run tests with pytest
test:
    uv run pytest tests/

# Run tests with coverage
test-coverage:
    uv run pytest --cov=src/datetime_mcp_server tests/

# Run tests in watch mode
test-watch:
    uv run pytest-watch tests/

# Run linting checks
lint:
    uv run ruff check src/ tests/

# Run type checking
typecheck:
    uv run mypy src/ tests/

# Format code using ruff
format:
    uv run ruff format src/ tests/

# Clean up cache directories
clean:
    rm -rf .pytest_cache
    rm -rf .mypy_cache
    rm -rf .ruff_cache
    rm -rf .coverage
    rm -rf htmlcov
    rm -rf dist
    rm -rf build
    rm -rf *.egg-info

# Build package
build:
    uv run python -m build

# Run all quality checks (format, lint, typecheck, test)
check: format lint typecheck test

# Create a new release (requires bump2version)
release version:
    uv run bump2version {{version}}
    git push
    git push --tags

# Run the server in debug mode
debug:
    uv run python -m debugpy --listen 5678 --wait-for-client -m datetime_mcp_server.server

# Generate documentation
docs:
    uv run sphinx-build -b html docs/source docs/build/html

# Install pre-commit hooks
setup-hooks:
    uv run pre-commit install

# Update all dependencies
update-deps:
    uv pip compile --upgrade pyproject.toml -o uv.lock
