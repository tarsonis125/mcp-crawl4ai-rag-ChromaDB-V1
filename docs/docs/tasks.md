---
id: tasks
title: Archon Tasks
sidebar_label: Tasks
---

# Archon Tasks

Tasks are defined via `@mcp.tool()` decorators.

## Example

```python
@mcp.tool(name="summarize_page")
def summarize(url: str) -> str:
    """Fetch and summarize page"""
    # ...
```

## Scheduling

Use MCP CLI or REST to schedule periodic tasks.
```
mcp schedule summarize_page --cron "0 * * * *"
```
