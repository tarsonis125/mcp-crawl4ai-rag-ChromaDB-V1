---
title: API Reference
sidebar_position: 4
---

# API Reference

Archon provides a comprehensive REST API built with FastAPI for all knowledge management, document processing, and system administration operations. This reference covers all endpoints with detailed examples, request/response schemas, and integration patterns.

## 🌐 Base URL & Authentication

**Base URL**: `http://localhost:8080`

**Interactive Documentation**: 
- Swagger UI: `http://localhost:8080/docs`
- ReDoc: `http://localhost:8080/redoc`

**Authentication**: Currently API key-based through settings. Future versions will support JWT tokens.

## 📚 Knowledge Management API

### List Knowledge Items

**GET** `/api/knowledge-items`

Retrieve all knowledge items with optional filtering.

#### Query Parameters

| Parameter | Type | Required | Description |
|-----------|------|----------|-------------|
| `source_type` | string | ❌ | Filter by source type (`web`, `document`, `upload`) |
| `knowledge_type` | string | ❌ | Filter by knowledge type (`technical`, `business`, `general`) |
| `tags` | string[] | ❌ | Filter by tags (comma-separated) |
| `limit` | integer | ❌ | Maximum results (default: 50, max: 1000) |
| `offset` | integer | ❌ | Pagination offset (default: 0) |
| `search` | string | ❌ | Text search in title and content |

#### Example Request

```bash
curl -X GET "http://localhost:8080/api/knowledge-items?source_type=web&knowledge_type=technical&limit=10" \
  -H "Accept: application/json"
```

#### Example Response

```json
{
  "items": [
    {
      "id": 123,
      "url": "https://docs.python.org/3/tutorial/",
      "title": "Python Tutorial",
      "content": "Python is an easy to learn, powerful programming language...",
      "source_type": "web",
      "knowledge_type": "technical",
      "tags": ["python", "tutorial", "programming"],
      "metadata": {
        "crawl_date": "2024-01-15T10:30:00Z",
        "word_count": 1250,
        "language": "en"
      },
      "created_at": "2024-01-15T10:30:00Z",
      "updated_at": "2024-01-15T10:30:00Z"
    }
  ],
  "total": 1,
  "limit": 10,
  "offset": 0,
  "has_more": false
}
```

### Get Knowledge Item

**GET** `/api/knowledge-items/{item_id}`

Retrieve a specific knowledge item by ID.

#### Path Parameters

| Parameter | Type | Required | Description |
|-----------|------|----------|-------------|
| `item_id` | integer | ✅ | Knowledge item ID |

#### Example Request

```bash
curl -X GET "http://localhost:8080/api/knowledge-items/123" \
  -H "Accept: application/json"
```

### Delete Knowledge Source

**DELETE** `/api/knowledge-items/{source_id}`

Delete all knowledge items from a specific source.

#### Path Parameters

| Parameter | Type | Required | Description |
|-----------|------|----------|-------------|
| `source_id` | string | ✅ | Source identifier (URL or document name) |

#### Example Request

```bash
curl -X DELETE "http://localhost:8080/api/knowledge-items/https%3A%2F%2Fdocs.python.org" \
  -H "Accept: application/json"
```

#### Example Response

```json
{
  "message": "Successfully deleted 45 items from source",
  "deleted_count": 45,
  "source_id": "https://docs.python.org"
}
```

### Crawl Website

**POST** `/api/knowledge-items/crawl`

Initiate web crawling for a URL with real-time progress tracking.

#### Request Body

```json
{
  "url": "https://docs.python.org/3/tutorial/",
  "knowledge_type": "technical",
  "tags": ["python", "tutorial"],
  "options": {
    "max_pages": 50,
    "max_depth": 3,
    "follow_links": true,
    "respect_robots_txt": true,
    "delay_between_requests": 1.0,
    "include_patterns": ["*/tutorial/*"],
    "exclude_patterns": ["*/download/*", "*/bugs/*"]
  }
}
```

