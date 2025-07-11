# Multi-stage build for optimized production image using UV
FROM ghcr.io/astral-sh/uv:python3.12-bookworm-slim AS builder

# Set UV environment variables for better performance
ENV UV_COMPILE_BYTECODE=1
ENV UV_LINK_MODE=copy

# Set working directory
WORKDIR /app

# Copy all necessary files for building
COPY pyproject.toml uv.lock ./
COPY src/ ./src/
COPY README.md ./

# Install all dependencies (including dev for building)
RUN uv sync --frozen

# Create clean production environment in separate directory
WORKDIR /prod
COPY pyproject.toml uv.lock ./
COPY src/ ./src/
COPY README.md ./

# Install only production dependencies
RUN uv sync --frozen --no-dev

# Production stage
FROM python:3.12-slim AS production

# Create non-root user
RUN groupadd -r mcpuser && useradd -r -g mcpuser mcpuser

# Set working directory
WORKDIR /app

# Copy production virtual environment from builder stage
COPY --from=builder /prod/.venv /app/.venv

# Copy only essential files
COPY src/ ./src/
COPY health_check.py ./

# Change ownership to non-root user
RUN chown -R mcpuser:mcpuser /app

# Switch to non-root user
USER mcpuser

# Set environment variables
ENV PATH="/app/.venv/bin:$PATH"
ENV PYTHONPATH="/app/src:$PYTHONPATH"
ENV PYTHONUNBUFFERED=1

# Expose port (for future HTTP support)
EXPOSE 8000

# Add health check
HEALTHCHECK --interval=30s --timeout=10s --start-period=5s --retries=3 \
    CMD python /app/health_check.py

# Default command (can be overridden with environment variables)
CMD ["python", "-m", "datetime_mcp_server.main"] 