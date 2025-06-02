# Archon — Project & Task Management Layer  
_A plug‑and‑play planning stack for your existing MCP‑RAG FastAPI server_

---

## 0 . Quick mental map  

```mermaid
graph TD
    subgraph Postgres(Supabase)
        projects_table((projects))
        tasks_table((tasks))
    end

    subgraph FastAPI
        ProjectsRouter
        TasksRouter
    end

    subgraph MCP Tools
        project_lookup
        task_lookup
        create_task
        update_task
    end

    projects_table --> ProjectsRouter
    tasks_table --> TasksRouter
    ProjectsRouter --> project_lookup
    TasksRouter --> task_lookup
    TasksRouter --> create_task
    TasksRouter --> update_task
```

---

## 1 . Database schema  

Save the block below as **`supabase_archon.sql`** and run it in the Supabase SQL editor (or via `supabase db reset`).

```sql
-- UUID helper (optional if your Supabase project already has it)
create extension if not exists "pgcrypto";

------------------------------------------------------------------
-- 1. Enumerations
------------------------------------------------------------------
create type task_status as enum ('todo','doing','blocked','done');

------------------------------------------------------------------
-- 2. Tables
------------------------------------------------------------------

-- Projects
create table if not exists projects (
  id                uuid primary key default gen_random_uuid(),
  title             text not null,
  prd               jsonb default '{}'::jsonb,           -- full PRD
  docs              jsonb default '[]'::jsonb,           -- misc reference docs
  features          jsonb default '[]'::jsonb,           -- feature list
  data              jsonb default '[]'::jsonb,           -- any sample datasets
  github_repo       text,                                -- git clone url
  created_at        timestamptz default now(),
  updated_at        timestamptz default now()
);

-- Tasks
create table if not exists tasks (
  id                uuid primary key default gen_random_uuid(),
  project_id        uuid not null references projects(id) on delete cascade,
  parent_task_id    uuid references tasks(id) on delete cascade,
  title             text not null,
  description       text,
  sources           jsonb default '[]'::jsonb,           -- reference docs
  code_examples     jsonb default '[]'::jsonb,           -- code snippets / gists
  status            task_status default 'todo',
  created_at        timestamptz default now(),
  updated_at        timestamptz default now()
);

-- Breath‑easy index helpers
create index if not exists idx_tasks_project on tasks(project_id);
create index if not exists idx_tasks_parent  on tasks(parent_task_id);
```

---

## 2 . Python data layer (SQLModel ≅ Pydantic + SQLAlchemy)  

Install deps:

```bash
pip install sqlmodel psycopg[binary] asyncpg
```

`models.py`

```python
from datetime import datetime
from enum import Enum
from typing import List, Optional
from sqlmodel import Field, JSON, Relationship, SQLModel

class TaskStatus(str, Enum):
    todo = "todo"
    doing = "doing"
    blocked = "blocked"
    done = "done"

class Project(SQLModel, table=True):
    __tablename__ = "projects"

    id: Optional[str] = Field(default=None, primary_key=True, index=True)
    title: str
    prd: dict = Field(sa_column=JSON, default_factory=dict)
    docs: List[dict] = Field(sa_column=JSON, default_factory=list)
    features: List[dict] = Field(sa_column=JSON, default_factory=list)
    data: List[dict] = Field(sa_column=JSON, default_factory=list)
    github_repo: Optional[str] = None
    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: datetime = Field(default_factory=datetime.utcnow)

    tasks: list["Task"] = Relationship(back_populates="project")

class Task(SQLModel, table=True):
    __tablename__ = "tasks"

    id: Optional[str] = Field(default=None, primary_key=True, index=True)
    project_id: str = Field(foreign_key="projects.id")
    parent_task_id: Optional[str] = Field(foreign_key="tasks.id")
    title: str
    description: Optional[str] = None
    sources: List[dict] = Field(sa_column=JSON, default_factory=list)
    code_examples: List[dict] = Field(sa_column=JSON, default_factory=list)
    status: TaskStatus = Field(default=TaskStatus.todo)
    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: datetime = Field(default_factory=datetime.utcnow)

    project: Project = Relationship(back_populates="tasks")
```

---

## 3 . FastAPI routers  

### `database.py` – (async engine + session)

```python
from sqlmodel import SQLModel, create_engine
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine
from sqlalchemy.orm import sessionmaker
import os

DATABASE_URL = os.environ["SUPABASE_DB_URL"].replace("postgres://", "postgresql+asyncpg://")
engine = create_async_engine(DATABASE_URL, echo=False)
async_session = sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)

async def init_db():
    async with engine.begin() as conn:
        await conn.run_sync(SQLModel.metadata.create_all)
```