#### Request Schema

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `url` | string | ✅ | Target URL to crawl |
| `knowledge_type` | string | ✅ | Knowledge classification (`technical`, `business`, `general`) |
| `tags` | string[] | ❌ | Tags for categorization |
| `options.max_pages` | integer | ❌ | Maximum pages to crawl (default: 100) |
| `options.max_depth` | integer | ❌ | Maximum crawl depth (default: 2) |
| `options.follow_links` | boolean | ❌ | Follow internal links (default: true) |
| `options.respect_robots_txt` | boolean | ❌ | Respect robots.txt (default: true) |
| `options.delay_between_requests` | float | ❌ | Delay in seconds (default: 1.0) |
| `options.include_patterns` | string[] | ❌ | URL patterns to include |
| `options.exclude_patterns` | string[] | ❌ | URL patterns to exclude |

#### Example Request

```bash
curl -X POST "http://localhost:8080/api/knowledge-items/crawl" \
  -H "Content-Type: application/json" \
  -d '{
    "url": "https://docs.python.org/3/tutorial/",
    "knowledge_type": "technical",
    "tags": ["python", "tutorial"],
    "options": {
      "max_pages": 20,
      "max_depth": 2
    }
  }'
```

#### Example Response

```json
{
  "message": "Crawling started successfully",
  "progress_id": "crawl_20240115_103045_abc123",
  "websocket_url": "ws://localhost:8080/api/crawl-progress/crawl_20240115_103045_abc123",
  "estimated_pages": 15,
  "status": "started"
}
```

### WebSocket Progress Tracking

**WebSocket** `/api/crawl-progress/{progress_id}`

Real-time progress updates for crawling operations.

#### Connection Example

```javascript
const ws = new WebSocket('ws://localhost:8080/api/crawl-progress/crawl_20240115_103045_abc123');

ws.onmessage = function(event) {
  const progress = JSON.parse(event.data);
  console.log('Progress:', progress);
};
```

#### Progress Message Format

```json
{
  "progress_id": "crawl_20240115_103045_abc123",
  "status": "running",
  "current_page": 5,
  "total_pages": 15,
  "percentage": 33.3,
  "current_url": "https://docs.python.org/3/tutorial/classes.html",
  "pages_processed": 5,
  "pages_successful": 4,
  "pages_failed": 1,
  "errors": [
    {
      "url": "https://docs.python.org/3/tutorial/broken-link.html",
      "error": "404 Not Found",
      "timestamp": "2024-01-15T10:32:15Z"
    }
  ],
  "estimated_completion": "2024-01-15T10:35:00Z"
}
```

## 📄 Document Management API

### Upload Document

**POST** `/api/documents/upload`

Upload and process documents (PDF, Word, Markdown, Text).

#### Request (Multipart Form)

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `file` | file | ✅ | Document file to upload |
| `knowledge_type` | string | ✅ | Knowledge classification |
| `tags` | string | ❌ | JSON array of tags |
| `title` | string | ❌ | Custom title (auto-generated if not provided) |
| `description` | string | ❌ | Document description |

#### Supported File Types

| Extension | MIME Type | Max Size | Processing Engine |
|-----------|-----------|----------|-------------------|
| `.pdf` | `application/pdf` | 50MB | PyPDF2 + pdfplumber |
| `.docx` | `application/vnd.openxmlformats-officedocument.wordprocessingml.document` | 25MB | python-docx |
| `.doc` | `application/msword` | 25MB | python-docx |
| `.md` | `text/markdown` | 10MB | Direct processing |
| `.txt` | `text/plain` | 10MB | Direct processing |

#### Example Request

```bash
curl -X POST "http://localhost:8080/api/documents/upload" \
  -F "file=@python-guide.pdf" \
  -F "knowledge_type=technical" \
  -F "tags=[\"python\", \"guide\", \"programming\"]" \
  -F "title=Python Programming Guide" \
  -F "description=Comprehensive guide to Python programming"
```

#### Example Response

