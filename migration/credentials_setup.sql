-- Credentials and Configuration Management Table
-- This table stores both encrypted sensitive data and plain configuration settings

CREATE TABLE IF NOT EXISTS app_credentials (
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
CREATE INDEX IF NOT EXISTS idx_app_credentials_key ON app_credentials(key);
CREATE INDEX IF NOT EXISTS idx_app_credentials_category ON app_credentials(category);

-- Insert configuration settings from original .env-doc.md
-- Note: Sensitive values like OPENAI_API_KEY will be added via the Settings UI with encryption

-- Server Configuration
INSERT INTO app_credentials (key, value, is_encrypted, category, description) VALUES
('TRANSPORT', 'sse', false, 'server_config', 'The transport for the MCP server - either ''sse'' or ''stdio'' (defaults to sse if left empty)'),
('HOST', 'localhost', false, 'server_config', 'Host to bind to if using sse as the transport (leave empty if using stdio)'),
('PORT', '8051', false, 'server_config', 'Port to listen on if using sse as the transport (leave empty if using stdio)'),
('MODEL_CHOICE', 'gpt-4o-mini', false, 'llm_config', 'The LLM you want to use for summaries and contextual embeddings. Generally this is a very cheap and fast LLM like gpt-4o-mini');

-- RAG Strategy Configuration (all default to false)
INSERT INTO app_credentials (key, value, is_encrypted, category, description) VALUES
('USE_CONTEXTUAL_EMBEDDINGS', 'false', false, 'rag_strategy', 'Enhances embeddings with contextual information for better retrieval'),
('USE_HYBRID_SEARCH', 'false', false, 'rag_strategy', 'Combines vector similarity search with keyword search for better results'),
('USE_AGENTIC_RAG', 'false', false, 'rag_strategy', 'Enables code example extraction, storage, and specialized code search functionality'),
('USE_RERANKING', 'false', false, 'rag_strategy', 'Applies cross-encoder reranking to improve search result relevance');

-- Placeholder for sensitive credentials (to be added via Settings UI)
INSERT INTO app_credentials (key, encrypted_value, is_encrypted, category, description) VALUES
('OPENAI_API_KEY', NULL, true, 'api_keys', 'OpenAI API Key for embedding model (text-embedding-3-small). Get from: https://help.openai.com/en/articles/4936850-where-do-i-find-my-openai-api-key');

-- Create trigger to automatically update updated_at timestamp
CREATE OR REPLACE FUNCTION update_updated_at_column()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = NOW();
    RETURN NEW;
END;
$$ language 'plpgsql';

CREATE TRIGGER update_app_credentials_updated_at 
    BEFORE UPDATE ON app_credentials 
    FOR EACH ROW 
    EXECUTE FUNCTION update_updated_at_column();

-- Create RLS (Row Level Security) policies for future security
ALTER TABLE app_credentials ENABLE ROW LEVEL SECURITY;

-- Create policy that allows all operations for service role
CREATE POLICY "Allow service role full access" ON app_credentials
    FOR ALL USING (auth.role() = 'service_role');

-- Create policy for authenticated users (adjust as needed for your security requirements)
CREATE POLICY "Allow authenticated users to read and update" ON app_credentials
    FOR ALL TO authenticated
    USING (true); 