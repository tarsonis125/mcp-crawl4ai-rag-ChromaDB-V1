-- UUID helper
create extension if not exists "pgcrypto";

-- Task status enumeration
-- Drop existing enum if present
DROP TYPE IF EXISTS task_status;
-- Create task_status enum
CREATE TYPE task_status AS ENUM ('todo','doing','blocked','done');

-- Assignee enumeration
-- Drop existing enum if present
DROP TYPE IF EXISTS task_assignee;
-- Create task_assignee enum
CREATE TYPE task_assignee AS ENUM ('User','Archon','AI IDE Agent');

-- Projects table
create table if not exists projects (
  id uuid primary key default gen_random_uuid(),
  title text not null,
  prd jsonb default '{}'::jsonb,
  docs jsonb default '[]'::jsonb,
  features jsonb default '[]'::jsonb,
  data jsonb default '[]'::jsonb,
  github_repo text,
  created_at timestamptz default now(),
  updated_at timestamptz default now()
);

-- Tasks table
create table if not exists tasks (
  id uuid primary key default gen_random_uuid(),
  project_id uuid references projects(id) on delete cascade,
  parent_task_id uuid references tasks(id) on delete cascade,
  title text not null,
  description text default '',
  status task_status default 'todo',
  assignee task_assignee default 'User',
  task_order integer default 0,
  feature text,
  sources jsonb default '[]'::jsonb,
  code_examples jsonb default '[]'::jsonb,
  created_at timestamptz default now(),
  updated_at timestamptz default now()
);

-- Project Sources junction table for many-to-many relationship
create table if not exists project_sources (
  id uuid primary key default gen_random_uuid(),
  project_id uuid references projects(id) on delete cascade,
  source_id text not null, -- References sources in the knowledge base
  linked_at timestamptz default now(),
  created_by text default 'system',
  notes text,
  -- Unique constraint to prevent duplicate links
  unique(project_id, source_id)
);

-- Create indexes for better performance
create index if not exists idx_tasks_project_id on tasks(project_id);
create index if not exists idx_tasks_status on tasks(status);
create index if not exists idx_tasks_assignee on tasks(assignee);
create index if not exists idx_tasks_order on tasks(task_order);
create index if not exists idx_project_sources_project_id on project_sources(project_id);
create index if not exists idx_project_sources_source_id on project_sources(source_id);

-- Add trigger to automatically update updated_at timestamp
CREATE OR REPLACE FUNCTION update_updated_at_column()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = now();
    RETURN NEW;
END;
$$ language 'plpgsql';

-- Apply triggers to tables
DROP TRIGGER IF EXISTS update_projects_updated_at ON projects;
CREATE TRIGGER update_projects_updated_at 
    BEFORE UPDATE ON projects 
    FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();

DROP TRIGGER IF EXISTS update_tasks_updated_at ON tasks;
CREATE TRIGGER update_tasks_updated_at 
    BEFORE UPDATE ON tasks 
    FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();