```json
{
  "message": "Document uploaded and processed successfully",
  "document": {
    "id": 456,
    "filename": "python-guide.pdf",
    "title": "Python Programming Guide",
    "description": "Comprehensive guide to Python programming",
    "knowledge_type": "technical",
    "tags": ["python", "guide", "programming"],
    "source_type": "document",
    "file_size": 2048576,
    "page_count": 150,
    "word_count": 45000,
    "processing_time": 12.5,
    "chunks_created": 89,
    "created_at": "2024-01-15T10:45:00Z"
  }
}
```

### List Documents

**GET** `/api/documents`

Retrieve uploaded documents with metadata.

#### Query Parameters

| Parameter | Type | Required | Description |
|-----------|------|----------|-------------|
| `knowledge_type` | string | ❌ | Filter by knowledge type |
| `tags` | string[] | ❌ | Filter by tags |
| `limit` | integer | ❌ | Maximum results (default: 50) |
| `offset` | integer | ❌ | Pagination offset |
| `sort_by` | string | ❌ | Sort field (`created_at`, `title`, `file_size`) |
| `sort_order` | string | ❌ | Sort order (`asc`, `desc`) |

#### Example Request

```bash
curl -X GET "http://localhost:8080/api/documents?knowledge_type=technical&sort_by=created_at&sort_order=desc" \
  -H "Accept: application/json"
```

### Delete Document

**DELETE** `/api/documents/{document_id}`

Delete a document and all associated knowledge items.

#### Example Request

```bash
curl -X DELETE "http://localhost:8080/api/documents/456" \
  -H "Accept: application/json"
```

## 🔍 RAG (Retrieval-Augmented Generation) API

### Query Knowledge Base

**POST** `/api/rag/query`

Perform semantic search across the knowledge base.

#### Request Body

```json
{
  "query": "How to handle exceptions in Python?",
  "limit": 10,
  "filters": {
    "knowledge_type": ["technical"],
    "tags": ["python"],
    "source_domains": ["docs.python.org"]
  },
  "options": {
    "use_reranking": true,
    "include_metadata": true,
    "similarity_threshold": 0.7,
    "hybrid_search": true
  }
}
```

#### Request Schema

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `query` | string | ✅ | Search query text |
| `limit` | integer | ❌ | Maximum results (default: 10, max: 100) |
| `filters.knowledge_type` | string[] | ❌ | Filter by knowledge types |
| `filters.tags` | string[] | ❌ | Filter by tags |
| `filters.source_domains` | string[] | ❌ | Filter by source domains |
| `options.use_reranking` | boolean | ❌ | Enable result reranking (default: true) |
| `options.include_metadata` | boolean | ❌ | Include metadata in results (default: true) |
| `options.similarity_threshold` | float | ❌ | Minimum similarity score (0.0-1.0) |
| `options.hybrid_search` | boolean | ❌ | Combine vector and keyword search |

#### Example Request

```bash
curl -X POST "http://localhost:8080/api/rag/query" \
  -H "Content-Type: application/json" \
  -d '{
    "query": "How to handle exceptions in Python?",
    "limit": 5,
    "filters": {
      "knowledge_type": ["technical"],
      "tags": ["python"]
    },
    "options": {
      "use_reranking": true,
      "hybrid_search": true
    }
  }'
```

#### Example Response

```json
{
  "query": "How to handle exceptions in Python?",
  "results": [
    {
      "id": 789,
      "title": "Python Exception Handling",
      "content": "Python uses try-except blocks to handle exceptions. When an error occurs...",
      "url": "https://docs.python.org/3/tutorial/errors.html",
      "similarity_score": 0.92,
      "rerank_score": 0.89,
      "knowledge_type": "technical",
      "tags": ["python", "exceptions", "error-handling"],
      "metadata": {
        "source_domain": "docs.python.org",
        "section": "Tutorial",
        "word_count": 450,
        "last_updated": "2024-01-10T00:00:00Z"
      },
      "highlights": [
        "Python uses <mark>try-except</mark> blocks to <mark>handle exceptions</mark>",
        "When an <mark>error occurs</mark> during execution, Python raises an exception"
      ]
    }
  ],
  "total_results": 1,
  "processing_time": 0.245,
  "search_strategy": "hybrid_with_reranking"
}
```

### Get Available Sources

