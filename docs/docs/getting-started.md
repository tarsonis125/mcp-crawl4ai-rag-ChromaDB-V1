---
title: Getting Started
sidebar_position: 2
---

# Getting Started with Archon

This comprehensive guide will walk you through setting up Archon from scratch, configuring all components, and getting your first knowledge base operational.

## 📋 Prerequisites

Before you begin, ensure you have the following:

### Required Software
- **[Docker Desktop](https://www.docker.com/products/docker-desktop/)** (v4.0+)
- **[Git](https://git-scm.com/)** for cloning the repository
- **Web Browser** (Chrome, Firefox, Safari, or Edge)

### Required Accounts & API Keys
- **[Supabase Account](https://supabase.com/)** (free tier sufficient)
- **[OpenAI API Key](https://platform.openai.com/api-keys)** for embeddings

### System Requirements
- **RAM**: 4GB minimum, 8GB recommended
- **Storage**: 2GB free space
- **Network**: Internet connection for initial setup and API calls

## 🚀 Installation Process

### Step 1: Clone the Repository

```bash
# Clone the Archon repository
git clone https://github.com/coleam00/archon.git
cd archon

# Check available branches
git branch -a

# Switch to the latest feature branch if needed
git checkout feature/docusauraus
```

### Step 2: Supabase Database Setup

Archon uses Supabase as its primary database with pgvector for embeddings.

#### 2.1 Create Supabase Project

1. Go to [Supabase Dashboard](https://supabase.com/dashboard)
2. Click **"New Project"**
3. Choose your organization
4. Enter project details:
   - **Name**: `archon-knowledge-base` (or your preferred name)
   - **Database Password**: Generate a strong password
   - **Region**: Choose closest to your location
5. Click **"Create new project"**
6. Wait for project initialization (2-3 minutes)

#### 2.2 Configure Database Schema

Run the following SQL scripts in order in your Supabase SQL Editor:

**First: Credentials Setup**
```sql
-- credentials_setup.sql
-- Creates the settings storage for API keys and configuration

CREATE TABLE IF NOT EXISTS credentials (
    id SERIAL PRIMARY KEY,
    key_name VARCHAR(255) UNIQUE NOT NULL,
    key_value TEXT NOT NULL,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Create an index for faster lookups
CREATE INDEX IF NOT EXISTS idx_credentials_key_name ON credentials(key_name);

-- Insert default settings
INSERT INTO credentials (key_name, key_value) VALUES 
('openai_api_key', '')
ON CONFLICT (key_name) DO NOTHING;
```

**Second: Vector Database Setup**
```sql
-- crawled_pages.sql
-- Creates the main knowledge base tables with vector support

-- Enable the pgvector extension
CREATE EXTENSION IF NOT EXISTS vector;

-- Create the main crawled_pages table
CREATE TABLE IF NOT EXISTS crawled_pages (
    id SERIAL PRIMARY KEY,
    url TEXT NOT NULL,
    title TEXT,
    content TEXT NOT NULL,
    embedding vector(1536),
    source_type VARCHAR(50) DEFAULT 'web',
    knowledge_type VARCHAR(50) DEFAULT 'general',
    tags TEXT[] DEFAULT '{}',
    metadata JSONB DEFAULT '{}',
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Create indexes for better performance
CREATE INDEX IF NOT EXISTS idx_crawled_pages_url ON crawled_pages(url);
CREATE INDEX IF NOT EXISTS idx_crawled_pages_source_type ON crawled_pages(source_type);
CREATE INDEX IF NOT EXISTS idx_crawled_pages_knowledge_type ON crawled_pages(knowledge_type);
CREATE INDEX IF NOT EXISTS idx_crawled_pages_tags ON crawled_pages USING GIN(tags);
CREATE INDEX IF NOT EXISTS idx_crawled_pages_embedding ON crawled_pages USING ivfflat (embedding vector_cosine_ops) WITH (lists = 100);

-- Create function to update the updated_at timestamp
CREATE OR REPLACE FUNCTION update_updated_at_column()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = CURRENT_TIMESTAMP;
    RETURN NEW;
END;
$$ language 'plpgsql';

-- Create trigger to automatically update updated_at
CREATE TRIGGER update_crawled_pages_updated_at
    BEFORE UPDATE ON crawled_pages
    FOR EACH ROW
    EXECUTE FUNCTION update_updated_at_column();
```

**Third: Task Management Setup**
```sql
-- supabase_archon.sql
-- Creates the project and task management tables

-- UUID helper (optional if your Supabase project already has it)
CREATE EXTENSION IF NOT EXISTS "pgcrypto";

-- Enumerations
CREATE TYPE task_status AS ENUM ('todo','doing','blocked','done');

-- Projects table
CREATE TABLE IF NOT EXISTS projects (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  title TEXT NOT NULL,
  prd JSONB DEFAULT '{}'::jsonb,
  docs JSONB DEFAULT '[]'::jsonb,
  features JSONB DEFAULT '[]'::jsonb,
  data JSONB DEFAULT '[]'::jsonb,
  github_repo TEXT,
  created_at TIMESTAMPTZ DEFAULT NOW(),
  updated_at TIMESTAMPTZ DEFAULT NOW()
);

-- Tasks table
CREATE TABLE IF NOT EXISTS tasks (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  project_id UUID NOT NULL REFERENCES projects(id) ON DELETE CASCADE,
  parent_task_id UUID REFERENCES tasks(id) ON DELETE CASCADE,
  title TEXT NOT NULL,
  description TEXT,
  sources JSONB DEFAULT '[]'::jsonb,
  code_examples JSONB DEFAULT '[]'::jsonb,
  status task_status DEFAULT 'todo',
  created_at TIMESTAMPTZ DEFAULT NOW(),
  updated_at TIMESTAMPTZ DEFAULT NOW()
);

-- Indexes for better performance
CREATE INDEX IF NOT EXISTS idx_tasks_project ON tasks(project_id);
CREATE INDEX IF NOT EXISTS idx_tasks_parent ON tasks(parent_task_id);
CREATE INDEX IF NOT EXISTS idx_tasks_status ON tasks(status);
```

#### 2.3 Get Connection Details

1. In your Supabase project dashboard, go to **Settings > API**
2. Copy the following values:
   - **Project URL** (looks like: `https://xxxxx.supabase.co`)
   - **Service Role Key** (starts with `eyJ...`)

### Step 3: Environment Configuration

#### 3.1 Create Environment File

```bash
# Copy the example environment file
cp .env-doc.md .env

# Edit the .env file with your preferred editor
nano .env
# or
vim .env
# or
code .env
```

#### 3.2 Configure Environment Variables

Add only these two essential variables to your `.env` file:

```bash
# Supabase Configuration
SUPABASE_URL=https://your-project-id.supabase.co
SUPABASE_SERVICE_KEY=your-service-role-key-here

# Optional: Set custom ports if needed
# FRONTEND_PORT=3737
# BACKEND_PORT=8080
# MCP_PORT=8051
```

:::warning Important Security Note
Never commit your `.env` file to version control. The `.gitignore` file already excludes it.
:::

### Step 4: Launch Archon

#### 4.1 Start with Docker Compose

```bash
# Build and start all services
docker-compose up -d

# Check that all services are running
docker-compose ps

# View logs if needed
docker-compose logs -f
```

#### 4.2 Verify Services

Check that all services are accessible:

| Service | URL | Purpose |
|---------|-----|----------|
| **Frontend** | http://localhost:3737 | Main web interface |
| **Backend API** | http://localhost:8080/docs | FastAPI documentation |
| **MCP Server** | Port 8051 | Model Context Protocol server |

### Step 5: Initial Configuration

#### 5.1 Configure OpenAI API Key

1. Open http://localhost:3737 in your browser
2. Navigate to **Settings** (gear icon)
3. Enter your OpenAI API key
4. Click **Save Settings**
5. Verify the key is saved (green checkmark should appear)

#### 5.2 Test Basic Functionality

**Test Document Upload:**
1. Go to **Documents** tab
2. Drag and drop a PDF or markdown file
3. Select knowledge type (Technical/Business)
4. Add tags if desired
5. Click **Upload**
6. Verify the document appears in the list

**Test Smart Web Crawling:**
1. Go to **Knowledge Base** tab
2. Click **"Crawl Website"** button
3. Enter a URL - Archon automatically detects the content type:
   - **Documentation URLs**: `https://docs.python.org/3/tutorial/`
   - **Sitemap URLs**: `https://example.com/sitemap.xml`
   - **Text Files**: `https://raw.githubusercontent.com/user/repo/main/README.txt`
4. Select knowledge type (Technical/Business/General)
5. Add tags for categorization (optional)
6. Click **Start Crawling**
7. Monitor real-time progress with detailed logs
8. View results in the Knowledge Base when complete

**Test Knowledge Chat:**
1. Go to **Chat** tab
2. Ask a question about your uploaded content
3. Verify you get relevant responses

## 🕷️ Smart Crawling Features

Archon includes intelligent web crawling that automatically adapts to different content types:

### Automatic Content Type Detection

| URL Pattern | Crawling Strategy | Description |
|-------------|------------------|-------------|
| `*.xml` or `*sitemap*` | **Sitemap Crawling** | Extracts all URLs from XML sitemap and crawls each page |
| `*.txt` | **Direct Download** | Downloads and processes text files directly |
| Regular URLs | **Recursive Crawling** | Follows internal links up to 3 levels deep |

### Crawling Configuration

- **Max Depth**: 3 levels for recursive webpage crawling
- **Concurrent Sessions**: Up to 10 simultaneous browser sessions
- **Chunk Size**: 5000 characters per knowledge chunk
- **Progress Tracking**: Real-time WebSocket updates with detailed logs

### Best Practices

**For Documentation Sites:**
```
✅ Use the main documentation URL (e.g., https://docs.python.org/3/)
✅ Let Archon recursively discover all pages
✅ Use "technical" knowledge type for code documentation
```

**For Large Sites:**
```
✅ Look for sitemap.xml first (e.g., https://site.com/sitemap.xml)  
✅ Use specific tags to categorize content
✅ Monitor progress via real-time updates
```

**For Text Content:**
```
✅ Direct links to .txt files work automatically
✅ GitHub raw URLs are supported
✅ README files and documentation in text format
```

## 🔧 Advanced Configuration

### RAG Strategy Configuration

Archon supports multiple RAG strategies that can be configured in the Settings:

#### Strategy Options

| Strategy | Description | Best For | Performance Impact |
|----------|-------------|----------|--------------------|
| **Contextual Embeddings** | Enhanced semantic understanding | Technical docs | Slower indexing, better accuracy |
| **Hybrid Search** | Vector + keyword matching | Mixed content types | Slightly slower, comprehensive |
| **Agentic RAG** | Code-aware processing | Developer documentation | Slower crawling, specialized search |
| **Reranking** | Cross-encoder result scoring | Complex queries | +100-200ms latency, better ranking |

#### Recommended Configurations

**For General Documentation:**
```
✅ Hybrid Search
✅ Reranking
❌ Contextual Embeddings
❌ Agentic RAG
```

**For Technical/Code Documentation:**
```
✅ Contextual Embeddings
✅ Hybrid Search
✅ Agentic RAG
✅ Reranking
```

### Docker Configuration

#### Custom Ports

If you need to use different ports, modify your `.env` file:

```bash
# Custom port configuration
FRONTEND_PORT=4000
BACKEND_PORT=9000
MCP_PORT=9051
```

Then restart the services:

```bash
docker-compose down
docker-compose up -d
```

#### Resource Limits

For production or resource-constrained environments, you can modify `docker-compose.yml`:

```yaml
services:
  backend:
    # ... other configuration
    deploy:
      resources:
        limits:
          memory: 2G
          cpus: '1.0'
        reservations:
          memory: 1G
          cpus: '0.5'
```

## 🔍 Troubleshooting

### Common Issues

#### Services Won't Start

**Problem**: `docker-compose up` fails

**Solutions**:
1. Check Docker is running: `docker --version`
2. Verify ports aren't in use: `netstat -tulpn | grep :3737`
3. Check environment variables: `cat .env`
4. View detailed logs: `docker-compose logs backend`

#### Database Connection Issues

**Problem**: "Database connection failed"

**Solutions**:
1. Verify Supabase URL and key in `.env`
2. Check Supabase project is active
3. Ensure SQL scripts were run successfully
4. Test connection manually:
   ```bash
   curl -H "apikey: YOUR_SERVICE_KEY" \
        "https://your-project.supabase.co/rest/v1/credentials"
   ```

#### OpenAI API Issues

**Problem**: "OpenAI API key invalid"

**Solutions**:
1. Verify API key format (starts with `sk-`)
2. Check API key has sufficient credits
3. Test key manually:
   ```bash
   curl -H "Authorization: Bearer YOUR_API_KEY" \
        "https://api.openai.com/v1/models"
   ```

#### Frontend Not Loading

**Problem**: Blank page or connection refused

**Solutions**:
1. Check frontend service: `docker-compose ps frontend`
2. Verify port mapping: `docker-compose logs frontend`
3. Clear browser cache and cookies
4. Try incognito/private browsing mode

### Performance Optimization

#### For Large Knowledge Bases

1. **Increase Database Connection Pool**:
   ```bash
   # Add to .env
   DATABASE_POOL_SIZE=20
   DATABASE_MAX_OVERFLOW=30
   ```

2. **Optimize Vector Index**:
   ```sql
   -- In Supabase SQL Editor
   DROP INDEX IF EXISTS idx_crawled_pages_embedding;
   CREATE INDEX idx_crawled_pages_embedding 
   ON crawled_pages USING ivfflat (embedding vector_cosine_ops) 
   WITH (lists = 1000);  -- Increase for larger datasets
   ```

3. **Enable Query Caching**:
   ```bash
   # Add to .env
   ENABLE_QUERY_CACHE=true
   CACHE_TTL_SECONDS=3600
   ```

## 🎯 Next Steps

Now that Archon is running, explore these features:

1. **[Connect MCP Clients](./mcp-reference)** - Set up Cursor, Windsurf, or Claude Desktop
2. **[Explore the API](./api-reference)** - Integrate with your existing tools
3. **[Set Up Task Management](./tasks)** - Organize your projects and workflows
4. **[Optimize RAG Performance](./rag)** - Fine-tune for your specific use case
5. **[Deploy to Production](./deployment)** - Scale for team or enterprise use

## 📚 Additional Resources

- **[Supabase Documentation](https://supabase.com/docs)**
- **[OpenAI API Documentation](https://platform.openai.com/docs)**
- **[Docker Compose Reference](https://docs.docker.com/compose/)**
- **[Model Context Protocol](https://modelcontextprotocol.io)**

---

**Need help?** Check our [troubleshooting guide](./testing#troubleshooting) or open an issue on GitHub.
