---
id: server
title: Server Architecture
sidebar_label: Server
---

# Server Architecture

The backend is built with **FastAPI** and integrated with the **MCP** task framework.

## Directory Structure

```
src/
├── main.py            # entrypoint
├── crawl4ai_mcp.py    # MCP tool definitions
├── api/               # REST endpoints
└── services/          # business logic
```

## Key Components

- **FastAPI App**: Defines REST & WebSocket endpoints
- **MCP Layer**: Decorators (@mcp.tool) for async task orchestration

```python
from mcp import MCP
mcp = MCP()

@mcp.tool()
def crawl_and_index(params: dict) -> dict:
    """Crawl pages and index embeddings"""
    # ... implementation
```
