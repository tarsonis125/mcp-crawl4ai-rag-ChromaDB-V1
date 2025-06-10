import React, { useState, memo, useEffect } from 'react';
import { Plus, Settings } from 'lucide-react';
import { ClientCard } from './ClientCard';
import { ToolTestingPanel } from './ToolTestingPanel';
import { Button } from '../ui/Button';
import { mcpClientService, MCPClient, MCPClientConfig } from '../../services/mcpClientService';

// Client interface (keeping for backward compatibility)
export interface Client {
  id: string;
  name: string;
  status: 'online' | 'offline' | 'error';
  ip: string;
  lastSeen: string;
  version: string;
  tools: Tool[];
  region?: string;
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

export const MCPClients = memo(() => {
  const [clients, setClients] = useState<Client[]>([]);
  const [isLoading, setIsLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  
  // State for selected client and panel visibility
  const [selectedClient, setSelectedClient] = useState<Client | null>(null);
  const [isPanelOpen, setIsPanelOpen] = useState(false);
  const [isAddClientModalOpen, setIsAddClientModalOpen] = useState(false);
  
  // State for edit drawer
  const [editClient, setEditClient] = useState<Client | null>(null);
  const [isEditDrawerOpen, setIsEditDrawerOpen] = useState(false);

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

      // Load ALL clients from database (including Archon)
      let dbClients: MCPClient[] = [];
      try {
        dbClients = await mcpClientService.getClients();
      } catch (clientError) {
        console.warn('Failed to load database clients:', clientError);
        dbClients = [];
      }
      
      // Convert database clients to our Client interface and load their tools
      const convertedClients: Client[] = await Promise.all(
        dbClients.map(async (dbClient) => {
          const client = convertDbClientToClient(dbClient);
          // Load tools for connected clients using universal method
          if (client.status === 'online') {
            await loadTools(client);
          }
          return client;
        })
      );

      // Set all clients (Archon will be included as a regular client)
      setClients(convertedClients);
    } catch (error) {
      console.error('Failed to load MCP clients:', error);
      setError(error instanceof Error ? error.message : 'Failed to load clients');
      setClients([]);
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
               config.command ? config.command : 
               config.package ? config.package : 'N/A';

    return {
      id: dbClient.id,
      name: dbClient.name,
      status: statusMap[dbClient.status] || 'offline',
      ip,
      lastSeen: dbClient.last_seen ? new Date(dbClient.last_seen).toLocaleString() : 'Never',
      version: config.version || 'Unknown',
      region: config.region || 'Unknown',
      tools: [] // Will be loaded separately
    };
  };



  /**
   * Load tools from any MCP client using universal client service
   */
  const loadTools = async (client: Client) => {
    try {
      const toolsResponse = await mcpClientService.getClientTools(client.id);
      
      // Convert client tools to our Tool interface format
      const convertedTools: Tool[] = toolsResponse.tools.map((clientTool: any, index: number) => {
        const parameters: ToolParameter[] = [];
        
        // Extract parameters from tool schema
        if (clientTool.tool_schema?.inputSchema?.properties) {
          const required = clientTool.tool_schema.inputSchema.required || [];
          Object.entries(clientTool.tool_schema.inputSchema.properties).forEach(([name, schema]: [string, any]) => {
            parameters.push({
              name,
              type: schema.type === 'integer' ? 'number' : 
                    schema.type === 'array' ? 'array' : 
                    schema.type === 'boolean' ? 'boolean' : 'string',
              required: required.includes(name),
              description: schema.description || `${name} parameter`
            });
          });
        }
        
        return {
          id: `${client.id}-${index}`,
          name: clientTool.tool_name,
          description: clientTool.tool_description || 'No description available',
          parameters
        };
      });

      client.tools = convertedTools;
      console.log(`Loaded ${convertedTools.length} tools for client ${client.name}`);
    } catch (error) {
      console.error(`Failed to load tools for client ${client.name}:`, error);
      client.tools = [];
    }
  };

  /**
   * Handle adding a new client
   */
  const handleAddClient = async (clientConfig: MCPClientConfig) => {
    try {
      // Create client in database
      const newClient = await mcpClientService.createClient(clientConfig);
      
      // Convert and add to local state
      const convertedClient = convertDbClientToClient(newClient);
      
      // Try to load tools if client is connected
      if (convertedClient.status === 'online') {
        await loadTools(convertedClient);
      }
      
      setClients(prev => [...prev, convertedClient]);
      
      // Close modal
      setIsAddClientModalOpen(false);
      
      console.log('Client added successfully:', newClient.name);
    } catch (error) {
      console.error('Failed to add client:', error);
      setError(error instanceof Error ? error.message : 'Failed to add client');
      throw error; // Re-throw so modal can handle it
    }
  };

  // Handle client selection
  const handleSelectClient = async (client: Client) => {
    setSelectedClient(client);
    setIsPanelOpen(true);
    
    // Refresh tools for the selected client if needed
    if (client.tools.length === 0 && client.status === 'online') {
      await loadTools(client);
      
      // Update the client in the list
      setClients(prev => prev.map(c => c.id === client.id ? client : c));
    }
  };

  // Handle client editing
  const handleEditClient = (client: Client) => {
    setEditClient(client);
    setIsEditDrawerOpen(true);
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
    <div className="relative">
      {/* Error display */}
      {error && (
        <div className="mb-6 p-4 bg-red-500/10 border border-red-500/20 rounded-lg">
          <p className="text-red-600 dark:text-red-400">{error}</p>
          <button 
            onClick={() => setError(null)} 
            className="text-red-500 hover:text-red-600 text-sm mt-2"
          >
            Dismiss
          </button>
        </div>
      )}

      {/* Add Client Button */}
      <div className="flex justify-between items-center mb-6">
        <div>
          <h2 className="text-2xl font-bold text-gray-800 dark:text-white">MCP Clients</h2>
          <p className="text-gray-600 dark:text-gray-400 mt-1">
            Connect and manage your MCP-enabled applications
          </p>
        </div>
        <Button
          onClick={() => setIsAddClientModalOpen(true)}
          variant="primary"
          accentColor="cyan"
          className="shadow-cyan-500/20 shadow-sm"
        >
          <Plus className="w-4 h-4 mr-2" />
          Add Client
        </Button>
      </div>

      {/* Client Grid */}
      <div className="space-y-6">
        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-6 relative z-10">
          {clients.map(client => (
            <ClientCard 
              key={client.id} 
              client={client} 
              onSelect={() => handleSelectClient(client)}
              onEdit={() => handleEditClient(client)} 
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
      
      {/* Edit Client Drawer */}
      {isEditDrawerOpen && editClient && (
        <EditClientDrawer 
          client={editClient}
          isOpen={isEditDrawerOpen}
          onClose={() => {
            setIsEditDrawerOpen(false);
            setEditClient(null);
          }}
          onUpdate={(updatedClient) => {
            // Update the client in state
            setClients(prev => prev.map(c => c.id === updatedClient.id ? updatedClient : c));
            setIsEditDrawerOpen(false);
            setEditClient(null);
          }}
        />
      )}
    </div>
  );
});

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
            setIsSubmitting(false);
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
            setIsSubmitting(false);
            return;
          }
          connection_config = {
            command: formData.command
          };
          break;
        case 'npx':
          if (!formData.package) {
            setError('Package name is required for NPX transport');
            setIsSubmitting(false);
            return;
          }
          connection_config = {
            package: formData.package
          };
          break;
        case 'docker':
          if (!formData.command) {
            setError('Docker command is required for Docker transport');
            setIsSubmitting(false);
            return;
          }
          connection_config = {
            command: formData.command
          };
          break;
        default:
          setError('Unsupported transport type');
          setIsSubmitting(false);
          return;
      }

      const clientConfig: MCPClientConfig = {
        name: formData.name.trim(),
        transport_type: formData.transport_type,
        connection_config,
        auto_connect: formData.auto_connect
      };

      await onSubmit(clientConfig);
      
      // Reset form on success
      setFormData({
        name: '',
        transport_type: 'sse',
        host: '',
        port: '',
        command: '',
        package: '',
        auto_connect: true
      });
      setError(null);
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
              className="w-full px-3 py-2 bg-white/50 dark:bg-black/50 border border-gray-300 dark:border-gray-700 rounded-md focus:outline-none focus:ring-2 focus:ring-cyan-500" 
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
              className="w-full px-3 py-2 bg-white/50 dark:bg-black/50 border border-gray-300 dark:border-gray-700 rounded-md focus:outline-none focus:ring-2 focus:ring-cyan-500"
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
                  className="w-full px-3 py-2 bg-white/50 dark:bg-black/50 border border-gray-300 dark:border-gray-700 rounded-md focus:outline-none focus:ring-2 focus:ring-cyan-500" 
                  placeholder="localhost" 
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
                  className="w-full px-3 py-2 bg-white/50 dark:bg-black/50 border border-gray-300 dark:border-gray-700 rounded-md focus:outline-none focus:ring-2 focus:ring-cyan-500" 
                  placeholder="8051" 
                />
              </div>
            </>
          )}

          {(formData.transport_type === 'stdio' || formData.transport_type === 'docker') && (
            <div>
              <label className="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-1">
                Command *
              </label>
              <input 
                type="text" 
                value={formData.command}
                onChange={(e) => setFormData(prev => ({ ...prev, command: e.target.value }))}
                className="w-full px-3 py-2 bg-white/50 dark:bg-black/50 border border-gray-300 dark:border-gray-700 rounded-md focus:outline-none focus:ring-2 focus:ring-cyan-500" 
                placeholder={formData.transport_type === 'docker' ? "docker run -it mcp-server" : "python mcp_server.py"} 
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
                className="w-full px-3 py-2 bg-white/50 dark:bg-black/50 border border-gray-300 dark:border-gray-700 rounded-md focus:outline-none focus:ring-2 focus:ring-cyan-500" 
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
            <div className="text-red-600 dark:text-red-400 text-sm bg-red-50 dark:bg-red-900/20 p-2 rounded">
              {error}
            </div>
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

// Edit Client Drawer Component
interface EditClientDrawerProps {
  client: Client;
  isOpen: boolean;
  onClose: () => void;
  onUpdate: (client: Client) => void;
}

const EditClientDrawer: React.FC<EditClientDrawerProps> = ({ client, isOpen, onClose, onUpdate }) => {
  if (!isOpen) return null;

  return (
    <div className="fixed inset-0 bg-black/50 backdrop-blur-sm flex items-end justify-center z-50" onClick={onClose}>
      <div 
        className="bg-white/90 dark:bg-black/90 border border-gray-200 dark:border-gray-800 rounded-t-lg p-6 w-full max-w-2xl relative backdrop-blur-lg animate-slide-up"
        onClick={(e) => e.stopPropagation()}
      >
        <div className="absolute top-0 left-0 right-0 h-[2px] bg-gradient-to-r from-cyan-400 via-blue-500 to-cyan-400 shadow-[0_0_10px_rgba(34,211,238,0.6)]"></div>
        
        <h3 className="text-xl font-bold text-gray-900 dark:text-white mb-4 flex items-center">
          <Settings className="w-5 h-5 mr-2 text-cyan-500" />
          Edit Client Configuration
        </h3>
        
        <div className="space-y-4">
          {/* Client Info Display */}
          <div className="bg-gray-50 dark:bg-gray-900/50 rounded-lg p-4">
            <h4 className="font-medium text-gray-900 dark:text-white mb-2">{client.name}</h4>
            <div className="text-sm text-gray-600 dark:text-gray-400 space-y-1">
              <p><span className="font-medium">Status:</span> {client.status}</p>
              <p><span className="font-medium">Address:</span> {client.ip}</p>
              <p><span className="font-medium">Version:</span> {client.version}</p>
              <p><span className="font-medium">Tools:</span> {client.tools.length} available</p>
              <p><span className="font-medium">Last Seen:</span> {client.lastSeen}</p>
            </div>
          </div>

          {/* Configuration Notice */}
          <div className="bg-blue-50 dark:bg-blue-900/20 border border-blue-200 dark:border-blue-800 rounded-lg p-4">
            <h4 className="font-medium text-blue-900 dark:text-blue-100 mb-2">Configuration Management</h4>
            <p className="text-sm text-blue-700 dark:text-blue-300">
              Client configuration editing will be available in a future update. For now, you can view the current settings above.
            </p>
          </div>

          {/* Actions */}
          <div className="bg-gray-50 dark:bg-gray-900/50 rounded-lg p-4">
            <h4 className="font-medium text-gray-900 dark:text-white mb-3">Available Actions</h4>
            <div className="space-y-2">
              <Button 
                variant="ghost" 
                accentColor="green"
                className="w-full justify-start"
                disabled={client.status === 'online'}
              >
                {client.status === 'online' ? 'Connected' : 'Connect'}
              </Button>
              <Button 
                variant="ghost" 
                accentColor="orange"
                className="w-full justify-start"
                disabled={client.status === 'offline'}
              >
                {client.status === 'offline' ? 'Disconnected' : 'Disconnect'}
              </Button>
              <Button 
                variant="ghost" 
                accentColor="pink"
                className="w-full justify-start"
              >
                Remove Client
              </Button>
              <Button 
                variant="ghost" 
                accentColor="cyan"
                className="w-full justify-start"
              >
                Test Connection
              </Button>
            </div>
          </div>
        </div>

        {/* Close Button */}
        <div className="flex justify-end mt-6">
          <Button variant="primary" accentColor="cyan" onClick={onClose}>
            Close
          </Button>
        </div>
      </div>
    </div>
  );
};