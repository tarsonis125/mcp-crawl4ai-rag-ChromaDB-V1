 -- Credentials and Configuration Management Table
-- This table stores both encrypted sensitive data and plain configuration settings

CREATE TABLE IF NOT EXISTS settings (
    id UUID DEFAULT gen_random_uuid() PRIMARY KEY,
    key VARCHAR(255) UNIQUE NOT NULL,
    value TEXT,                    -- For plain text config values
    encrypted_value TEXT,          -- For encrypted sensitive data (bcrypt hashed)
    is_encrypted BOOLEAN DEFAULT FALSE,
    category VARCHAR(100),         -- Group related settings (e.g., 'rag_strategy', 'api_keys', 'server_config')
    description TEXT,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

-- Create index for faster lookups
CREATE INDEX IF NOT EXISTS idx_settings_key ON settings(key);
CREATE INDEX IF NOT EXISTS idx_settings_category ON settings(category);

-- Insert configuration settings from original .env-doc.md
-- Note: Sensitive values like OPENAI_API_KEY will be added via the Settings UI with encryption

-- Server Configuration
INSERT INTO settings (key, value, is_encrypted, category, description) VALUES
('MCP_TRANSPORT', 'dual', false, 'server_config', 'MCP server transport mode - sse (web clients), stdio (IDE clients), or dual (both)'),
('HOST', 'localhost', false, 'server_config', 'Host to bind to if using sse as the transport (leave empty if using stdio)'),
('PORT', '8051', false, 'server_config', 'Port to listen on if using sse as the transport (leave empty if using stdio)'),
('MODEL_CHOICE', 'gpt-4.1-nano', false, 'rag_strategy', 'The LLM you want to use for summaries and contextual embeddings. Generally this is a very cheap and fast LLM like gpt-4.1-nano');

-- RAG Strategy Configuration (all default to true
INSERT INTO settings (key, value, is_encrypted, category, description) VALUES
('USE_CONTEXTUAL_EMBEDDINGS', 'true', true, 'rag_strategy', 'Enhances embeddings with contextual information for better retrieval'),
('CONTEXTUAL_EMBEDDINGS_MAX_WORKERS', '3', false, 'rag_strategy', 'Maximum number of parallel workers for contextual embedding generation (reduces API rate limit pressure)'),
('USE_HYBRID_SEARCH', 'true', true, 'rag_strategy', 'Combines vector similarity search with keyword search for better results'),
('USE_AGENTIC_RAG', 'true', true, 'rag_strategy', 'Enables code example extraction, storage, and specialized code search functionality'),
('USE_RERANKING', 'true', true, 'rag_strategy', 'Applies cross-encoder reranking to improve search result relevance');

-- Monitoring Configuration
INSERT INTO settings (key, value, is_encrypted, category, description) VALUES
('LOGFIRE_ENABLED', 'true', false, 'monitoring', 'Enable or disable Pydantic Logfire logging and observability platform'),
('PROJECTS_ENABLED', 'false', false, 'features', 'Enable or disable Projects and Tasks functionality');

-- Placeholder for sensitive credentials (to be added via Settings UI)
INSERT INTO settings (key, encrypted_value, is_encrypted, category, description) VALUES
('OPENAI_API_KEY', NULL, true, 'api_keys', 'OpenAI API Key for embedding model (text-embedding-3-small). Get from: https://help.openai.com/en/articles/4936850-where-do-i-find-my-openai-api-key');

-- Create trigger to automatically update updated_at timestamp
CREATE OR REPLACE FUNCTION update_updated_at_column()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = NOW();
    RETURN NEW;
END;
$$ language 'plpgsql';

CREATE TRIGGER update_settings_updated_at 
    BEFORE UPDATE ON settings 
    FOR EACH ROW 
    EXECUTE FUNCTION update_updated_at_column();

-- Create RLS (Row Level Security) policies for future security
ALTER TABLE settings ENABLE ROW LEVEL SECURITY;

-- Create policy that allows all operations for service role
CREATE POLICY "Allow service role full access" ON settings
    FOR ALL USING (auth.role() = 'service_role');

-- Create policy for authenticated users (adjust as needed for your security requirements)
CREATE POLICY "Allow authenticated users to read and update" ON settings
    FOR ALL TO authenticated
    USING (true); -- Enable the pgvector extension
create extension if not exists vector;

-- Drop tables if they exist (to allow rerunning the script)
drop table if exists crawled_pages;
drop table if exists code_examples;
drop table if exists sources;

-- Create the sources table
create table sources (
    source_id text primary key,
    summary text,
    total_word_count integer default 0,
    title TEXT,
    metadata JSONB DEFAULT '{}',
    update_frequency integer default 7, -- Frequency in days (1=daily, 7=weekly, 30=monthly, 0=never)
    created_at timestamp with time zone default timezone('utc'::text, now()) not null,
    updated_at timestamp with time zone default timezone('utc'::text, now()) not null
);

-- Create indexes for better query performance on the new columns
CREATE INDEX IF NOT EXISTS idx_sources_title ON sources(title);
CREATE INDEX IF NOT EXISTS idx_sources_metadata ON sources USING GIN(metadata);
CREATE INDEX IF NOT EXISTS idx_sources_update_frequency ON sources(update_frequency);

-- Create index for knowledge_type specifically since it will be commonly queried
CREATE INDEX IF NOT EXISTS idx_sources_knowledge_type ON sources((metadata->>'knowledge_type'));

-- Add comments to document the new columns
COMMENT ON COLUMN sources.title IS 'Descriptive title for the source (e.g., "Pydantic AI API Reference")';
COMMENT ON COLUMN sources.metadata IS 'JSONB field storing knowledge_type, tags, and other metadata';
COMMENT ON COLUMN sources.update_frequency IS 'Update frequency in days: 1=daily, 7=weekly, 30=monthly, 0=never';

-- Create the documentation chunks table
create table crawled_pages (
    id bigserial primary key,
    url varchar not null,
    chunk_number integer not null,
    content text not null,
    metadata jsonb not null default '{}'::jsonb,
    source_id text not null,
    embedding vector(1536),  -- OpenAI embeddings are 1536 dimensions
    created_at timestamp with time zone default timezone('utc'::text, now()) not null,
    
    -- Add a unique constraint to prevent duplicate chunks for the same URL
    unique(url, chunk_number),
    
    -- Add foreign key constraint to sources table
    foreign key (source_id) references sources(source_id)
);

-- Create an index for better vector similarity search performance
create index on crawled_pages using ivfflat (embedding vector_cosine_ops);

-- Create an index on metadata for faster filtering
create index idx_crawled_pages_metadata on crawled_pages using gin (metadata);

-- Create an index on source_id for faster filtering
CREATE INDEX idx_crawled_pages_source_id ON crawled_pages (source_id);

-- Create a function to search for documentation chunks
create or replace function match_crawled_pages (
  query_embedding vector(1536),
  match_count int default 10,
  filter jsonb DEFAULT '{}'::jsonb,
  source_filter text DEFAULT NULL
) returns table (
  id bigint,
  url varchar,
  chunk_number integer,
  content text,
  metadata jsonb,
  source_id text,
  similarity float
)
language plpgsql
as $$
#variable_conflict use_column
begin
  return query
  select
    id,
    url,
    chunk_number,
    content,
    metadata,
    source_id,
    1 - (crawled_pages.embedding <=> query_embedding) as similarity
  from crawled_pages
  where metadata @> filter
    AND (source_filter IS NULL OR source_id = source_filter)
  order by crawled_pages.embedding <=> query_embedding
  limit match_count;
end;
$$;

-- Enable RLS on the crawled_pages table
alter table crawled_pages enable row level security;

-- Create a policy that allows anyone to read crawled_pages
create policy "Allow public read access to crawled_pages"
  on crawled_pages
  for select
  to public
  using (true);

-- Enable RLS on the sources table
alter table sources enable row level security;

-- Create a policy that allows anyone to read sources
create policy "Allow public read access to sources"
  on sources
  for select
  to public
  using (true);

-- Create the code_examples table
create table code_examples (
    id bigserial primary key,
    url varchar not null,
    chunk_number integer not null,
    content text not null,  -- The code example content
    summary text not null,  -- Summary of the code example
    metadata jsonb not null default '{}'::jsonb,
    source_id text not null,
    embedding vector(1536),  -- OpenAI embeddings are 1536 dimensions
    created_at timestamp with time zone default timezone('utc'::text, now()) not null,
    
    -- Add a unique constraint to prevent duplicate chunks for the same URL
    unique(url, chunk_number),
    
    -- Add foreign key constraint to sources table
    foreign key (source_id) references sources(source_id)
);

-- Create an index for better vector similarity search performance
create index on code_examples using ivfflat (embedding vector_cosine_ops);

-- Create an index on metadata for faster filtering
create index idx_code_examples_metadata on code_examples using gin (metadata);

-- Create an index on source_id for faster filtering
CREATE INDEX idx_code_examples_source_id ON code_examples (source_id);

-- Create a function to search for code examples
create or replace function match_code_examples (
  query_embedding vector(1536),
  match_count int default 10,
  filter jsonb DEFAULT '{}'::jsonb,
  source_filter text DEFAULT NULL
) returns table (
  id bigint,
  url varchar,
  chunk_number integer,
  content text,
  summary text,
  metadata jsonb,
  source_id text,
  similarity float
)
language plpgsql
as $$
#variable_conflict use_column
begin
  return query
  select
    id,
    url,
    chunk_number,
    content,
    summary,
    metadata,
    source_id,
    1 - (code_examples.embedding <=> query_embedding) as similarity
  from code_examples
  where metadata @> filter
    AND (source_filter IS NULL OR source_id = source_filter)
  order by code_examples.embedding <=> query_embedding
  limit match_count;
end;
$$;

-- Enable RLS on the code_examples table
alter table code_examples enable row level security;

-- Create a policy that allows anyone to read code_examples
create policy "Allow public read access to code_examples"
  on code_examples
  for select
  to public
  using (true);