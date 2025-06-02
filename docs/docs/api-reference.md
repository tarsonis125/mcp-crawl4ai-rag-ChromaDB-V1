# API Reference

Comprehensive reference of HTTP endpoints.

## Status

- **GET** `/api/mcp/status`
  - Returns health and version

```json
{ "status": "ok", "version": "1.0.0" }
```

## RAG Endpoint

- **POST** `/api/mcp/query`
  - Body: `{ "query": "Your question" }`
  - Response: `{ "answer": "..." }`

```bash
curl -X POST http://localhost:8080/api/mcp/query \
     -H 'Content-Type: application/json' \
     -d '{"query":"What is MCP?"}'
```

## Task Management

- **POST** `/api/mcp/task` - Create a new task
- **GET** `/api/mcp/task/{id}` - Query task status

Refer to [MCP Reference](mcp-reference) for payload schemas.
