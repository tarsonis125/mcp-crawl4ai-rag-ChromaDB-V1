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
  description text default '',
  docs jsonb default '[]'::jsonb,
  features jsonb default '[]'::jsonb,
  data jsonb default '[]'::jsonb,
  github_repo text,
  pinned boolean default false,
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

-- Document Versions table for version control of project JSONB fields only
-- UPDATED: Task versioning has been removed - only document versioning is supported
create table if not exists document_versions (
  id uuid primary key default gen_random_uuid(),
  project_id uuid references projects(id) on delete cascade,
  task_id uuid references tasks(id) on delete cascade, -- DEPRECATED: No longer used, kept for historical data
  field_name text not null, -- 'docs', 'features', 'data', 'prd' (task fields 'sources', 'code_examples' no longer versioned)
  version_number integer not null,
  content jsonb not null, -- Full snapshot of the field content
  change_summary text, -- Human-readable description of changes
  change_type text default 'update', -- 'create', 'update', 'delete', 'restore', 'backup'
  document_id text, -- For docs array, store the specific document ID
  created_by text default 'system',
  created_at timestamptz default now(),
  -- Ensure we have either project_id OR task_id, not both
  -- NOTE: task_id constraint kept for historical data but new versions only use project_id
  constraint chk_project_or_task check (
    (project_id is not null and task_id is null) or 
    (project_id is null and task_id is not null)
  ),
  -- Unique constraint to prevent duplicate version numbers per field
  unique(project_id, task_id, field_name, version_number)
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
create index if not exists idx_document_versions_project_id on document_versions(project_id);
create index if not exists idx_document_versions_task_id on document_versions(task_id);
create index if not exists idx_document_versions_field_name on document_versions(field_name);
create index if not exists idx_document_versions_version_number on document_versions(version_number);
create index if not exists idx_document_versions_created_at on document_versions(created_at);

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

-- Soft delete functions (keep the core functionality)
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

-- Add comments to document the soft delete fields
COMMENT ON COLUMN tasks.archived IS 'Soft delete flag - TRUE if task is archived/deleted';
COMMENT ON COLUMN tasks.archived_at IS 'Timestamp when task was archived';
COMMENT ON COLUMN tasks.archived_by IS 'User/system that archived the task';

-- Add comments for versioning table
COMMENT ON TABLE document_versions IS 'Version control for JSONB fields in projects only - task versioning has been removed to simplify MCP operations';
COMMENT ON COLUMN document_versions.field_name IS 'Name of JSONB field being versioned (docs, features, data) - task fields and prd removed as unused';
COMMENT ON COLUMN document_versions.content IS 'Full snapshot of field content at this version';
COMMENT ON COLUMN document_versions.change_type IS 'Type of change: create, update, delete, restore, backup';
COMMENT ON COLUMN document_versions.document_id IS 'For docs arrays, the specific document ID that was changed';
COMMENT ON COLUMN document_versions.task_id IS 'DEPRECATED: No longer used for new versions, kept for historical task version data';

-- Enable Row Level Security (RLS) for all tables
-- Projects table
ALTER TABLE projects ENABLE ROW LEVEL SECURITY;

-- Tasks table
ALTER TABLE tasks ENABLE ROW LEVEL SECURITY;

-- Project Sources junction table
ALTER TABLE project_sources ENABLE ROW LEVEL SECURITY;

-- Document Versions table
ALTER TABLE document_versions ENABLE ROW LEVEL SECURITY;

-- Create RLS policies for service role (full access)
CREATE POLICY "Allow service role full access to projects" ON projects
    FOR ALL USING (auth.role() = 'service_role');

CREATE POLICY "Allow service role full access to tasks" ON tasks
    FOR ALL USING (auth.role() = 'service_role');

CREATE POLICY "Allow service role full access to project_sources" ON project_sources
    FOR ALL USING (auth.role() = 'service_role');

CREATE POLICY "Allow service role full access to document_versions" ON document_versions
    FOR ALL USING (auth.role() = 'service_role');

-- Create RLS policies for authenticated users
CREATE POLICY "Allow authenticated users to read and update projects" ON projects
    FOR ALL TO authenticated
    USING (true);

CREATE POLICY "Allow authenticated users to read and update tasks" ON tasks
    FOR ALL TO authenticated
    USING (true);

CREATE POLICY "Allow authenticated users to read and update project_sources" ON project_sources
    FOR ALL TO authenticated
    USING (true);

CREATE POLICY "Allow authenticated users to read document_versions" ON document_versions
    FOR SELECT TO authenticated
    USING (true);

