-- Migration 005: MCP Client Management System
-- Creates table for managing MCP client connections (SSE-only)

-- MCP Clients table - stores client configurations
CREATE TABLE IF NOT EXISTS mcp_clients (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    name VARCHAR(255) NOT NULL UNIQUE,
    transport_type VARCHAR(50) NOT NULL DEFAULT 'sse' CHECK (transport_type = 'sse'),
    connection_config JSONB NOT NULL,
    status VARCHAR(50) DEFAULT 'disconnected' CHECK (status IN ('connected', 'disconnected', 'connecting', 'error')),
    auto_connect BOOLEAN DEFAULT true,
    health_check_interval INTEGER DEFAULT 30,
    last_seen TIMESTAMP WITH TIME ZONE,
    last_error TEXT,
    is_default BOOLEAN DEFAULT false,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

-- Indexes for performance
CREATE INDEX IF NOT EXISTS idx_mcp_clients_status ON mcp_clients(status);
CREATE INDEX IF NOT EXISTS idx_mcp_clients_auto_connect ON mcp_clients(auto_connect) WHERE auto_connect = true;

-- Trigger to update updated_at timestamp
CREATE OR REPLACE FUNCTION update_updated_at_column()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = NOW();
    RETURN NEW;
END;
$$ language 'plpgsql';

CREATE TRIGGER update_mcp_clients_updated_at 
    BEFORE UPDATE ON mcp_clients 
    FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();

-- Update any existing clients to use SSE with Docker-compatible URL
-- Note: host.docker.internal is used when the backend runs in Docker and needs to access
-- services on the host machine. For production deployments, use actual hostnames/IPs.
UPDATE mcp_clients 
SET transport_type = 'sse',
    connection_config = '{"url": "http://host.docker.internal:8051/sse"}'
WHERE transport_type != 'sse';

-- Insert default Archon client if not exists
INSERT INTO mcp_clients (
    name, 
    transport_type, 
    connection_config, 
    status, 
    auto_connect, 
    is_default
) VALUES (
    'Archon (Default)',
    'sse',
    '{"url": "http://host.docker.internal:8051/sse"}',
    'disconnected',
    true,
    true
) ON CONFLICT (name) DO UPDATE SET
    transport_type = 'sse',
    connection_config = '{"url": "http://host.docker.internal:8051/sse"}';

-- Comments for documentation
COMMENT ON TABLE mcp_clients IS 'Registry of MCP client configurations using SSE (Streamable HTTP) transport';
COMMENT ON COLUMN mcp_clients.connection_config IS 'JSON configuration containing the SSE endpoint URL';
COMMENT ON COLUMN mcp_clients.is_default IS 'Indicates if this is the default Archon MCP server client';

-- Enable Row Level Security (RLS)
ALTER TABLE mcp_clients ENABLE ROW LEVEL SECURITY;

-- Create RLS policies for service role (full access)
CREATE POLICY "Allow service role full access to mcp_clients" ON mcp_clients
    FOR ALL USING (auth.role() = 'service_role');

-- Create RLS policies for authenticated users
CREATE POLICY "Allow authenticated users to manage mcp_clients" ON mcp_clients
    FOR ALL TO authenticated
    USING (true);