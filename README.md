<h1 align="center">Archon - Knowledge Engine MCP Server</h1>

<p align="center">
  <em>Build Your AI's Knowledge Base with Web Crawling and Document Management</em>
</p>

Archon is a powerful knowledge engine that integrates the [Model Context Protocol (MCP)](https://modelcontextprotocol.io) with [Crawl4AI](https://crawl4ai.com) and [Supabase](https://supabase.com/) to create a centralized knowledge base for your AI agents and coding assistants. 

**Connect your Cursor or Windsurf agents to Archon** and give them access to:
- Your technical documentation
- Your business/project documentation  
- Any website content you've crawled
- A searchable knowledge base with advanced RAG capabilities

With Archon's web interface, you can **manage all your knowledge in one place** - crawl websites, upload documents, organize by type, and even chat with your knowledge base to test queries before your AI agents use them.

## 🎯 What is Archon?

Archon serves as a bridge between your documentation and your AI coding assistants. Instead of having your AI search the entire internet or work with outdated training data, Archon lets you:

1. **Build a Custom Knowledge Base**: Crawl specific documentation sites, upload your own docs, and organize them by type (technical vs business/project)
2. **Connect Your AI Tools**: Use the MCP protocol to connect Cursor, Windsurf, or any MCP-compatible AI assistant
3. **Get Relevant Answers**: Your AI agents query YOUR knowledge base with advanced RAG strategies for precise, contextual answers
4. **Test and Refine**: Use the built-in chat interface to test queries and see what knowledge your AI agents will access

## ✨ Key Features

### 📚 Knowledge Management
- **Web Crawling**: Intelligently crawl documentation sites, handling sitemaps, recursive crawling, and various content types
- **Document Upload**: Upload and process your own documentation files
- **Organization**: Segment knowledge by technical documentation vs business/project documentation
- **Source Filtering**: RAG queries can filter by specific domains or document sources

### 🤖 Advanced RAG Capabilities
- **Smart URL Detection**: Automatically detects and handles different URL types (regular webpages, sitemaps, text files)
- **Contextual Embeddings**: Enhanced semantic understanding of technical content
- **Hybrid Search**: Combines vector and keyword search for better results
- **Code Example Extraction**: Special handling for code snippets in documentation
- **Reranking**: Improves result relevance using cross-encoder models

### 🔌 MCP Integration
- **Universal Compatibility**: Works with any MCP-compatible client (Cursor, Windsurf, Claude Desktop, etc.)
- **Easy Connection**: Get connection details directly from the web UI
- **Real-time Access**: Your AI agents get immediate access to newly added knowledge

### �� Web Interface
- **MCP Dashboard**: Monitor server status, view real-time logs, and get connection configuration
- **Server Management**: Start/stop the MCP server with one click, see uptime and status
- **Settings Page**: Configure credentials (OpenAI API key) and RAG strategies through an intuitive UI
- **Crawling Dashboard**: Initiate and monitor web crawling operations
- **Document Management**: Upload and organize your documentation
- **Knowledge Chat**: Test RAG queries through an interactive chat interface
- **Real-time Log Streaming**: Watch server logs in real-time as operations execute

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

## 🎓 Using Archon

### Building Your Knowledge Base

1. **Crawl Documentation Sites**:
   - Navigate to the Knowledge Base page
   - Enter a documentation URL (e.g., `https://docs.example.com`)
   - Archon will intelligently crawl the site, following links and building your knowledge base

2. **Upload Your Documents**:
   - Use the upload feature to add your own documentation
   - Organize by type (technical vs business/project)
   - Documents are processed and indexed automatically

3. **Test with Chat**:
   - Use the built-in chat to query your knowledge base
   - See exactly what results your AI agents will get
   - Refine your content organization based on results

### Connecting AI Assistants

Once your MCP server is running, add it to your AI assistant's configuration:

**For Cursor/Windsurf**:
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

Your AI assistant can now use these tools:
- `crawl_single_page`: Process a specific page
- `smart_crawl_url`: Intelligently crawl an entire site
- `perform_rag_query`: Search the knowledge base
- `get_available_sources`: List indexed sources
- `search_code_examples`: Find code snippets (when enabled)

## 🧪 RAG Strategies

Archon includes several advanced RAG strategies you can enable through the Settings page:

### 1. **Contextual Embeddings** 
Enhances each chunk's embedding with document context for better semantic understanding.
- **Best for**: Technical docs where context is crucial
- **Trade-off**: Slower indexing, much better accuracy

### 2. **Hybrid Search**
Combines vector similarity with keyword matching.
- **Best for**: Technical content with specific terms/functions
- **Trade-off**: Slightly slower, more comprehensive results

### 3. **Agentic RAG** 
Extracts and indexes code examples separately with summaries.
- **Best for**: Developer documentation with code samples
- **Trade-off**: Slower crawling, enables specialized code search

### 4. **Reranking**
Re-scores results using a cross-encoder model for better relevance.
- **Best for**: Complex queries requiring precision
- **Trade-off**: +100-200ms latency, significantly better ranking

### Recommended Configurations

Configure these in the Settings page based on your use case:

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

## 🔮 Vision & Roadmap

Archon is evolving to become the ultimate knowledge engine for AI coding assistants:

1. **Multi-Model Support**: Beyond OpenAI - support for Ollama and local models
2. **Advanced Chunking**: Context-aware chunking strategies for better retrieval
3. **Knowledge Graphs**: Visual representation of your knowledge connections
4. **Team Collaboration**: Shared knowledge bases for development teams
5. **Performance Optimization**: Faster crawling and real-time indexing

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

## 📚 Advanced Usage

### Direct MCP Integration

While the UI is the recommended way to use Archon, you can also integrate directly:

```json
{
  "mcpServers": {
    "archon": {
      "command": "python",
      "args": ["path/to/archon/src/crawl4ai_mcp.py"],
      "env": {
        "TRANSPORT": "stdio",
        "OPENAI_API_KEY": "your_key",
        "SUPABASE_URL": "your_url",
        "SUPABASE_SERVICE_KEY": "your_key"
      }
    }
  }
}
```

### API Access

The Backend API is available at http://localhost:8080/docs for programmatic access to:
- Crawling operations
- RAG queries
- Knowledge base management
- Server control

## 🤝 Contributing

Archon is designed to grow with the community's needs. We welcome contributions for:
- Additional document processors
- New embedding models
- Enhanced UI features
- Performance optimizations
- Integration improvements

## 📄 License

This project is licensed under the MIT License - see the [LICENSE](LICENSE) file for details.