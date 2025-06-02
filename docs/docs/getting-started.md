# Getting Started

Welcome to **Crawl4AI RAG**, an advanced Retrieval-Augmented Generation (RAG) system with Modular Control Plane (MCP) integration.

## Prerequisites

- Git >= 2.25.0
- Docker & Docker Compose >= 1.27.0
- Node.js >= 18.x
- Python 3.10+

## Clone the Repository

```bash
git clone https://github.com/your-org/mcp-crawl4ai-rag.git
cd mcp-crawl4ai-rag
git checkout feature/docusauraus
```

## Project Structure

```bash
tree -L 2 .
```

```text
.
├── src/                   # Python server source code
├── archon-ui-main/        # React frontend source
├── docs/                  # Docusaurus documentation
│   └── docs/              # Markdown content
├── docker-compose.yml     # Local development services
└── Dockerfile             # Server Dockerfile
```

## Environment Variables

| Variable                  | Description                                   | Default                   |
|---------------------------|-----------------------------------------------|---------------------------|
| SUPABASE_URL              | Supabase API endpoint                         | –                         |
| SUPABASE_SERVICE_KEY      | Supabase service role key                     | –                         |
| HOST                      | Backend host                                  | `localhost`               |
| PORT                      | Backend port                                  | `8051`                    |
| VITE_API_URL              | Frontend API URL                              | `http://localhost:8080`   |

## Running Locally

Start backend, frontend, and docs:

```bash
docker-compose up --build
```

Access:

- Backend API: `http://localhost:8080`
- Frontend UI: `http://localhost:3737`
- Docs site : `http://localhost:3838`

## Architecture Diagram

```mermaid
graph LR
  A[Browser] --> B(React UI)
  B --> C[Backend API]
  C --> D[MCP Controller]
  C --> E[Vector Store]
  E --> F[OpenAI]
```