**GET** `/api/rag/sources`

Retrieve all available knowledge sources for filtering.

#### Example Response

```json
{
  "sources": {
    "domains": [
      "docs.python.org",
      "fastapi.tiangolo.com",
      "supabase.com"
    ],
    "knowledge_types": [
      "technical",
      "business",
      "general"
    ],
    "tags": [
      "python",
      "fastapi",
      "database",
      "tutorial",
      "api"
    ],
    "source_types": [
      "web",
      "document",
      "upload"
    ]
  },
  "statistics": {
    "total_items": 1250,
    "total_sources": 15,
    "last_updated": "2024-01-15T10:45:00Z"
  }
}
```

## 🔧 MCP Server Management API

### Get MCP Server Status

**GET** `/api/mcp/status`

Retrieve current MCP server status and configuration.

#### Example Response

```json
{
  "status": "running",
  "pid": 12345,
  "port": 8051,
  "uptime": 3600,
  "connections": {
    "active": 2,
    "total": 15
  },
  "capabilities": [
    "tools",
    "resources",
    "prompts"
  ],
  "tools": [
    "search_knowledge",
    "create_task",
    "update_task",
    "list_projects"
  ],
  "last_activity": "2024-01-15T10:44:30Z",
  "version": "1.0.0"
}
```

### Start MCP Server

**POST** `/api/mcp/start`

Start the MCP server if not running.

#### Request Body (Optional)

```json
{
  "port": 8051,
  "transport": "stdio",
  "options": {
    "enable_logging": true,
    "log_level": "INFO"
  }
}
```

#### Example Response

```json
{
  "message": "MCP server started successfully",
  "pid": 12345,
  "port": 8051,
  "status": "running",
  "connection_info": {
    "stdio_command": "python src/mcp_server.py",
    "sse_endpoint": "http://localhost:8080/api/mcp/sse"
  }
}
```

### Stop MCP Server

**POST** `/api/mcp/stop`

Stop the running MCP server.

#### Example Response

```json
{
  "message": "MCP server stopped successfully",
  "previous_status": "running",
  "uptime": 3600
}
```

### MCP Server Logs Stream

**WebSocket** `/api/mcp/logs/stream`

Real-time MCP server log streaming.

#### Connection Example

```javascript
const ws = new WebSocket('ws://localhost:8080/api/mcp/logs/stream');

ws.onmessage = function(event) {
  const logEntry = JSON.parse(event.data);
  console.log(`[${logEntry.timestamp}] ${logEntry.level}: ${logEntry.message}`);
};
```

#### Log Message Format

```json
{
  "timestamp": "2024-01-15T10:45:30.123Z",
  "level": "INFO",
  "logger": "mcp.server",
  "message": "Tool 'search_knowledge' called with query: 'Python exceptions'",
  "metadata": {
    "client_id": "cursor_client_001",
    "tool_name": "search_knowledge",
    "execution_time": 0.245
  }
}
```

## 📋 Task Management API

### List Projects

**GET** `/api/projects`

Retrieve all projects with optional filtering.

#### Query Parameters

| Parameter | Type | Required | Description |
|-----------|------|----------|-------------|
| `limit` | integer | ❌ | Maximum results (default: 50) |
| `offset` | integer | ❌ | Pagination offset |
| `search` | string | ❌ | Search in project titles |

#### Example Response

```json
{
  "projects": [
    {
      "id": "550e8400-e29b-41d4-a716-446655440000",
      "title": "Archon Documentation",
      "prd": {
        "overview": "Create comprehensive documentation for Archon",
        "goals": ["User-friendly docs", "API reference", "Tutorials"]
      },
      "docs": [
        {"name": "README.md", "url": "https://github.com/repo/README.md"},
        {"name": "API Spec", "url": "https://api.example.com/docs"}
      ],
      "features": [
        {"name": "Getting Started Guide", "status": "completed"},
        {"name": "API Reference", "status": "in_progress"}
      ],
      "github_repo": "https://github.com/user/archon",
      "created_at": "2024-01-15T10:00:00Z",
      "updated_at": "2024-01-15T10:45:00Z"
    }
  ],
  "total": 1,
  "limit": 50,
  "offset": 0
}
```

