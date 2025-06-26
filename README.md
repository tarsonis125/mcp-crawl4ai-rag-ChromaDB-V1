# Archon - Knowledge Engine MCP Server

<p align="center">
  <em>Build Your AI's Knowledge Base with Web Crawling and Document Management</em>
</p>

<p align="center">
  <a href="#-quick-start">Quick Start</a> •
  <a href="#-connecting-to-cursor-ide">Cursor Setup</a> •
  <a href="#-documentation">Documentation</a>
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

### Initial Setup

```bash
# Clone the repository
git clone https://github.com/coleam00/archon.git
cd archon

# Create environment file
cp .env.example .env
```

Edit `.env` and add your Supabase credentials:

```bash
# Required
SUPABASE_URL=https://your-project.supabase.co
SUPABASE_SERVICE_KEY=your-service-key-here
```

## Step 1: Initial Setup - Enable RAG Crawl and Document Upload

1. **Set Up Database**: In your [Supabase project](https://supabase.com/dashboard) SQL Editor, run:
   ```sql
   -- Copy and paste the contents of migration/1_initial_setup.sql
   ```

2. **Start Archon**:
   ```bash
   docker-compose up --build -d
   ```

3. **Configure API Key**:
   - Open http://localhost:3737
   - Go to **Settings** → Add your OpenAI API key
   - Test by uploading a document or crawling a website

## Step 2: Install Projects Module

1. **Add Project Management**: In Supabase SQL Editor, run:
   ```sql
   -- Copy and paste the contents of migration/2_archon_projects.sql
   ```

2. **Restart Python Server**:
   ```bash
   docker-compose restart archon-api
   ```

3. **Enable Projects Feature**:
   - Go to **Settings** in the web interface
   - Toggle **"Enable Projects Feature"** to ON
   - Access projects at http://localhost:3737/projects

## Step 3: Enable MCP Client Management (Optional)

1. **Add MCP Client Features**: In Supabase SQL Editor, run:
   ```sql
   -- Copy and paste the contents of migration/3_mcp_client_management.sql
   ```

2. **Restart Services**:
   ```bash
   docker-compose restart
   ```

3. **Configure MCP Clients**:
   - Access MCP Dashboard at http://localhost:3737/mcp
   - Add and manage MCP client connections

## 🔄 Database Reset (Start Fresh)

If you need to completely reset your database and start fresh:

<details>
<summary>⚠️ <strong>Reset Database - This will delete ALL data!</strong></summary>

1. **Run Reset Script**: In your Supabase SQL Editor, run:
   ```sql
   -- Copy and paste the contents of migration/RESET_DB.sql
   -- ⚠️ WARNING: This will delete all data!
   ```

2. **Rebuild Database**: After reset, run the migration files in order:
   ```sql
   -- Step 1: Run migration/1_initial_setup.sql
   -- Step 2: Run migration/2_archon_projects.sql
   -- Step 3: Run migration/3_mcp_client_management.sql (optional)
   ```

3. **Restart Services**:
   ```bash
   docker-compose restart
   ```

4. **Reconfigure**: 
   - Add your OpenAI API key in Settings
   - Re-upload any documents or re-crawl websites
   - Enable Projects feature if needed

The reset script safely removes all tables, functions, triggers, and policies with proper dependency handling.

</details>

## 🔌 Connecting to Cursor IDE

Add this configuration to your Cursor settings:

**File**: `~/.cursor/mcp.json`

```json
{
  "mcpServers": {
    "archon": {
      "command": "docker",
      "args": [
        "exec", 
        "-i",
        "-e", "TRANSPORT=stdio",
        "-e", "HOST=localhost", 
        "-e", "PORT=8051",
        "archon-api",
        "python", "src/mcp_server.py"
      ]
    }
  }
}
```

## 📚 Documentation

**Complete documentation is available at: http://localhost:3838**

| Service | URL | Purpose |
|---------|-----|---------|
| **Web Interface** | http://localhost:3737 | Main dashboard and controls |
| **Documentation** | http://localhost:3838 | Complete setup and usage guides |
| **API Docs** | http://localhost:8080/docs | FastAPI documentation |

## ⚡ Quick Test

Once everything is running:

1. **Test Document Upload**: Go to http://localhost:3737 → Knowledge Base → Upload a PDF
2. **Test Web Crawling**: Knowledge Base → "Crawl Website" → Enter a docs URL
3. **Test Projects**: Projects → Create a new project and add tasks
4. **Test AI Integration**: MCP Dashboard → Copy connection config for your AI client

## 🛠️ What's Included

- **Smart Web Crawling**: Automatically detects sitemaps, text files, or webpages
- **Document Processing**: Upload PDFs, Word docs, markdown, and text files
- **AI Integration**: Connect any MCP-compatible client (Cursor, Windsurf, etc.)
- **Task Management**: Organize projects and tasks with AI agent integration
- **Real-time Updates**: WebSocket-based live progress tracking

## 🔧 Development

For development with hot reload:

```bash
# Backend (with auto-reload)
docker-compose up archon-api --build

# Frontend (with hot reload) 
cd archon-ui-main && npm run dev

# Documentation (with hot reload)
cd docs && npm start
```

## 📄 License

MIT License - see [LICENSE](LICENSE) file for details.

---

<p align="center">
  <strong>Build once, query everywhere</strong><br>
  <em>Transform your AI coding experience with Archon</em>
</p>