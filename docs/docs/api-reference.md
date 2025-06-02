---
id: api-reference
title: API Reference
sidebar_label: API Reference
---

# API Reference

## REST Endpoints

| Method | Path                 | Description                         |
| ------ | -------------------- | ----------------------------------- |
| GET    | /docs/openapi.json   | OpenAPI schema                     |
| POST   | /api/crawl           | Trigger crawl task                 |
| GET    | /api/status/{task_id}| Check status of MCP task           |

## WebSocket API

**URL**: `ws://localhost:3838/ws`

```json
{
  "action": "start_crawl",
  "payload": { "seedUrl": "https://example.com" }
}
```