### Create Project

**POST** `/api/projects`

Create a new project.

#### Request Body

```json
{
  "title": "New Documentation Project",
  "prd": {
    "overview": "Project overview",
    "goals": ["Goal 1", "Goal 2"]
  },
  "docs": [
    {"name": "Requirements", "url": "https://example.com/requirements"}
  ],
  "features": [
    {"name": "Feature 1", "status": "planned"}
  ],
  "github_repo": "https://github.com/user/project"
}
```

### List Tasks

**GET** `/api/tasks`

Retrieve tasks with filtering options.

#### Query Parameters

| Parameter | Type | Required | Description |
|-----------|------|----------|-------------|
| `project_id` | string | ❌ | Filter by project ID |
| `status` | string | ❌ | Filter by status (`todo`, `doing`, `blocked`, `done`) |
| `parent_task_id` | string | ❌ | Filter by parent task |
| `limit` | integer | ❌ | Maximum results |
| `offset` | integer | ❌ | Pagination offset |

#### Example Response

```json
{
  "tasks": [
    {
      "id": "660e8400-e29b-41d4-a716-446655440001",
      "project_id": "550e8400-e29b-41d4-a716-446655440000",
      "parent_task_id": null,
      "title": "Write API documentation",
      "description": "Create comprehensive API reference documentation",
      "sources": [
        {"name": "FastAPI docs", "url": "https://fastapi.tiangolo.com"}
      ],
      "code_examples": [
        {
          "language": "python",
          "code": "@app.get('/api/example')\nasync def example():\n    return {'message': 'Hello'}"
        }
      ],
      "status": "doing",
      "created_at": "2024-01-15T10:15:00Z",
      "updated_at": "2024-01-15T10:30:00Z"
    }
  ],
  "total": 1
}
```

### Create Task

**POST** `/api/tasks`

Create a new task.

#### Request Body

```json
{
  "project_id": "550e8400-e29b-41d4-a716-446655440000",
  "parent_task_id": null,
  "title": "Implement user authentication",
  "description": "Add JWT-based authentication to the API",
  "sources": [
    {"name": "JWT Guide", "url": "https://jwt.io/introduction"}
  ],
  "code_examples": [],
  "status": "todo"
}
```

### Update Task

**PATCH** `/api/tasks/{task_id}`

Update an existing task.

#### Request Body (Partial Update)

```json
{
  "status": "done",
  "description": "Updated description with completion notes"
}
```

## ⚙️ Settings Management API

### Get Settings

**GET** `/api/settings`

Retrieve current application settings.

#### Example Response

```json
{
  "openai_api_key_configured": true,
  "rag_strategies": {
    "contextual_embeddings": false,
    "hybrid_search": true,
    "agentic_rag": false,
    "reranking": true
  },
  "crawling_defaults": {
    "max_pages": 100,
    "max_depth": 2,
    "delay_between_requests": 1.0,
    "respect_robots_txt": true
  },
  "upload_limits": {
    "max_file_size": 52428800,
    "allowed_extensions": [".pdf", ".docx", ".doc", ".md", ".txt"]
  }
}
```

### Update Settings

**POST** `/api/settings`

Update application settings.

#### Request Body

```json
{
  "openai_api_key": "sk-...",
  "rag_strategies": {
    "contextual_embeddings": true,
    "hybrid_search": true,
    "agentic_rag": true,
    "reranking": true
  },
  "crawling_defaults": {
    "max_pages": 200,
    "max_depth": 3
  }
}
```

## 🔍 System Information API

### Health Check

**GET** `/health`

System health and status check.

#### Example Response

