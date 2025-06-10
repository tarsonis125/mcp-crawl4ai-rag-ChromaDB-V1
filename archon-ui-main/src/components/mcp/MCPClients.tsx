import React, { useState, memo, useEffect } from 'react';
import { Plus } from 'lucide-react';
import { ClientCard } from './ClientCard';
import { ToolTestingPanel } from './ToolTestingPanel';
import { Button } from '../ui/Button';
import { mcpService } from '../../services/mcpService';
// Client interface
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
  // Sample clients data with Archon client first
  const [clients, setClients] = useState<Client[]>([{
    id: 'archon',
    name: 'Archon MCP Client',
    status: 'online',
    ip: '192.168.1.100',
    lastSeen: 'Just now',
    version: 'v2.0.0',
    cpuUsage: 12,
    memoryUsage: 34,
    region: 'central',
    isArchon: true,
    tools: [] // Will be loaded from real MCP server
  }, {
    id: '1',
    name: 'Production Server',
    status: 'online',
    ip: '192.168.1.101',
    lastSeen: 'Just now',
    version: 'v1.2.4',
    cpuUsage: 42,
    memoryUsage: 68,
    region: 'us-west',
    tools: [{
      id: 't1',
      name: 'system_diagnostics',
      description: 'Run system diagnostics and return health report',
      parameters: [{
        name: 'level',
        type: 'string',
        required: false,
        description: 'Diagnostic depth (basic, detailed, full)'
      }]
    }, {
      id: 't2',
      name: 'restart_service',
      description: 'Restart a specific service on the client',
      parameters: [{
        name: 'service_name',
        type: 'string',
        required: true,
        description: 'Name of the service to restart'
      }]
    }]
  }, {
    id: '2',
    name: 'Development Server',
    status: 'online',
    ip: '192.168.1.102',
    lastSeen: '5 mins ago',
    version: 'v1.3.0-beta',
    cpuUsage: 23,
    memoryUsage: 45,
    region: 'us-east',
    tools: [{
      id: 't3',
      name: 'run_tests',
      description: 'Execute test suite on the development server',
      parameters: [{
        name: 'suite',
        type: 'string',
        required: true,
        description: 'Test suite to run (unit, integration, e2e)'
      }, {
        name: 'verbose',
        type: 'boolean',
        required: false,
        description: 'Output verbose logs'
      }]
    }]
  }, {
    id: '3',
    name: 'Analytics Server',
    status: 'offline',
    ip: '192.168.1.103',
    lastSeen: '2 days ago',
    version: 'v1.2.3',
    region: 'eu-central',
    tools: [{
      id: 't4',
      name: 'generate_report',
      description: 'Generate analytics report',
      parameters: [{
        name: 'start_date',
        type: 'string',
        required: true,
        description: 'Start date for report data (YYYY-MM-DD)'
      }, {
        name: 'end_date',
        type: 'string',
        required: true,
        description: 'End date for report data (YYYY-MM-DD)'
      }, {
        name: 'format',
        type: 'string',
        required: false,
        description: 'Output format (csv, json, pdf)'
      }]
    }]
  }, {
    id: '4',
    name: 'Database Cluster',
    status: 'error',
    ip: '192.168.1.104',
    lastSeen: '35 mins ago',
    version: 'v1.2.4',
    cpuUsage: 92,
    memoryUsage: 87,
    region: 'ap-south',
    tools: [{
      id: 't5',
      name: 'backup_database',
      description: 'Create a backup of the database',
      parameters: [{
        name: 'database',
        type: 'string',
        required: true,
        description: 'Database name to backup'
      }, {
        name: 'compression',
        type: 'boolean',
        required: false,
        description: 'Use compression'
      }]
    }, {
      id: 't6',
      name: 'optimize_tables',
      description: 'Optimize database tables',
      parameters: [{
        name: 'tables',
        type: 'array',
        required: false,
        description: 'List of tables to optimize (empty for all)'
      }]
    }]
  }]);
  // State for selected client and panel visibility
  const [selectedClient, setSelectedClient] = useState<Client | null>(null);
  const [isPanelOpen, setIsPanelOpen] = useState(false);
  const [isAddClientModalOpen, setIsAddClientModalOpen] = useState(false);
  // Load real MCP tools for Archon client when component mounts
  useEffect(() => {
    loadArchonTools();
  }, []);
  /**
   * Load real tools from the MCP server for the Archon client
   */
  const loadArchonTools = async () => {
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

        // Update the Archon client with real tools
        setClients(prevClients => 
          prevClients.map(client => 
            client.id === 'archon' 
              ? { ...client, tools: convertedTools, status: 'online' as const }
              : client
          )
        );
      } else {
        // Server not running, mark Archon client as offline
        setClients(prevClients => 
          prevClients.map(client => 
            client.id === 'archon' 
              ? { ...client, tools: [], status: 'offline' as const }
              : client
          )
        );
      }
    } catch (error) {
      console.error('Failed to load Archon MCP tools:', error);
      // Mark Archon client as having an error
      setClients(prevClients => 
        prevClients.map(client => 
          client.id === 'archon' 
            ? { ...client, tools: [], status: 'error' as const }
            : client
        )
      );
    }
  };
  // Handle client selection
  const handleSelectClient = (client: Client) => {
    setSelectedClient(client);
    setIsPanelOpen(true);
  };
  return <div className="relative min-h-[80vh]">
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
          <button onClick={() => setIsAddClientModalOpen(true)} className="flex items-center gap-2 px-4 py-2 rounded-full bg-gradient-to-r from-cyan-500/80 to-blue-600/80 text-white border border-cyan-400/50 shadow-[0_0_15px_rgba(34,211,238,0.4)] hover:shadow-[0_0_20px_rgba(34,211,238,0.6)] transition-all duration-300">
            <Plus className="w-5 h-5" />
            <span className="font-medium">Add Client</span>
          </button>
        </div>
        {/* Client Cards Grid - updated for 3 columns on medium */}
        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-6 relative z-10">
          {clients.map(client => <ClientCard key={client.id} client={client} onSelect={() => handleSelectClient(client)} />)}
        </div>
      </div>
      {/* Tool Testing Panel */}
      <ToolTestingPanel client={selectedClient} isOpen={isPanelOpen} onClose={() => setIsPanelOpen(false)} />
      {/* Add Client Modal */}
      {isAddClientModalOpen && <div className="fixed inset-0 bg-black/50 backdrop-blur-sm flex items-center justify-center z-50">
          <div className="bg-white/90 dark:bg-black/90 border border-gray-200 dark:border-gray-800 rounded-lg p-6 w-full max-w-md relative backdrop-blur-lg">
            <div className="absolute top-0 left-0 right-0 h-[2px] bg-gradient-to-r from-cyan-400 via-blue-500 to-cyan-400 shadow-[0_0_10px_rgba(34,211,238,0.6)]"></div>
            <h3 className="text-xl font-bold text-gray-900 dark:text-white mb-4">
              Add New MCP Client
            </h3>
            <div className="space-y-4">
              <div>
                <label className="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-1">
                  Client Name
                </label>
                <input type="text" className="w-full px-3 py-2 bg-white/50 dark:bg-black/50 border border-gray-300 dark:border-gray-700 rounded-md" placeholder="Enter client name" />
              </div>
              <div>
                <label className="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-1">
                  IP Address
                </label>
                <input type="text" className="w-full px-3 py-2 bg-white/50 dark:bg-black/50 border border-gray-300 dark:border-gray-700 rounded-md" placeholder="192.168.1.xxx" />
              </div>
              <div>
                <label className="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-1">
                  Region
                </label>
                <select className="w-full px-3 py-2 bg-white/50 dark:bg-black/50 border border-gray-300 dark:border-gray-700 rounded-md">
                  <option value="us-west">US West</option>
                  <option value="us-east">US East</option>
                  <option value="eu-central">EU Central</option>
                  <option value="ap-south">Asia Pacific</option>
                </select>
              </div>
            </div>
            <div className="mt-6 flex justify-end gap-3">
              <Button variant="ghost" onClick={() => setIsAddClientModalOpen(false)}>
                Cancel
              </Button>
              <Button variant="primary" accentColor="cyan" onClick={() => setIsAddClientModalOpen(false)}>
                Add Client
              </Button>
            </div>
          </div>
        </div>}
    </div>;
};