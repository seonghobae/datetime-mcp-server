# Makefile for datetime-mcp-server
# Alternative to justfile for environments without 'just' command

.PHONY: help install run test test-coverage lint-ci format-check typecheck-ci pre-commit-validate
.PHONY: lint typecheck format fix clean build check check-ci setup-hooks install-pre-commit-hook

# Default target
help:
	@echo "Available commands:"
	@echo "  install               - Install all dependencies including development dependencies"
	@echo "  run                   - Run the development server"
	@echo "  test                  - Run tests with pytest"
	@echo "  test-coverage         - Run tests with coverage"
	@echo ""
	@echo "GitHub Actions Equivalent Commands:"
	@echo "  lint-ci               - Run ruff linter (GitHub Actions equivalent)"
	@echo "  format-check          - Check code formatting (GitHub Actions equivalent)"
	@echo "  typecheck-ci          - Run type checking with pyright (GitHub Actions equivalent)"
	@echo "  pre-commit-validate   - Complete pre-commit validation (runs same as GitHub Actions)"
	@echo "  check-ci              - Run GitHub Actions equivalent checks locally"
	@echo ""
	@echo "Original Commands:"
	@echo "  lint                  - Run linting checks (original)"
	@echo "  typecheck             - Run type checking (original with mypy)"
	@echo "  format                - Format code using ruff (applies formatting)"
	@echo "  fix                   - Auto-fix formatting and linting issues"
	@echo "  setup-hooks           - Install pre-commit hooks"
	@echo "  clean                 - Clean up cache directories"

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
pre-commit-validate: lint-ci format-check typecheck-ci
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
	rm -rf .pytest_cache .mypy_cache .ruff_cache .coverage htmlcov dist build *.egg-info

# Run all quality checks (format, lint, typecheck, test)
check: format lint typecheck test

# Run GitHub Actions equivalent checks locally
check-ci: pre-commit-validate test

# Install pre-commit hooks
setup-hooks: install-pre-commit-hook
	@echo "✅ Pre-commit hooks installed!"

# Install git pre-commit hook script
install-pre-commit-hook:
	@echo "🔧 Installing pre-commit hook..."
	@echo '#!/bin/bash' > .git/hooks/pre-commit
	@echo '# Auto-generated pre-commit hook for datetime-mcp-server' >> .git/hooks/pre-commit
	@echo 'set -e' >> .git/hooks/pre-commit
	@echo 'echo "🚀 Running pre-commit validation..."' >> .git/hooks/pre-commit
	@echo 'make pre-commit-validate' >> .git/hooks/pre-commit
	@echo 'echo "✅ Pre-commit validation passed!"' >> .git/hooks/pre-commit
	@chmod +x .git/hooks/pre-commit 