```json
{
  "status": "healthy",
  "timestamp": "2024-01-15T10:45:00Z",
  "version": "1.0.0",
  "services": {
    "database": {
      "status": "connected",
      "response_time": 0.012,
      "connection_pool": {
        "active": 5,
        "idle": 15,
        "total": 20
      }
    },
    "openai": {
      "status": "available",
      "api_key_valid": true,
      "rate_limit_remaining": 4500
    },
    "mcp_server": {
      "status": "running",
      "port": 8051,
      "active_connections": 2
    }
  },
  "system": {
    "memory_usage": {
      "used": "512MB",
      "available": "1.5GB",
      "percentage": 25.6
    },
    "disk_usage": {
      "used": "2.1GB",
      "available": "47.9GB",
      "percentage": 4.2
    }
  }
}
```

### System Metrics

**GET** `/metrics`

Prometheus-compatible metrics endpoint.

#### Example Response

```
# HELP http_requests_total Total HTTP requests
# TYPE http_requests_total counter
http_requests_total{method="GET",endpoint="/api/knowledge-items"} 1250
http_requests_total{method="POST",endpoint="/api/documents/upload"} 45

# HELP http_request_duration_seconds HTTP request duration
# TYPE http_request_duration_seconds histogram
http_request_duration_seconds_bucket{le="0.1"} 1000
http_request_duration_seconds_bucket{le="0.5"} 1200
http_request_duration_seconds_bucket{le="1.0"} 1250

# HELP documents_uploaded_total Total documents uploaded
# TYPE documents_uploaded_total counter
documents_uploaded_total 45

# HELP rag_queries_total Total RAG queries
# TYPE rag_queries_total counter
rag_queries_total 890
```

## 🚨 Error Handling

### Standard Error Response Format

All API errors follow a consistent format:

```json
{
  "error": {
    "code": "VALIDATION_ERROR",
    "message": "Invalid request parameters",
    "details": {
      "field": "knowledge_type",
      "issue": "Must be one of: technical, business, general"
    },
    "timestamp": "2024-01-15T10:45:00Z",
    "request_id": "req_abc123def456"
  }
}
```

### Common Error Codes

| HTTP Status | Error Code | Description |
|-------------|------------|-------------|
| 400 | `VALIDATION_ERROR` | Invalid request parameters |
| 401 | `AUTHENTICATION_ERROR` | Missing or invalid API key |
| 403 | `AUTHORIZATION_ERROR` | Insufficient permissions |
| 404 | `NOT_FOUND` | Resource not found |
| 409 | `CONFLICT` | Resource already exists |
| 413 | `FILE_TOO_LARGE` | Uploaded file exceeds size limit |
| 415 | `UNSUPPORTED_MEDIA_TYPE` | Unsupported file format |
| 422 | `PROCESSING_ERROR` | Document processing failed |
| 429 | `RATE_LIMIT_EXCEEDED` | Too many requests |
| 500 | `INTERNAL_ERROR` | Server error |
| 502 | `EXTERNAL_SERVICE_ERROR` | External service unavailable |
| 503 | `SERVICE_UNAVAILABLE` | Service temporarily unavailable |

## 📊 Rate Limiting

### Default Limits

| Endpoint Category | Rate Limit | Window |
|------------------|------------|--------|
| Document Upload | 10 requests | 1 minute |
| RAG Queries | 100 requests | 1 minute |
| Crawling | 5 requests | 5 minutes |
| General API | 1000 requests | 1 hour |

### Rate Limit Headers

All responses include rate limiting headers:

```
X-RateLimit-Limit: 100
X-RateLimit-Remaining: 95
X-RateLimit-Reset: 1642248000
X-RateLimit-Window: 60
```

## 🔧 SDK & Integration Examples

### Python SDK Example

