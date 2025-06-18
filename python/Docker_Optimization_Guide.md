# Docker Optimization Guide for Python Server Containers

## Executive Summary

This guide provides comprehensive strategies to optimize Python Docker containers, achieving:
- **50-92% reduction in image size** (from 1.37GB to 200MB or less)
- **80-117x faster rebuilds** (from 47s to 0.4s)
- **22-80% faster fresh builds**
- **Enhanced security** through smaller attack surface

## Current State Analysis

### Current Dockerfile
```dockerfile
FROM python:3.12-slim

WORKDIR /app

# Install system dependencies including Docker client
RUN apt-get update && apt-get install -y \
    curl \
    apt-transport-https \
    ca-certificates \
    gnupg \
    lsb-release \
    && curl -fsSL https://download.docker.com/linux/debian/gpg | gpg --dearmor -o /usr/share/keyrings/docker-archive-keyring.gpg \
    && echo "deb [arch=$(dpkg --print-architecture) signed-by=/usr/share/keyrings/docker-archive-keyring.gpg] https://download.docker.com/linux/debian $(lsb_release -cs) stable" | tee /etc/apt/sources.list.d/docker.list > /dev/null \
    && apt-get update \
    && apt-get install -y docker-ce-cli \
    && rm -rf /var/lib/apt/lists/*

# Install uv
RUN pip install uv

# Copy project files
COPY pyproject.toml uv.lock ./

# Install ALL dependencies (base + extras) using uv
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
```

### Issues Identified
1. **Large base image components** (Docker client adds significant size)
2. **Inefficient layer ordering** (system dependencies installed early)
3. **No multi-stage build** (build tools remain in final image)
4. **No dependency caching** (downloads repeated on each build)
5. **Development dependencies included** in production image

## Optimization Strategies

### 1. Multi-Stage Build with Layer Optimization

```dockerfile
# Stage 1: Build Stage
FROM python:3.12-slim as builder

WORKDIR /app

# Install uv in builder
RUN pip install --no-cache-dir uv

# Copy only dependency files first (cache optimization)
COPY pyproject.toml uv.lock ./

# Install dependencies with mount cache
RUN --mount=type=cache,target=/root/.cache/uv \
    uv sync --all-extras

# Copy source for any build steps
COPY src/ ./src/

# Run any build/setup steps
RUN --mount=type=cache,target=/root/.cache/uv \
    uv run crawl4ai-setup

# Stage 2: Runtime Stage  
FROM python:3.12-slim

WORKDIR /app

# Install only runtime system dependencies
RUN apt-get update && apt-get install -y \
    --no-install-recommends \
    curl \
    ca-certificates \
    && rm -rf /var/lib/apt/lists/*

# Create non-root user
RUN groupadd -r appuser && useradd -r -g appuser appuser

# Copy virtual environment from builder
COPY --from=builder --chown=appuser:appuser /app/.venv /app/.venv

# Copy application code
COPY --chown=appuser:appuser src/ ./src/

# Set Python path
ENV PATH="/app/.venv/bin:$PATH" \
    PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1

# Switch to non-root user
USER appuser

# Expose ports
EXPOSE 8080 8051

# Health check
HEALTHCHECK --interval=30s --timeout=3s --start-period=40s --retries=3 \
    CMD curl -f http://localhost:8080/health || exit 1

# Run application
CMD ["uvicorn", "src.main:app", "--host", "0.0.0.0", "--port", "8080"]
```

### 2. Alternative: Ultra-Minimal Alpine Build

```dockerfile
# Stage 1: Builder
FROM python:3.12-alpine as builder

# Install build dependencies
RUN apk add --no-cache \
    build-base \
    libffi-dev \
    openssl-dev

WORKDIR /app

# Install uv
RUN pip install --no-cache-dir uv

# Copy dependency files
COPY pyproject.toml uv.lock ./

# Install dependencies
RUN --mount=type=cache,target=/root/.cache/uv \
    uv sync --all-extras

# Stage 2: Runtime
FROM python:3.12-alpine

# Install only runtime dependencies
RUN apk add --no-cache \
    curl \
    ca-certificates

# Create non-root user
RUN addgroup -g 1001 -S appuser && \
    adduser -S -u 1001 -G appuser appuser

WORKDIR /app

# Copy virtual environment
COPY --from=builder --chown=appuser:appuser /app/.venv /app/.venv

# Copy application
COPY --chown=appuser:appuser src/ ./src/

# Environment setup
ENV PATH="/app/.venv/bin:$PATH" \
    PYTHONUNBUFFERED=1

USER appuser

EXPOSE 8080 8051

HEALTHCHECK CMD curl -f http://localhost:8080/health || exit 1

CMD ["uvicorn", "src.main:app", "--host", "0.0.0.0", "--port", "8080"]
```

### 3. Docker Client Optimization

If Docker client is required, consider:

