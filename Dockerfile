FROM python:3.12-slim

WORKDIR /app

# Install uv
RUN pip install uv

# Copy project files
COPY pyproject.toml uv.lock ./

# Install dependencies
RUN pip install --system -e "[api,test]"

# Copy source code
COPY src/ ./src/
COPY tests/ ./tests/

# Install the MCP crawl4ai setup
RUN crawl4ai-setup

# Expose port 8080 for the API wrapper
EXPOSE 8080

# Command to run the API wrapper
CMD ["python", "-m", "uvicorn", "src.api_wrapper:app", "--host", "0.0.0.0", "--port", "8080"]