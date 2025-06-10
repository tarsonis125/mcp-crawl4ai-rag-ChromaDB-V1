-- Migration 005: MCP Client Management System
-- Creates tables for managing multiple MCP client connections

-- MCP Clients table - stores client configurations
CREATE TABLE IF NOT EXISTS mcp_clients (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    name VARCHAR(255) NOT NULL UNIQUE,
    transport_type VARCHAR(50) NOT NULL CHECK (transport_type IN ('sse', 'stdio', 'docker', 'npx')),
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

-- MCP Client Tools table - caches discovered tools from each client
CREATE TABLE IF NOT EXISTS mcp_client_tools (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    client_id UUID NOT NULL REFERENCES mcp_clients(id) ON DELETE CASCADE,
    tool_name VARCHAR(255) NOT NULL,
    tool_description TEXT,
    tool_schema JSONB NOT NULL,
    discovered_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    UNIQUE(client_id, tool_name)
);

-- MCP Client Sessions table - tracks active connections and performance
CREATE TABLE IF NOT EXISTS mcp_client_sessions (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    client_id UUID NOT NULL REFERENCES mcp_clients(id) ON DELETE CASCADE,
    session_start TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    session_end TIMESTAMP WITH TIME ZONE,
    connection_time_ms INTEGER,
    total_tool_calls INTEGER DEFAULT 0,
    successful_calls INTEGER DEFAULT 0,
    failed_calls INTEGER DEFAULT 0,
    avg_response_time_ms DECIMAL(10,2),
    process_id INTEGER,
    memory_usage_mb DECIMAL(10,2),
    cpu_usage_percent DECIMAL(5,2),
    is_active BOOLEAN DEFAULT true
);

-- MCP Client Health Checks table - tracks health monitoring
CREATE TABLE IF NOT EXISTS mcp_client_health_checks (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    client_id UUID NOT NULL REFERENCES mcp_clients(id) ON DELETE CASCADE,
    check_time TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    status VARCHAR(50) NOT NULL CHECK (status IN ('success', 'failure', 'timeout')),
    response_time_ms INTEGER,
    error_message TEXT,
    metadata JSONB
);

-- Indexes for performance
CREATE INDEX IF NOT EXISTS idx_mcp_clients_status ON mcp_clients(status);
CREATE INDEX IF NOT EXISTS idx_mcp_clients_transport_type ON mcp_clients(transport_type);
CREATE INDEX IF NOT EXISTS idx_mcp_clients_auto_connect ON mcp_clients(auto_connect) WHERE auto_connect = true;
CREATE INDEX IF NOT EXISTS idx_mcp_client_tools_client_id ON mcp_client_tools(client_id);
CREATE INDEX IF NOT EXISTS idx_mcp_client_tools_name ON mcp_client_tools(tool_name);
CREATE INDEX IF NOT EXISTS idx_mcp_client_sessions_client_id ON mcp_client_sessions(client_id);
CREATE INDEX IF NOT EXISTS idx_mcp_client_sessions_active ON mcp_client_sessions(client_id) WHERE is_active = true;
CREATE INDEX IF NOT EXISTS idx_mcp_client_health_checks_client_id ON mcp_client_health_checks(client_id);
CREATE INDEX IF NOT EXISTS idx_mcp_client_health_checks_time ON mcp_client_health_checks(check_time);

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
    '{"host": "localhost", "port": 8051, "endpoint": "/sse", "timeout": 30}',
    'disconnected',
    true,
    true
) ON CONFLICT (name) DO NOTHING;

-- Comments for documentation
COMMENT ON TABLE mcp_clients IS 'Registry of MCP client configurations and connection settings';
COMMENT ON TABLE mcp_client_tools IS 'Cache of tools discovered from each MCP client';
COMMENT ON TABLE mcp_client_sessions IS 'Active connection sessions and performance metrics';
COMMENT ON TABLE mcp_client_health_checks IS 'Historical health check results for monitoring';

COMMENT ON COLUMN mcp_clients.connection_config IS 'JSON configuration specific to transport type (host/port for SSE, command/args for stdio, etc.)';
COMMENT ON COLUMN mcp_clients.is_default IS 'Indicates if this is the default Archon MCP server client';
COMMENT ON COLUMN mcp_client_tools.tool_schema IS 'Complete JSON schema for the tool including inputSchema and metadata'; 