```python
import requests
import json
from typing import List, Dict, Any

class ArchonClient:
    def __init__(self, base_url: str = "http://localhost:8080"):
        self.base_url = base_url
        self.session = requests.Session()
    
    def upload_document(self, file_path: str, knowledge_type: str, tags: List[str] = None) -> Dict[str, Any]:
        """Upload a document to Archon"""
        with open(file_path, 'rb') as f:
            files = {'file': f}
            data = {
                'knowledge_type': knowledge_type,
                'tags': json.dumps(tags or [])
            }
            response = self.session.post(f"{self.base_url}/api/documents/upload", files=files, data=data)
            response.raise_for_status()
            return response.json()
    
    def query_knowledge(self, query: str, limit: int = 10, filters: Dict[str, Any] = None) -> Dict[str, Any]:
        """Query the knowledge base"""
        payload = {
            "query": query,
            "limit": limit,
            "filters": filters or {},
            "options": {"use_reranking": True, "hybrid_search": True}
        }
        response = self.session.post(f"{self.base_url}/api/rag/query", json=payload)
        response.raise_for_status()
        return response.json()
    
    def start_crawl(self, url: str, knowledge_type: str, options: Dict[str, Any] = None) -> Dict[str, Any]:
        """Start crawling a website"""
        payload = {
            "url": url,
            "knowledge_type": knowledge_type,
            "options": options or {}
        }
        response = self.session.post(f"{self.base_url}/api/knowledge-items/crawl", json=payload)
        response.raise_for_status()
        return response.json()

# Usage example
client = ArchonClient()

# Upload a document
result = client.upload_document(
    file_path="./python-guide.pdf",
    knowledge_type="technical",
    tags=["python", "programming"]
)
print(f"Document uploaded: {result['document']['id']}")

# Query knowledge
results = client.query_knowledge(
    query="How to handle exceptions in Python?",
    filters={"tags": ["python"]}
)
print(f"Found {len(results['results'])} relevant documents")
```

### JavaScript/Node.js Example

```javascript
class ArchonClient {
  constructor(baseUrl = 'http://localhost:8080') {
    this.baseUrl = baseUrl;
  }

  async uploadDocument(file, knowledgeType, tags = []) {
    const formData = new FormData();
    formData.append('file', file);
    formData.append('knowledge_type', knowledgeType);
    formData.append('tags', JSON.stringify(tags));

    const response = await fetch(`${this.baseUrl}/api/documents/upload`, {
      method: 'POST',
      body: formData
    });

    if (!response.ok) {
      throw new Error(`Upload failed: ${response.statusText}`);
    }

    return response.json();
  }

  async queryKnowledge(query, options = {}) {
    const payload = {
      query,
      limit: options.limit || 10,
      filters: options.filters || {},
      options: {
        use_reranking: true,
        hybrid_search: true,
        ...options.searchOptions
      }
    };

    const response = await fetch(`${this.baseUrl}/api/rag/query`, {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json'
      },
      body: JSON.stringify(payload)
    });

    if (!response.ok) {
      throw new Error(`Query failed: ${response.statusText}`);
    }

    return response.json();
  }

  async startCrawl(url, knowledgeType, options = {}) {
    const payload = {
      url,
      knowledge_type: knowledgeType,
      options
    };

    const response = await fetch(`${this.baseUrl}/api/knowledge-items/crawl`, {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json'
      },
      body: JSON.stringify(payload)
    });

    if (!response.ok) {
      throw new Error(`Crawl failed: ${response.statusText}`);
    }

    return response.json();
  }

  // WebSocket connection for real-time updates
  connectToProgress(progressId, onMessage) {
    const ws = new WebSocket(`ws://localhost:8080/api/crawl-progress/${progressId}`);
    
    ws.onmessage = (event) => {
      const data = JSON.parse(event.data);
      onMessage(data);
    };

    ws.onerror = (error) => {
      console.error('WebSocket error:', error);
    };

    return ws;
  }
}

// Usage example
const client = new ArchonClient();

// Start a crawl with progress tracking
client.startCrawl('https://docs.python.org/3/tutorial/', 'technical', {
  max_pages: 20,
  max_depth: 2
}).then(result => {
  console.log('Crawl started:', result.progress_id);
  
  // Connect to progress updates
  const ws = client.connectToProgress(result.progress_id, (progress) => {
    console.log(`Progress: ${progress.percentage}% - ${progress.current_url}`);
    
    if (progress.status === 'completed') {
      console.log('Crawl completed!');
      ws.close();
    }
  });
});
```

---

**Next Steps**: 
- Explore [MCP Integration](./mcp-reference) to connect AI clients
- Learn about [RAG Strategies](./rag) for optimal search performance
- Check [Testing Guide](./testing) for API testing examples