### `routers/projects.py`

```python
from fastapi import APIRouter, Depends, HTTPException
from sqlmodel import select
from ..database import async_session
from ..models import Project

router = APIRouter(prefix="/projects", tags=["Projects"])

async def get_session():
    async with async_session() as session:
        yield session

@router.post("", response_model=Project)
async def create_project(project: Project, session=Depends(get_session)):
    session.add(project)
    await session.commit()
    await session.refresh(project)
    return project

@router.get("/{project_id}", response_model=Project)
async def get_project(project_id: str, session=Depends(get_session)):
    proj = await session.get(Project, project_id)
    if not proj:
        raise HTTPException(404)
    return proj
```

### `routers/tasks.py`

```python
from fastapi import APIRouter, Depends, HTTPException
from sqlmodel import select
from ..database import async_session
from ..models import Task, TaskStatus

router = APIRouter(prefix="/tasks", tags=["Tasks"])

async def get_session():
    async with async_session() as session:
        yield session

@router.post("", response_model=Task)
async def create_task(task: Task, session=Depends(get_session)):
    session.add(task)
    await session.commit()
    await session.refresh(task)
    return task

@router.get("/by_project/{project_id}", response_model=list[Task])
async def list_tasks(project_id: str, session=Depends(get_session)):
    tasks = (await session.exec(select(Task).where(Task.project_id == project_id))).all()
    return tasks

@router.patch("/{task_id}/status", response_model=Task)
async def update_status(task_id: str, status: TaskStatus, session=Depends(get_session)):
    task = await session.get(Task, task_id)
    if not task:
        raise HTTPException(404)
    task.status = status
    await session.commit()
    await session.refresh(task)
    return task
```

### Plug routers into main `app.py`

```python
from fastapi import FastAPI
from .routers import projects, tasks
from .database import init_db

app = FastAPI(title="Archon API")

app.include_router(projects.router)
app.include_router(tasks.router)

@app.on_event("startup")
async def on_start():
    await init_db()
```

---

## 4 . MCP tool definitions  

Your existing MCP runtime expects a “tools” manifest.  Place this near your RAG tools and load it at boot.

```python
# mcp_tools/project_management.py
from typing import Annotated, List
from pydantic import BaseModel, Field

class ProjectLookup(BaseModel):
    """Retrieve a project and its metadata."""
    project_id: str = Field(..., description="UUID of the project")

class TaskLookup(BaseModel):
    """Retrieve a single task."""
    task_id: str

class CreateTask(BaseModel):
    """Create a new task under a project."""
    project_id: str
    title: str
    description: str | None = None
    parent_task_id: str | None = None
    sources: list[dict] | None = None
    code_examples: list[dict] | None = None

class UpdateTaskStatus(BaseModel):
    """Update a task’s status."""
    task_id: str
    status: str = Field(..., enum=["todo","doing","blocked","done"])

TOOL_REGISTRY = {
    "project_lookup": {"schema": ProjectLookup, "endpoint": "/projects/{project_id}"},
    "task_lookup": {"schema": TaskLookup, "endpoint": "/tasks/{task_id}"},
    "create_task": {"schema": CreateTask, "endpoint": "/tasks"},
    "update_task": {"schema": UpdateTaskStatus, "endpoint": "/tasks/{task_id}/status"},
}
```

> **Tip:**  When your IDE agent (Cursor, etc.) starts, attach `TOOL_REGISTRY` so the LLM can autonomously plan, create, and check off tasks.

---

## 5 . Minimal React fetch example  

```ts
// src/api.ts
export async function listTasks(projectId: string) {
  const res = await fetch(`/api/tasks/by_project/${projectId}`);
  return res.json();
}

export async function updateTaskStatus(taskId: string, status: string) {
  await fetch(`/api/tasks/${taskId}/status?status=${status}`, {
    method: "PATCH",
  });
}
```

---

## 6 . Next steps  

1. **Run SQL** → create tables/enums in Supabase.  
2. **Export `SUPABASE_DB_URL`** → point FastAPI to the same DB.  
3. **`uvicorn app:app --reload`** → verify `/docs` shows the new endpoints.  
4. **Wire React UI** → call the endpoints; show tasks by status column.  
5. **Register `TOOL_REGISTRY`** → allow Claude/OpenAI agents to query and mutate tasks as part of their workflow.

That’s the entire plumbing—everything else is front‑end flair and prompt‑crafting! 🚀
