# Archon - Knowledge Engine MCP Server

<p align="center">
  <em>Build Your AI's Knowledge Base with Web Crawling and Document Management</em>
</p>

<p align="center">
  <a href="#-quick-start">Quick Start</a> •
  <a href="#-whats-included">What's Included</a> •
  <a href="#-accessing-documentation">Documentation</a> •
  <a href="#-next-steps">Next Steps</a>
</p>

---

## 🎯 What is Archon?

Archon is a **Model Context Protocol (MCP) server** that creates a centralized knowledge base for your AI coding assistants. Connect Cursor, Windsurf, or Claude Desktop to give your AI agents access to:

- **Your documentation** (crawled websites, uploaded PDFs/docs)
- **Smart search capabilities** with advanced RAG strategies  
- **Task management** integrated with your knowledge base
- **Real-time updates** as you add new content

## 🚀 Quick Start

### Prerequisites
- [Docker Desktop](https://www.docker.com/products/docker-desktop/)
- [Supabase](https://supabase.com/) account (free tier works)
- [OpenAI API key](https://platform.openai.com/api-keys)

### 1. Clone & Setup

```bash
git clone https://github.com/coleam00/archon.git
cd archon

# Create environment file
cp .env-doc.md .env
```

### 2. Configure Environment

Edit `.env` and add your credentials:

```bash
# Required
SUPABASE_URL=https://your-project.supabase.co
SUPABASE_SERVICE_KEY=your-service-key-here
```

### 3. Set Up Database

1. Create a new [Supabase project](https://supabase.com/dashboard)
2. In SQL Editor, run these scripts **in order**:
   - `migration/credentials_setup.sql` (creates settings storage)
   - `migration/crawled_pages.sql` (creates vector database)
   - `migration/supabase_archon.sql` (creates task management)

### 4. Start Archon

```bash
docker-compose up -d
```

### 5. Access & Configure

| Service | URL | Purpose |
|---------|-----|---------|
| **Web Interface** | http://localhost:3737 | Main dashboard and controls |
| **Documentation** | http://localhost:3838 | Complete setup and usage guides |
| **API Docs** | http://localhost:8080/docs | FastAPI documentation |

1. Open the **Web Interface** (http://localhost:3737)
2. Go to **Settings** and add your OpenAI API key
3. Start the MCP server from the **MCP Dashboard**
4. Get connection details for your AI client

## 📚 Accessing Documentation

**Complete documentation is available at: http://localhost:3838**

The documentation includes:

- **[Getting Started Guide](http://localhost:3838/docs/getting-started)** - Detailed setup walkthrough
- **[MCP Integration](http://localhost:3838/docs/mcp-reference)** - Connect Cursor, Windsurf, Claude Desktop
- **[API Reference](http://localhost:3838/docs/api-reference)** - Complete REST API documentation
- **[RAG Strategies](http://localhost:3838/docs/rag)** - Configure search and retrieval
- **[Deployment Guide](http://localhost:3838/docs/deployment)** - Production setup

## 🛠️ What's Included

When you run `docker-compose up -d`, you get:

### Core Services
- **Frontend** (Port 3737): React dashboard for managing knowledge and tasks
- **Backend API** (Port 8080): FastAPI server with RAG capabilities
- **MCP Server** (Port 8051): Model Context Protocol server for AI clients
- **Documentation** (Port 3838): Complete Docusaurus documentation site

### Key Features  
- **Smart Web Crawling**: Automatically detects sitemaps, text files, or webpages
- **Document Processing**: Upload PDFs, Word docs, markdown, and text files
- **AI Integration**: Connect any MCP-compatible client (Cursor, Windsurf, etc.)
- **Real-time Updates**: WebSocket-based live progress tracking
- **Task Management**: Organize projects and tasks with AI agent integration

## ⚡ Quick Test

Once everything is running:

1. **Test Document Upload**: Go to http://localhost:3737 → Documents → Upload a PDF
2. **Test Web Crawling**: Knowledge Base → "Crawl Website" → Enter a docs URL
3. **Test AI Integration**: MCP Dashboard → Copy connection config for your AI client

## 🔧 Development

For development with hot reload:

```bash
# Backend (with auto-reload)
docker-compose up backend --build

# Frontend (with hot reload) 
cd archon-ui-main && npm run dev

# Documentation (with hot reload)
cd docs && npm start
```

## 🎯 Next Steps

1. **📖 [Read the Full Documentation](http://localhost:3838)** - Complete setup and usage guides
2. **🔌 [Connect Your AI Client](http://localhost:3838/docs/mcp-reference)** - Set up Cursor, Windsurf, or Claude Desktop
3. **📚 [Build Your Knowledge Base](http://localhost:3838/docs/getting-started#building-your-knowledge-base)** - Start crawling and uploading content
4. **🚀 [Deploy to Production](http://localhost:3838/docs/deployment)** - Scale for team use

## 🤝 Contributing

See our [development documentation](http://localhost:3838/docs/testing) for:
- Development setup and testing
- Architecture and code organization  
- Contributing guidelines

## 📄 License

MIT License - see [LICENSE](LICENSE) file for details.

---

<p align="center">
  <strong>Build once, query everywhere</strong><br>
  <em>Transform your AI coding experience with Archon</em>
</p>