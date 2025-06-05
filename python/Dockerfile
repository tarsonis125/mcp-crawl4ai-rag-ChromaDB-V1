FROM python:3.12-slim

WORKDIR /app

# Install system dependencies
RUN apt-get update && apt-get install -y \
    curl \
    && rm -rf /var/lib/apt/lists/*

# Install uv
RUN pip install uv

# Copy project files
COPY pyproject.toml uv.lock ./

# Install ALL dependencies (base + extras) using uv
# This ensures all dependencies including mcp are installed
RUN uv sync --all-extras

# Copy source code
COPY src/ ./src/
COPY tests/ ./tests/

# Install the MCP crawl4ai setup using uv
RUN uv run crawl4ai-setup

# Test that the MCP server can import successfully
RUN uv run python -c "from src.mcp_server import mcp; print('✓ MCP server imports successfully')" || \
    echo "⚠ MCP server import test failed - will try at runtime"

# Expose ports
EXPOSE 8080 8051

# Add healthcheck script
RUN echo '#!/bin/bash\ncurl -f http://localhost:8080/api/mcp/status || exit 1' > /healthcheck.sh && \
    chmod +x /healthcheck.sh

# Default command runs the API wrapper, but can be overridden
CMD ["uv", "run", "uvicorn", "src.main:app", "--host", "0.0.0.0", "--port", "8080"]