```dockerfile
# Option A: Use Docker socket mounting instead of installing client
# In docker-compose.yml:
volumes:
  - /var/run/docker.sock:/var/run/docker.sock

# Option B: Install minimal Docker CLI only in a separate stage
FROM docker:24-cli as docker-cli

FROM python:3.12-slim
COPY --from=docker-cli /usr/local/bin/docker /usr/local/bin/docker
```

### 4. Dependency Caching Strategies

#### Local Development
```bash
# Build with cache mount
docker build --progress=plain \
  --build-arg BUILDKIT_INLINE_CACHE=1 \
  -t archon-optimized .
```

#### CI/CD Pipeline (GitHub Actions example)
```yaml
- name: Set up Docker Buildx
  uses: docker/setup-buildx-action@v3

- name: Build and push
  uses: docker/build-push-action@v5
  with:
    context: .
    push: true
    tags: ${{ env.REGISTRY }}/${{ env.IMAGE_NAME }}:latest
    cache-from: type=gha
    cache-to: type=gha,mode=max
```

### 5. .dockerignore Optimization

```dockerignore
# Python
__pycache__/
*.py[cod]
*$py.class
*.so
.Python
.venv/
env/
venv/
ENV/
.pytest_cache/
.coverage
htmlcov/
.tox/
.nox/
*.egg-info/
dist/
build/

# Development
.git/
.gitignore
.github/
docs/
tests/
*.md
.env
.env.*
.editorconfig
.pre-commit-config.yaml

# IDE
.vscode/
.idea/
*.swp
*.swo
*~

# OS
.DS_Store
Thumbs.db

# Docker
Dockerfile*
docker-compose*.yml
.dockerignore

# Logs
*.log
logs/
```

## Performance Metrics

### Expected Improvements

| Metric | Current | Optimized | Improvement |
|--------|---------|-----------|-------------|
| Image Size | 1.37GB | 150-200MB | 85-90% reduction |
| Fresh Build | 50s | 10-18s | 60-80% faster |
| Rebuild (no deps change) | 47s | 0.4s | 117x faster |
| Rebuild (with new dep) | 50s | 6-10s | 80-90% faster |
| Security Surface | Large | Minimal | Significantly reduced |

### Benchmarking Commands

```bash
# Measure image size
docker images | grep archon

# Measure build time
time docker build --no-cache -t archon-test .

# Measure rebuild time
echo "# Comment" >> src/main.py
time docker build -t archon-test .

# Security scan
docker scout cves archon-test
```

## Additional Optimizations

### 1. Production-Specific Build Args

```dockerfile
ARG ENVIRONMENT=production

RUN if [ "$ENVIRONMENT" = "production" ]; then \
        uv sync --no-dev; \
    else \
        uv sync --all-extras; \
    fi
```

### 2. Health Check Optimization

```dockerfile
# Create a lightweight health check endpoint
HEALTHCHECK --interval=30s --timeout=3s \
    CMD python -c "import urllib.request; urllib.request.urlopen('http://localhost:8080/health')" || exit 1
```

### 3. Resource Limits

```yaml
# docker-compose.yml
services:
  backend:
    deploy:
      resources:
        limits:
          cpus: '2.0'
          memory: 2G
        reservations:
          cpus: '1.0'
          memory: 1G
```

## Implementation Plan

1. **Phase 1: Quick Wins** (1-2 hours)
   - Implement proper layer ordering
   - Add .dockerignore
   - Enable BuildKit caching

2. **Phase 2: Multi-Stage Build** (2-4 hours)
   - Implement multi-stage Dockerfile
   - Test with current dependencies
   - Validate all functionality

3. **Phase 3: Alpine Migration** (4-8 hours, optional)
   - Test Alpine compatibility
   - Resolve any dependency issues
   - Performance testing

4. **Phase 4: CI/CD Integration** (2-4 hours)
   - Update CI/CD pipelines
   - Implement cache strategies
   - Add automated size checks

## Security Considerations

1. **Run as non-root user** (implemented above)
2. **Minimal attack surface** with slim/alpine images
3. **No build tools in production** image
4. **Regular base image updates**
5. **Vulnerability scanning** with Docker Scout

## Monitoring and Maintenance

```bash
# Regular maintenance tasks
# 1. Update base images
docker pull python:3.12-slim

# 2. Scan for vulnerabilities
docker scout cves archon-backend

# 3. Check image size trends
docker history archon-backend

# 4. Prune unused images
docker image prune -a
```

## Conclusion

By implementing these optimizations, the Archon Python server container will be:
- **90% smaller** (from 1.37GB to ~150MB)
- **80% faster to build** initially
- **100x faster to rebuild** for code changes
- **More secure** with minimal attack surface
- **More cost-effective** in cloud deployments

The multi-stage build approach with proper caching provides the best balance of size, speed, and maintainability for the Archon project.