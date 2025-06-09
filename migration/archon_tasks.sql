-- UUID helper
create extension if not exists "pgcrypto";

-- Task status enumeration
-- Drop existing enum if present
DROP TYPE IF EXISTS task_status;
-- Create task_status enum
CREATE TYPE task_status AS ENUM ('todo','doing','review','done');

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
  archived boolean default false,
  archived_at timestamptz null,
  archived_by text null,
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
create index if not exists idx_tasks_archived on tasks(archived);
create index if not exists idx_tasks_archived_at on tasks(archived_at);
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

-- Soft delete functions
CREATE OR REPLACE FUNCTION archive_task(
    task_id_param UUID,
    archived_by_param TEXT DEFAULT 'system'
) 
RETURNS BOOLEAN AS $$
DECLARE
    task_exists BOOLEAN;
BEGIN
    -- Check if task exists and is not already archived
    SELECT EXISTS(
        SELECT 1 FROM tasks 
        WHERE id = task_id_param AND archived = FALSE
    ) INTO task_exists;
    
    IF NOT task_exists THEN
        RETURN FALSE;
    END IF;
    
    -- Archive the task
    UPDATE tasks 
    SET 
        archived = TRUE,
        archived_at = NOW(),
        archived_by = archived_by_param,
        updated_at = NOW()
    WHERE id = task_id_param;
    
    -- Also archive all subtasks
    UPDATE tasks 
    SET 
        archived = TRUE,
        archived_at = NOW(), 
        archived_by = archived_by_param,
        updated_at = NOW()
    WHERE parent_task_id = task_id_param AND archived = FALSE;
    
    RETURN TRUE;
END;
$$ LANGUAGE plpgsql;

CREATE OR REPLACE FUNCTION restore_task(task_id_param UUID)
RETURNS BOOLEAN AS $$
DECLARE
    task_exists BOOLEAN;
BEGIN
    -- Check if task exists and is archived
    SELECT EXISTS(
        SELECT 1 FROM tasks 
        WHERE id = task_id_param AND archived = TRUE
    ) INTO task_exists;
    
    IF NOT task_exists THEN
        RETURN FALSE;
    END IF;
    
    -- Restore the task
    UPDATE tasks 
    SET 
        archived = FALSE,
        archived_at = NULL,
        archived_by = NULL,
        updated_at = NOW()
    WHERE id = task_id_param;
    
    RETURN TRUE;
END;
$$ LANGUAGE plpgsql;

-- Create views for active and archived tasks
CREATE OR REPLACE VIEW active_tasks AS
SELECT * FROM tasks WHERE archived = FALSE;

CREATE OR REPLACE VIEW archived_tasks AS
SELECT * FROM tasks WHERE archived = TRUE;

-- Add comments to document the new fields
COMMENT ON COLUMN tasks.archived IS 'Soft delete flag - TRUE if task is archived/deleted';
COMMENT ON COLUMN tasks.archived_at IS 'Timestamp when task was archived';
COMMENT ON COLUMN tasks.archived_by IS 'User/system that archived the task';
