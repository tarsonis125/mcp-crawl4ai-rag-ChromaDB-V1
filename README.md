<h1 align="center">Archon - Knowledge Engine MCP Server</h1>

<p align="center">
  <em>Build Your AI's Knowledge Base with Web Crawling and Document Management</em>
</p>

<p align="center">
  <a href="#-quick-start">Quick Start</a> •
  <a href="#-features">Features</a> •
  <a href="#-usage-guide">Usage</a> •
  <a href="#-mcp-integration">MCP Integration</a> •
  <a href="#-contributing">Contributing</a>
</p>

---

## 📑 Table of Contents

1. [What is Archon?](#-what-is-archon)
2. [Key Features](#-key-features)
3. [Quick Start](#-quick-start)
4. [Usage Guide](#-usage-guide)
   - [Building Your Knowledge Base](#building-your-knowledge-base)
   - [Web Crawling](#web-crawling)
   - [Document Upload](#document-upload)
   - [Testing with Chat](#testing-with-chat)
5. [MCP Integration](#-mcp-integration)
6. [RAG Strategies](#-rag-strategies)
7. [API Reference](#-api-reference)
8. [Development](#-development)
9. [Contributing](#-contributing)

---

## 🎯 What is Archon?

Archon is a powerful knowledge engine that integrates the [Model Context Protocol (MCP)](https://modelcontextprotocol.io) with [Crawl4AI](https://crawl4ai.com) and [Supabase](https://supabase.com/) to create a centralized knowledge base for your AI agents and coding assistants.

**Connect your Cursor or Windsurf agents to Archon** and give them access to:
- Your technical documentation
- Your business/project documentation  
- Any website content you've crawled
- Uploaded documents (PDFs, Word docs, markdown files)
- A searchable knowledge base with advanced RAG capabilities

With Archon's web interface, you can **manage all your knowledge in one place** - crawl websites, upload documents, organize by type, and even chat with your knowledge base to test queries before your AI agents use them.

---

## ✨ Key Features

### 📚 Knowledge Management
- **Web Crawling**: Intelligently crawl documentation sites, handling sitemaps, recursive crawling, and various content types
- **Document Upload**: Upload and process PDFs, Word documents, markdown, and text files
- **Organization**: Segment knowledge by technical documentation vs business/project documentation
- **Source Filtering**: RAG queries can filter by specific domains or document sources

### 📄 Document Processing
- **PDF Support**: Dual-engine extraction (PyPDF2 + pdfplumber) for reliable text extraction
- **Word Documents**: Full support for .doc and .docx files via python-docx
- **Markdown & Text**: Direct processing of .md and .txt files
- **Smart Chunking**: Context-aware content chunking preserving structure
- **AI-Generated Metadata**: Automatic title and description generation for uploaded documents

### 🤖 Advanced RAG Capabilities
- **Smart URL Detection**: Automatically detects and handles different URL types (regular webpages, sitemaps, text files)
- **Contextual Embeddings**: Enhanced semantic understanding of technical content
- **Hybrid Search**: Combines vector and keyword search for better results
- **Code Example Extraction**: Special handling for code snippets in documentation
- **Reranking**: Improves result relevance using cross-encoder models

### 🔌 MCP Integration
- **Universal Compatibility**: Works with any MCP-compatible client (Cursor, Windsurf, Claude Desktop, etc.)
- **Dual Transport**: SSE for web clients, stdio for standard MCP clients
- **Easy Connection**: Get connection details directly from the web UI
- **Real-time Access**: Your AI agents get immediate access to newly added knowledge

### 🖥 Web Interface
- **MCP Dashboard**: Monitor server status, view real-time logs, and get connection configuration
- **Server Management**: Start/stop the MCP server with one click, see uptime and status
- **Settings Page**: Configure credentials (OpenAI API key) and RAG strategies through an intuitive UI
- **Crawling Dashboard**: Initiate and monitor web crawling operations
- **Document Management**: Upload and organize your documentation with drag-and-drop interface
- **Knowledge Chat**: Test RAG queries through an interactive chat interface
- **Real-time Log Streaming**: Watch server logs in real-time as operations execute

---

## 🚀 Quick Start

### Prerequisites

- [Docker/Docker Desktop](https://www.docker.com/products/docker-desktop/)
- [Supabase](https://supabase.com/) account (free tier works great)
- [OpenAI API key](https://platform.openai.com/api-keys) for embeddings

### Setup Process

1. **Clone Archon**:
   ```bash
   git clone https://github.com/coleam00/archon.git
   cd archon
   ```

2. **Set up Supabase Database**:
   - Create a new Supabase project (or use existing)
   - Go to SQL Editor in your Supabase dashboard
   - Run `credentials_setup.sql` first (creates settings storage)
   - Run `crawled_pages.sql` second (creates vector database)

3. **Configure Environment**:
   ```bash
   cp .env-doc.md .env
   # Edit .env and add only these two values:
   # SUPABASE_URL=your_supabase_project_url
   # SUPABASE_SERVICE_KEY=your_supabase_service_key
   ```

4. **Start Archon**:
   ```bash
   docker-compose up --build
   ```

5. **Access the Web UI**:
   - Open http://localhost:3737
   - Go to Settings and add your OpenAI API key
   - Configure RAG strategies (Contextual Embeddings, Hybrid Search, Agentic RAG, Reranking)
   - Start the MCP server from the MCP Dashboard
   - Monitor server logs and status in real-time

6. **Connect Your AI Assistant**:
   - Go to the MCP Dashboard when server is running
   - Click "Copy Configuration" to get the connection details
   - Add to your Cursor/Windsurf settings (usually `~/.cursor/mcp.json` or equivalent)
   - Your AI now has access to your knowledge base!

---

## 📖 Usage Guide

### Building Your Knowledge Base

Archon provides multiple ways to build and manage your knowledge base:

### Web Crawling

1. **Navigate to Knowledge Base**: Go to the Knowledge Base page in the web UI
2. **Enter URL**: Input a documentation URL (e.g., `https://docs.example.com`)
3. **Configure Options**:
   - **Knowledge Type**: Technical or Business/Project
   - **Tags**: Add relevant tags for organization
   - **Crawl Depth**: Set maximum recursion depth (default: 3)
   - **Concurrent Limit**: Control crawling speed (default: 10)

4. **Smart Detection**: Archon automatically detects and handles:
   - **Regular webpages**: Recursive crawling following internal links
   - **Sitemaps**: Extracts and processes all URLs from sitemap.xml
   - **Text files**: Direct content processing for .txt files

### Document Upload

Upload and process your own documentation files:

#### Supported Formats

| Format | Extensions | Processing Method |
|--------|------------|------------------|
| **PDF** | `.pdf` | PyPDF2 + pdfplumber (dual-engine for reliability) |
| **Word** | `.doc`, `.docx` | python-docx library |
| **Markdown** | `.md` | Direct text processing |
| **Text** | `.txt` | Direct text processing |

#### Upload Process

1. **Access Upload**: Go to Knowledge Base → Add Knowledge → Upload File
2. **Select File**: Choose your document (max 10MB)
3. **Set Metadata**:
   - **Knowledge Type**: Technical or Business/Project
   - **Tags**: Add relevant tags for categorization
4. **Upload & Process**: Files are automatically:
   - Text extracted using appropriate libraries
   - Content chunked preserving structure
   - AI-generated title and description created
   - Indexed with embeddings for search
   - Code examples extracted (if Agentic RAG enabled)

#### Upload Features

- **File Validation**: Size limits, format checking, content verification
- **AI-Generated Metadata**: Automatic title and description generation from content
- **Smart Chunking**: Preserves document structure (headings, paragraphs, code blocks)
- **Progress Tracking**: Real-time upload and processing status
- **Error Handling**: Clear feedback for unsupported files or processing errors

#### Example Upload Flow

```bash
# Test upload via API (for development/testing)
curl -X POST "http://localhost:8080/api/documents/upload" \
  -F "file=@your_document.pdf" \
  -F "knowledge_type=technical" \
  -F "tags=[\"documentation\", \"api\"]"
```

### Testing with Chat

1. **Built-in Chat Interface**: Use the knowledge chat to test queries
2. **Query Testing**: See exactly what results your AI agents will receive
3. **Source Filtering**: Test queries against specific sources
4. **Result Analysis**: Review relevance scores and content chunks
5. **Refinement**: Adjust content organization based on test results

---

## 🔌 MCP Integration

### Transport Selection

Choose the appropriate transport method for your MCP client:

#### SSE Transport (Recommended for Web Clients)

Best for web-based integrations and dashboard control:

```json
{
  "mcpServers": {
    "archon": {
      "transport": "sse",
      "url": "http://localhost:8051/sse"
    }
  }
}
```

**Note for Windsurf**: Use `serverUrl` instead of `url`:
```json
{
  "mcpServers": {
    "archon": {
      "transport": "sse", 
      "serverUrl": "http://localhost:8051/sse"
    }
  }
}
```

#### Stdio Transport (For Standard MCP Clients)

Best for Cursor, Claude Desktop, and other standard MCP clients:

```json
{
  "mcpServers": {
    "archon": {
      "command": "docker",
      "args": [
        "run", "--rm", "-i",
        "--network", "mcp-crawl4ai-rag-ui_app-network",
        "-e", "TRANSPORT=stdio",
        "-e", "OPENAI_API_KEY",
        "-e", "SUPABASE_URL", 
        "-e", "SUPABASE_SERVICE_KEY",
        "mcp-crawl4ai-rag-ui-backend"
      ],
      "env": {
        "OPENAI_API_KEY": "your_openai_api_key",
        "SUPABASE_URL": "your_supabase_url",
        "SUPABASE_SERVICE_KEY": "your_supabase_service_key"
      }
    }
  }
}
```

### Available MCP Tools

Your AI assistant gains access to these tools:

| Tool | Description | Parameters |
|------|-------------|------------|
| `crawl_single_page` | Process a specific webpage | `url` |
| `smart_crawl_url` | Intelligently crawl an entire site | `url`, `max_depth`, `max_concurrent`, `chunk_size` |
| `upload_document` | Upload and process documents | `file_content`, `filename`, `knowledge_type`, `tags` |
| `perform_rag_query` | Search the knowledge base | `query`, `source`, `match_count` |
| `get_available_sources` | List all indexed sources | None |
| `search_code_examples` | Find code snippets | `query`, `source_id`, `match_count` |
| `delete_source` | Remove a source and its content | `source_id` |

---

## 🌐 Real-time Communication Architecture

Archon uses WebSocket connections for real-time streaming between the frontend and backend:

### WebSocket Endpoints

| Endpoint | Purpose | Status |
|----------|---------|--------|
| `/api/mcp/logs/stream` | MCP Server logs streaming | ✅ Working |
| `/api/crawl-progress/{progress_id}` | Crawl progress updates | ✅ Working |
| `/api/knowledge-items/stream` | Knowledge base updates | ✅ Working |

### Network Configuration

The Docker setup creates an isolated network (`mcp-crawl4ai-rag-ui_app-network`) where:

- **Frontend Container**: Runs on port 3737 (Vite dev server)
- **Backend Container**: Runs on ports 8080 (API) and 8051 (MCP Server)
- **WebSocket Protocol**: Automatically upgraded from HTTP (`ws://localhost:8080`)

### Connection Flow

1. **Frontend** connects to WebSocket endpoints via browser
2. **Docker Network** routes traffic between containers
3. **Backend** manages WebSocket connections and broadcasts updates
4. **Real-time Updates** flow from backend processes → WebSocket → frontend UI

### Troubleshooting WebSocket Issues

If WebSocket connections fail:

1. **Check Docker network**: `docker network ls | grep mcp-crawl4ai`
2. **Verify container ports**: `docker ps` (should show 8080:8080 mapping)
3. **Test HTTP connectivity**: `curl http://localhost:8080/api/mcp/status`
4. **Check browser console** for WebSocket error messages
5. **Restart containers**: `docker-compose restart`

The system automatically handles reconnection with exponential backoff (5-second delay).

---

## 🧪 RAG Strategies

Configure advanced RAG strategies through the Settings page:

### Strategy Options

#### 1. **Contextual Embeddings** 
Enhances each chunk's embedding with document context for better semantic understanding.
- **Best for**: Technical docs where context is crucial
- **Trade-off**: Slower indexing, much better accuracy

#### 2. **Hybrid Search**
Combines vector similarity with keyword matching.
- **Best for**: Technical content with specific terms/functions
- **Trade-off**: Slightly slower, more comprehensive results

#### 3. **Agentic RAG** 
Extracts and indexes code examples separately with summaries.
- **Best for**: Developer documentation with code samples
- **Trade-off**: Slower crawling, enables specialized code search

#### 4. **Reranking**
Re-scores results using a cross-encoder model for better relevance.
- **Best for**: Complex queries requiring precision
- **Trade-off**: +100-200ms latency, significantly better ranking

### Recommended Configurations

**For General Documentation**:
- Contextual Embeddings: OFF
- Hybrid Search: ON
- Agentic RAG: OFF
- Reranking: ON

**For Technical/Code Documentation**:
- Contextual Embeddings: ON
- Hybrid Search: ON
- Agentic RAG: ON
- Reranking: ON

---

## 📚 API Reference

### REST API Endpoints

The Backend API is available at `http://localhost:8080/docs` for programmatic access:

#### Knowledge Management
- `POST /api/knowledge-items/crawl` - Crawl a URL
- `POST /api/documents/upload` - Upload a document
- `GET /api/knowledge-items` - List knowledge items
- `DELETE /api/knowledge-items/{source_id}` - Delete a source

#### RAG Operations
- `POST /api/rag/query` - Perform RAG search
- `GET /api/rag/sources` - Get available sources

#### Server Management
- `POST /api/mcp/start` - Start MCP server
- `POST /api/mcp/stop` - Stop MCP server
- `GET /api/mcp/status` - Get server status

---

## 🛠️ Development

### Running for Development

```bash
# Backend API (with hot reload)
python -m uvicorn src.api_wrapper:app --host 0.0.0.0 --port 8080 --reload

# Frontend (with hot reload)
cd archon-ui-main
npm run dev

# MCP Server (for testing)
python src/crawl4ai_mcp.py
```

### Architecture

- **Frontend**: React + Vite (port 3737)
- **Backend API**: FastAPI wrapper (port 8080)
- **MCP Server**: Python implementation (port 8051)
- **Database**: Supabase (pgvector for embeddings)

### Testing Document Upload

```bash
# Test markdown upload
curl -X POST "http://localhost:8080/api/documents/upload" \
  -F "file=@test.md" \
  -F "knowledge_type=technical" \
  -F "tags=[\"test\"]"

# Test PDF upload
curl -X POST "http://localhost:8080/api/documents/upload" \
  -F "file=@document.pdf" \
  -F "knowledge_type=business" \
  -F "tags=[\"manual\", \"guide\"]"
```

---

## 🔮 Future Enhancements

### Potential Docusaurus Migration

For enhanced documentation experience, we're considering migrating to [Docusaurus](https://docusaurus.io/):

#### Benefits of Docusaurus
- **Interactive Documentation**: Live React components and examples
- **Better Navigation**: Automatic sidebar generation and search
- **Versioning**: Support for multiple documentation versions
- **Community Features**: Easy contribution workflow with GitHub integration
- **Mobile Responsive**: Better mobile experience than static README

#### Quick Setup (If We Migrate)
```bash
npx create-docusaurus@latest archon-docs classic
cd archon-docs && npm start
```

#### Pros & Cons

**Pros**:
- Professional documentation site
- Better organization and navigation
- Enhanced search capabilities
- Community contribution friendly
- Mobile responsive design

**Cons**:
- Additional maintenance overhead
- More complex deployment pipeline
- Overkill for simple project documentation

### Other Roadmap Items

1. **Multi-Model Support**: Beyond OpenAI - support for Ollama and local models
2. **Advanced Chunking**: Context-aware chunking strategies for better retrieval
3. **Knowledge Graphs**: Visual representation of your knowledge connections
4. **Team Collaboration**: Shared knowledge bases for development teams
5. **Performance Optimization**: Faster crawling and real-time indexing

---

## 🤝 Contributing

Archon is designed to grow with the community's needs. We welcome contributions for:

### Areas for Contribution
- **Document Processors**: Additional file format support (EPUB, RTF, etc.)
- **Embedding Models**: Support for local models and alternatives to OpenAI
- **UI Enhancements**: Better visualization and user experience
- **Performance**: Optimization for large-scale knowledge bases
- **Integration**: New MCP client integrations

### Getting Started
1. Fork the repository
2. Create a feature branch
3. Make your changes
4. Add tests if applicable
5. Submit a pull request

### Development Guidelines
- Follow existing code style and patterns
- Add documentation for new features
- Test your changes thoroughly
- Update README if needed

---

## 📄 License

This project is licensed under the MIT License - see the [LICENSE](LICENSE) file for details.

---

<p align="center">
  <strong>Transform your AI coding experience with Archon</strong><br>
  <em>Build once, query everywhere</em>
</p>