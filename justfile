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

# === GitHub Actions Equivalent Commands ===

# Run ruff linter (GitHub Actions equivalent)
lint-ci:
    @echo "🔍 Running ruff linter (GitHub Actions equivalent)..."
    uv run ruff check .

# Check code formatting (GitHub Actions equivalent)
format-check:
    @echo "📝 Checking code formatting (GitHub Actions equivalent)..."
    uv run ruff format --check .

# Run type checking with pyright (GitHub Actions equivalent)
typecheck-ci:
    @echo "📦 Installing pyright for type checking..."
    uv add --dev pyright
    @echo "🔍 Running type checking (GitHub Actions equivalent)..."
    uv run pyright src/ tests/

# Complete pre-commit validation (runs same as GitHub Actions)
pre-commit-validate:
    @echo "🚀 Running complete pre-commit validation (GitHub Actions equivalent)..."
    @just lint-ci
    @just format-check
    @just typecheck-ci
    @echo "✅ All pre-commit checks passed!"

# === Original Commands (kept for compatibility) ===

# Run linting checks (original)
lint:
    uv run ruff check src/ tests/

# Run type checking (original with mypy)
typecheck:
    uv run mypy src/ tests/

# Format code using ruff (applies formatting)
format:
    uv run ruff format src/ tests/

# Auto-fix formatting and linting issues
fix:
    @echo "🔧 Auto-fixing code formatting..."
    uv run ruff format .
    @echo "🔧 Auto-fixing linting issues..."
    uv run ruff check . --fix
    @echo "✅ Auto-fix completed!"

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

# Run GitHub Actions equivalent checks locally
check-ci: pre-commit-validate test

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
    @echo "🔧 Setting up pre-commit hooks..."
    @just install-pre-commit-hook
    @echo "✅ Pre-commit hooks installed!"

# Install git pre-commit hook script
install-pre-commit-hook:
    @echo "#!/bin/bash" > .git/hooks/pre-commit
    @echo "# Auto-generated pre-commit hook for datetime-mcp-server" >> .git/hooks/pre-commit
    @echo "set -e" >> .git/hooks/pre-commit
    @echo "echo '🚀 Running pre-commit validation...'" >> .git/hooks/pre-commit
    @echo "just pre-commit-validate" >> .git/hooks/pre-commit
    @echo "echo '✅ Pre-commit validation passed!'" >> .git/hooks/pre-commit
    @chmod +x .git/hooks/pre-commit

# Update all dependencies
update-deps:
    uv pip compile --upgrade pyproject.toml -o uv.lock

inspect:
    npx @modelcontextprotocol/inspector uv --directory /Users/malcolm/dev/bossjones/datetime-mcp-server run datetime-mcp-server
