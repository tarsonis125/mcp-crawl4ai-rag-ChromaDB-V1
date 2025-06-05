---
title: Configuration
sidebar_position: 2
---

# Configuration

This guide covers configuring Archon after installation, including environment variables, database setup, and service configuration.

## Environment Variables

Create a `.env` file in your project root with the following configuration:

```bash
# Supabase Configuration
SUPABASE_URL=https://xxxxx.supabase.co
SUPABASE_SERVICE_ROLE_KEY=eyJ...

# OpenAI Configuration
OPENAI_API_KEY=sk-...

# Server Configuration
ARCHON_API_PORT=8080
ARCHON_MCP_PORT=8051
ARCHON_UI_PORT=3737
ARCHON_DOCS_PORT=3838

# Optional: Custom endpoints
ARCHON_API_HOST=0.0.0.0
ARCHON_MCP_HOST=0.0.0.0

# Optional: Development settings
DEBUG=false
LOG_LEVEL=INFO
```

## Database Configuration

Archon requires a Supabase PostgreSQL database with pgvector extension. See the [Getting Started](./getting-started#step-2-supabase-database-setup) guide for detailed setup instructions.

### Required Tables

The following tables are automatically created when you run the SQL scripts:

- `credentials` - Stores API keys and configuration
- `crawled_pages` - Main knowledge base with vector embeddings
- `projects` - Project management
- `tasks` - Task tracking

## Service Configuration

### API Server Settings

The FastAPI backend can be configured via environment variables:

```bash
# API Configuration
ARCHON_API_PORT=8080        # API server port
ARCHON_API_HOST=0.0.0.0     # API server host
CORS_ORIGINS=*              # CORS allowed origins
```

### MCP Server Settings

The Model Context Protocol server configuration:

```bash
# MCP Configuration  
ARCHON_MCP_PORT=8051        # MCP server port
ARCHON_MCP_HOST=0.0.0.0     # MCP server host
MCP_TRANSPORT=sse           # Transport method (sse/stdio)
```

### Frontend Settings

The React UI configuration:

```bash
# Frontend Configuration
ARCHON_UI_PORT=3737         # Frontend port
REACT_APP_API_URL=http://localhost:8080  # API endpoint
```

## Advanced Configuration

### RAG Settings

Configure retrieval-augmented generation behavior:

```bash
# RAG Configuration
EMBEDDING_MODEL=text-embedding-3-small
CHUNK_SIZE=1000
CHUNK_OVERLAP=200
MAX_RESULTS=10
SIMILARITY_THRESHOLD=0.7
```

### Crawling Settings

Configure web crawling behavior:

```bash
# Crawling Configuration
MAX_CRAWL_DEPTH=3
CRAWL_DELAY=1
MAX_PAGES_PER_CRAWL=100
USER_AGENT=Archon-Crawler/1.0
```

## Docker Configuration

When using Docker, you can override settings in `docker-compose.yml`:

```yaml
version: '3.8'
services:
  backend:
    environment:
      - SUPABASE_URL=${SUPABASE_URL}
      - SUPABASE_SERVICE_ROLE_KEY=${SUPABASE_SERVICE_ROLE_KEY}
      - OPENAI_API_KEY=${OPENAI_API_KEY}
    ports:
      - "8080:8080"
      - "8051:8051"
  
  frontend:
    environment:
      - REACT_APP_API_URL=http://localhost:8080
    ports:
      - "3737:3737"
```

## Security Configuration

### API Keys

Store sensitive credentials securely:

1. **Never commit API keys to version control**
2. **Use environment variables or secret management**
3. **Rotate keys regularly**
4. **Use least-privilege access**

### CORS Settings

Configure CORS for your deployment environment:

```bash
# Development
CORS_ORIGINS=http://localhost:3737,http://localhost:3000

# Production
CORS_ORIGINS=https://your-domain.com
```

## Validation

After configuration, validate your setup:

1. **Test database connection**:
   ```bash
   docker-compose exec backend python -c "from src.config import get_supabase_client; print('Connected:', get_supabase_client())"
   ```

2. **Verify API keys**:
   ```bash
   docker-compose logs backend | grep "OpenAI"
   ```

3. **Check service health**:
   ```bash
   curl http://localhost:8080/health
   curl http://localhost:8051/health
   ```

## Troubleshooting

Common configuration issues:

### Database Connection Issues
- Verify Supabase URL and service role key
- Check network connectivity
- Ensure pgvector extension is installed

### API Key Issues  
- Verify OpenAI API key format (starts with `sk-`)
- Check API key permissions and billing
- Test key with simple API call

### Port Conflicts
- Check if ports are already in use: `netstat -an | grep :8080`
- Change ports in environment variables
- Update Docker port mappings

## Next Steps

Once configured, proceed to:
- [Getting Started](./getting-started) - Complete setup process
- [Deployment](./deployment) - Production deployment
- [API Reference](./api-reference) - Start using the API 