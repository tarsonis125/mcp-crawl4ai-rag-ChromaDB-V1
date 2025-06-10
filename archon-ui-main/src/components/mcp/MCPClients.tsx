import React, { useState, memo, useEffect } from 'react';
import { Plus } from 'lucide-react';
import { ClientCard } from './ClientCard';
import { ToolTestingPanel } from './ToolTestingPanel';
import { Button } from '../ui/Button';
import { mcpService, MCPClient, MCPClientConfig } from '../../services/mcpService';

// Client interface (keeping for backward compatibility)
export interface Client {
  id: string;
  name: string;
  status: 'online' | 'offline' | 'error';
  ip: string;
  lastSeen: string;
  version: string;
  tools: Tool[];
  cpuUsage?: number;
  memoryUsage?: number;
  region?: string;
  isArchon?: boolean;
}

// Tool interface
export interface Tool {
  id: string;
  name: string;
  description: string;
  parameters: ToolParameter[];
}

// Tool parameter interface
export interface ToolParameter {
  name: string;
  type: 'string' | 'number' | 'boolean' | 'array';
  required: boolean;
  description?: string;
}

export const MCPClients = () => {
  const [clients, setClients] = useState<Client[]>([]);
  const [isLoading, setIsLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  
  // State for selected client and panel visibility
  const [selectedClient, setSelectedClient] = useState<Client | null>(null);
  const [isPanelOpen, setIsPanelOpen] = useState(false);
  const [isAddClientModalOpen, setIsAddClientModalOpen] = useState(false);

  // Load clients when component mounts
  useEffect(() => {
    loadAllClients();
  }, []);

  /**
   * Load all clients: Archon (hardcoded) + real database clients
   */
  const loadAllClients = async () => {
    try {
      setIsLoading(true);
      setError(null);

      // Start with the Archon client (hardcoded as it represents our server)
      const archonClient: Client = {
        id: 'archon-default',
        name: 'Archon MCP Server',
        status: 'offline',
        ip: 'localhost:8051',
        lastSeen: 'Never',
        version: 'v2.0.0',
        cpuUsage: 12,
        memoryUsage: 34,
        region: 'local',
        isArchon: true,
        tools: []
      };

      // Load real tools for Archon client
      await loadArchonTools(archonClient);

      // Load real clients from database
      const dbClients = await mcpService.getClients();
      
      // Convert database clients to our Client interface
      const convertedClients: Client[] = dbClients
        .filter(client => !client.is_default) // Exclude default client (Archon)
        .map(dbClient => convertDbClientToClient(dbClient));

      // Set all clients: Archon first, then database clients
      setClients([archonClient, ...convertedClients]);
    } catch (error) {
      console.error('Failed to load MCP clients:', error);
      setError(error instanceof Error ? error.message : 'Failed to load clients');
      
      // Still show Archon client even if database fails
      const archonClient: Client = {
        id: 'archon-default',
        name: 'Archon MCP Server',
        status: 'error',
        ip: 'localhost:8051',
        lastSeen: 'Error loading',
        version: 'v2.0.0',
        isArchon: true,
        tools: []
      };
      setClients([archonClient]);
    } finally {
      setIsLoading(false);
    }
  };

  /**
   * Convert database MCP client to our Client interface
   */
  const convertDbClientToClient = (dbClient: MCPClient): Client => {
    // Map database status to our status types
    const statusMap: Record<string, 'online' | 'offline' | 'error'> = {
      'connected': 'online',
      'disconnected': 'offline',
      'connecting': 'offline', 
      'error': 'error'
    };

    // Extract connection info
    const config = dbClient.connection_config;
    const ip = config.host && config.port ? `${config.host}:${config.port}` : 
               config.command ? config.command : 'N/A';

    return {
      id: dbClient.id,
      name: dbClient.name,
      status: statusMap[dbClient.status] || 'offline',
      ip,
      lastSeen: dbClient.last_seen ? new Date(dbClient.last_seen).toLocaleString() : 'Never',
      version: config.version || 'Unknown',
      region: config.region || 'Unknown',
      isArchon: false,
      tools: [] // Will be loaded separately if needed
    };
  };

  /**
   * Load real tools from the MCP server for the Archon client
   */
  const loadArchonTools = async (archonClient: Client) => {
    try {
      // Get current server status first
      const status = await mcpService.getStatus();
      
      if (status.status === 'running') {
        // Load real tools from MCP server
        const mcpTools = await mcpService.getAvailableTools();
        
        // Convert MCP tools to our Tool interface format
        const convertedTools: Tool[] = mcpTools.map((mcpTool, index) => {
          const parameters: ToolParameter[] = [];
          
          // Extract parameters from MCP inputSchema
          if (mcpTool.inputSchema?.properties) {
            const required = mcpTool.inputSchema.required || [];
            Object.entries(mcpTool.inputSchema.properties).forEach(([name, schema]: [string, any]) => {
              parameters.push({
                name,
                type: schema.type === 'integer' ? 'number' : schema.type || 'string',
                required: required.includes(name),
                description: schema.description || ''
              });
            });
          }
          
          return {
            id: `archon-${index}`,
            name: mcpTool.name,
            description: mcpTool.description || 'No description available',
            parameters
          };
        });

        // Update the Archon client with real tools and status
        archonClient.tools = convertedTools;
        archonClient.status = 'online';
        archonClient.lastSeen = 'Just now';
      } else {
        // Server not running
        archonClient.status = 'offline';
        archonClient.lastSeen = 'MCP server offline';
        archonClient.tools = [];
      }
    } catch (error) {
      console.error('Failed to load Archon MCP tools:', error);
      archonClient.status = 'error';
      archonClient.lastSeen = 'Connection error';
      archonClient.tools = [];
    }
  };

  /**
   * Handle adding a new client
   */
  const handleAddClient = async (clientConfig: MCPClientConfig) => {
    try {
      // Create client in database
      const newClient = await mcpService.createClient(clientConfig);
      
      // Convert and add to local state
      const convertedClient = convertDbClientToClient(newClient);
      setClients(prev => [...prev, convertedClient]);
      
      // Close modal
      setIsAddClientModalOpen(false);
      
      // Show success message (you might want to add a toast here)
      console.log('Client added successfully:', newClient.name);
    } catch (error) {
      console.error('Failed to add client:', error);
      setError(error instanceof Error ? error.message : 'Failed to add client');
    }
  };

  // Handle client selection
  const handleSelectClient = (client: Client) => {
    setSelectedClient(client);
    setIsPanelOpen(true);
  };

  if (isLoading) {
    return (
      <div className="relative min-h-[80vh] flex items-center justify-center">
        <div className="text-center">
          <div className="animate-spin rounded-full h-8 w-8 border-b-2 border-cyan-400 mx-auto mb-4"></div>
          <p className="text-gray-600 dark:text-gray-400">Loading MCP clients...</p>
        </div>
      </div>
    );
  }

  return (
    <div className="relative min-h-[80vh]">
      {/* Background grid effect */}
      <div className="absolute inset-0 pointer-events-none bg-[linear-gradient(to_right,rgba(59,130,246,0.03)_1px,transparent_1px),linear-gradient(to_bottom,rgba(59,130,246,0.03)_1px,transparent_1px)] bg-[size:20px_20px]"></div>
      
      {/* Container with max-width to match panel */}
      <div className="max-w-[1400px] mx-auto px-6">
        {/* Header with Add Client button */}
        <div className="flex justify-between items-center mb-8 relative z-10">
          <h2 className="text-xl font-semibold text-gray-800 dark:text-white flex items-center">
            <span className="w-2 h-2 rounded-full bg-cyan-400 mr-2 shadow-[0_0_8px_rgba(34,211,238,0.6)]"></span>
            MCP Clients
            <span className="ml-3 text-sm text-gray-500 dark:text-gray-400 font-normal">
              {clients.filter(c => c.status === 'online').length} online /{' '}
              {clients.length} total
            </span>
          </h2>
          
          {/* Add Client button - styled like the Knowledge button in screenshot */}
          <button 
            onClick={() => setIsAddClientModalOpen(true)} 
            className="flex items-center gap-2 px-4 py-2 rounded-full bg-gradient-to-r from-cyan-500/80 to-blue-600/80 text-white border border-cyan-400/50 shadow-[0_0_15px_rgba(34,211,238,0.4)] hover:shadow-[0_0_20px_rgba(34,211,238,0.6)] transition-all duration-300"
          >
            <Plus className="w-5 h-5" />
            <span className="font-medium">Add Client</span>
          </button>
        </div>

        {/* Error message */}
        {error && (
          <div className="mb-6 p-4 bg-red-500/10 border border-red-500/20 rounded-lg">
            <p className="text-red-600 dark:text-red-400">{error}</p>
          </div>
        )}
        
        {/* Client Cards Grid - updated for 3 columns on medium */}
        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-6 relative z-10">
          {clients.map(client => (
            <ClientCard 
              key={client.id} 
              client={client} 
              onSelect={() => handleSelectClient(client)} 
            />
          ))}
        </div>
      </div>
      
      {/* Tool Testing Panel */}
      <ToolTestingPanel 
        client={selectedClient} 
        isOpen={isPanelOpen} 
        onClose={() => setIsPanelOpen(false)} 
      />
      
      {/* Add Client Modal */}
      {isAddClientModalOpen && (
        <AddClientModal 
          isOpen={isAddClientModalOpen}
          onClose={() => setIsAddClientModalOpen(false)}
          onSubmit={handleAddClient}
        />
      )}
    </div>
  );
};

// Add Client Modal Component
interface AddClientModalProps {
  isOpen: boolean;
  onClose: () => void;
  onSubmit: (config: MCPClientConfig) => Promise<void>;
}

const AddClientModal: React.FC<AddClientModalProps> = ({ isOpen, onClose, onSubmit }) => {
  const [formData, setFormData] = useState({
    name: '',
    transport_type: 'sse' as 'sse' | 'stdio' | 'docker' | 'npx',
    host: '',
    port: '',
    command: '',
    package: '',
    auto_connect: true
  });
  const [isSubmitting, setIsSubmitting] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    
    if (!formData.name.trim()) {
      setError('Client name is required');
      return;
    }

    setIsSubmitting(true);
    setError(null);

    try {
      // Build connection config based on transport type
      let connection_config: Record<string, any> = {};
      
      switch (formData.transport_type) {
        case 'sse':
          if (!formData.host || !formData.port) {
            setError('Host and port are required for SSE transport');
            return;
          }
          connection_config = {
            host: formData.host,
            port: parseInt(formData.port),
            endpoint: '/sse'
          };
          break;
        case 'stdio':
          if (!formData.command) {
            setError('Command is required for stdio transport');
            return;
          }
          connection_config = {
            command: formData.command
          };
          break;
        case 'npx':
          if (!formData.package) {
            setError('Package name is required for NPX transport');
            return;
          }
          connection_config = {
            package: formData.package
          };
          break;
        default:
          setError('Unsupported transport type');
          return;
      }

      const clientConfig: MCPClientConfig = {
        name: formData.name.trim(),
        transport_type: formData.transport_type,
        connection_config,
        auto_connect: formData.auto_connect
      };

      await onSubmit(clientConfig);
      
      // Reset form
      setFormData({
        name: '',
        transport_type: 'sse',
        host: '',
        port: '',
        command: '',
        package: '',
        auto_connect: true
      });
    } catch (error) {
      setError(error instanceof Error ? error.message : 'Failed to add client');
    } finally {
      setIsSubmitting(false);
    }
  };

  if (!isOpen) return null;

  return (
    <div className="fixed inset-0 bg-black/50 backdrop-blur-sm flex items-center justify-center z-50">
      <div className="bg-white/90 dark:bg-black/90 border border-gray-200 dark:border-gray-800 rounded-lg p-6 w-full max-w-md relative backdrop-blur-lg">
        <div className="absolute top-0 left-0 right-0 h-[2px] bg-gradient-to-r from-cyan-400 via-blue-500 to-cyan-400 shadow-[0_0_10px_rgba(34,211,238,0.6)]"></div>
        
        <h3 className="text-xl font-bold text-gray-900 dark:text-white mb-4">
          Add New MCP Client
        </h3>
        
        <form onSubmit={handleSubmit} className="space-y-4">
          {/* Client Name */}
          <div>
            <label className="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-1">
              Client Name *
            </label>
            <input 
              type="text" 
              value={formData.name}
              onChange={(e) => setFormData(prev => ({ ...prev, name: e.target.value }))}
              className="w-full px-3 py-2 bg-white/50 dark:bg-black/50 border border-gray-300 dark:border-gray-700 rounded-md" 
              placeholder="Enter client name" 
              required
            />
          </div>

          {/* Transport Type */}
          <div>
            <label className="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-1">
              Transport Type *
            </label>
            <select 
              value={formData.transport_type}
              onChange={(e) => setFormData(prev => ({ ...prev, transport_type: e.target.value as any }))}
              className="w-full px-3 py-2 bg-white/50 dark:bg-black/50 border border-gray-300 dark:border-gray-700 rounded-md"
            >
              <option value="sse">SSE (Server-Sent Events)</option>
              <option value="stdio">stdio (Process)</option>
              <option value="npx">NPX (Node Package)</option>
              <option value="docker">Docker (Container)</option>
            </select>
          </div>

          {/* Transport-specific fields */}
          {formData.transport_type === 'sse' && (
            <>
              <div>
                <label className="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-1">
                  Host *
                </label>
                <input 
                  type="text" 
                  value={formData.host}
                  onChange={(e) => setFormData(prev => ({ ...prev, host: e.target.value }))}
                  className="w-full px-3 py-2 bg-white/50 dark:bg-black/50 border border-gray-300 dark:border-gray-700 rounded-md" 
                  placeholder="localhost or IP address" 
                />
              </div>
              <div>
                <label className="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-1">
                  Port *
                </label>
                <input 
                  type="number" 
                  value={formData.port}
                  onChange={(e) => setFormData(prev => ({ ...prev, port: e.target.value }))}
                  className="w-full px-3 py-2 bg-white/50 dark:bg-black/50 border border-gray-300 dark:border-gray-700 rounded-md" 
                  placeholder="8051" 
                />
              </div>
            </>
          )}

          {formData.transport_type === 'stdio' && (
            <div>
              <label className="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-1">
                Command *
              </label>
              <input 
                type="text" 
                value={formData.command}
                onChange={(e) => setFormData(prev => ({ ...prev, command: e.target.value }))}
                className="w-full px-3 py-2 bg-white/50 dark:bg-black/50 border border-gray-300 dark:border-gray-700 rounded-md" 
                placeholder="python mcp_server.py" 
              />
            </div>
          )}

          {formData.transport_type === 'npx' && (
            <div>
              <label className="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-1">
                Package Name *
              </label>
              <input 
                type="text" 
                value={formData.package}
                onChange={(e) => setFormData(prev => ({ ...prev, package: e.target.value }))}
                className="w-full px-3 py-2 bg-white/50 dark:bg-black/50 border border-gray-300 dark:border-gray-700 rounded-md" 
                placeholder="@example/mcp-server" 
              />
            </div>
          )}

          {/* Auto Connect */}
          <div className="flex items-center">
            <input 
              type="checkbox" 
              id="auto_connect"
              checked={formData.auto_connect}
              onChange={(e) => setFormData(prev => ({ ...prev, auto_connect: e.target.checked }))}
              className="mr-2" 
            />
            <label htmlFor="auto_connect" className="text-sm text-gray-700 dark:text-gray-300">
              Auto-connect on startup
            </label>
          </div>

          {/* Error message */}
          {error && (
            <div className="text-red-600 dark:text-red-400 text-sm">{error}</div>
          )}

          {/* Buttons */}
          <div className="flex justify-end gap-3 mt-6">
            <Button variant="ghost" onClick={onClose} disabled={isSubmitting}>
              Cancel
            </Button>
            <Button 
              type="submit" 
              variant="primary" 
              accentColor="cyan" 
              disabled={isSubmitting}
            >
              {isSubmitting ? 'Adding...' : 'Add Client'}
            </Button>
          </div>
        </form>
      </div>
    </div>
  );
};