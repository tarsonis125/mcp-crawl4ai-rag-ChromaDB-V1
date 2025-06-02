-- UUID helper
create extension if not exists "pgcrypto";

-- Task status enumeration
-- Drop existing enum if present
DROP TYPE IF EXISTS task_status;
-- Create task_status enum
CREATE TYPE task_status AS ENUM ('todo','doing','blocked','done');

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
  sources jsonb default '[]'::jsonb,
  code_examples jsonb default '[]'::jsonb,
  created_at timestamptz default now(),
  updated_at timestamptz default now()
);
