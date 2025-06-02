---
id: mcp-reference
title: MCP Reference
sidebar_label: MCP Reference
---

# MCP Reference

The **MCP** (Modular Computing Platform) provides decorators and an event-driven task execution model.

## Tool Decorators

- `@mcp.tool()` - defines a task
- `mcp.trigger(task_name, params)` - invoke tasks programmatically

## Event Loop

```mermaid
sequenceDiagram
    participant API
    participant MCP
    participant Worker
    API->>MCP: trigger('crawl_and_index')
    MCP->>Worker: schedule task
    Worker-->>MCP: result
    MCP-->>API: return result
```
