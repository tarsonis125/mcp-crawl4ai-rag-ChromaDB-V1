import { useState, useEffect, useRef } from 'react';
import { Play, Square, Copy, Clock, Server, AlertCircle, CheckCircle, Loader } from 'lucide-react';
import { motion } from 'framer-motion';
import { Card } from '../components/ui/Card';
import { Button } from '../components/ui/Button';
import { useStaggeredEntrance } from '../hooks/useStaggeredEntrance';
import { useToast } from '../contexts/ToastContext';
import { mcpServerService, ServerStatus, LogEntry, ServerConfig } from '../services/mcpServerService';
import { MCPClients } from '../components/mcp/MCPClients';

/**
 * MCP Dashboard Page Component
 * 
 * This is the main dashboard for managing the MCP (Model Context Protocol) server.
 * It provides a comprehensive interface for:
 * 
 * 1. Server Control Tab:
 *    - Start/stop the MCP server
 *    - Monitor server status and uptime
 *    - Switch between SSE and stdio transports
 *    - View and copy connection configuration
 *    - Real-time log streaming via WebSocket
 *    - Historical log viewing and clearing
 * 
 * 2. MCP Clients Tab:
 *    - Interactive client management interface
 *    - Tool discovery and testing
 *    - Real-time tool execution
 *    - Parameter input and result visualization
 * 
 * The page uses a tab-based layout with preserved server functionality
 * and enhanced client management capabilities.
 * 
 * @component
 */
export const MCPPage = () => {
  const [serverStatus, setServerStatus] = useState<ServerStatus>({
    status: 'stopped',
    uptime: null,
    logs: []
  });
  const [config, setConfig] = useState<ServerConfig | null>(null);
  const [logs, setLogs] = useState<LogEntry[]>([]);
  const [isLoading, setIsLoading] = useState(true);
  const [isStarting, setIsStarting] = useState(false);
  const [isStopping, setIsStopping] = useState(false);
  const [selectedTransport, setSelectedTransport] = useState<'sse' | 'stdio'>('sse');
  const [transportMode, setTransportMode] = useState<'sse' | 'stdio' | 'dual'>('dual');
  const logsEndRef = useRef<HTMLDivElement>(null);
  const logsContainerRef = useRef<HTMLDivElement>(null);
  const statusPollInterval = useRef<NodeJS.Timeout | null>(null);
  const { showToast } = useToast();

  // Tab state for switching between Server Control and Clients
  const [activeTab, setActiveTab] = useState<'server' | 'clients'>('server');

  // Use staggered entrance animation
  const { isVisible, containerVariants, itemVariants, titleVariants } = useStaggeredEntrance(
    [1, 2, 3],
    0.15
  );

  // Load initial status and start polling
  useEffect(() => {
    loadStatus();
    loadConfiguration();
    loadTransportMode();

    // Start polling for status updates every 5 seconds
    statusPollInterval.current = setInterval(loadStatus, 5000);

    return () => {
      if (statusPollInterval.current) {
        clearInterval(statusPollInterval.current);
      }
      mcpServerService.disconnectLogs();
    };
  }, []);

  // Update selected transport based on transport mode
  useEffect(() => {
    if (transportMode === 'sse') {
      setSelectedTransport('sse');
    } else if (transportMode === 'stdio') {
      setSelectedTransport('stdio');
    } else if (transportMode === 'dual') {
      // Default to SSE for dual mode
      setSelectedTransport('sse');
    }
  }, [transportMode]);

  // Start WebSocket connection when server is running
  useEffect(() => {
    if (serverStatus.status === 'running') {
      // Fetch historical logs first (last 100 entries)
      mcpServerService.getLogs({ limit: 100 }).then(historicalLogs => {
        setLogs(historicalLogs);
      }).catch(console.error);

      // Then start streaming new logs via WebSocket
      mcpServerService.streamLogs((log) => {
        setLogs(prev => [...prev, log]);
      }, { autoReconnect: true });
      
      // Ensure configuration is loaded when server is running
      if (!config) {
        loadConfiguration();
      }
    } else {
      mcpServerService.disconnectLogs();
    }
  }, [serverStatus.status]);

  // Auto-scroll logs to bottom when new logs arrive
  useEffect(() => {
    if (logsContainerRef.current && logsEndRef.current) {
      logsContainerRef.current.scrollTop = logsContainerRef.current.scrollHeight;
    }
  }, [logs]);

  /**
   * Load the current MCP server status
   * Called on mount and every 5 seconds via polling
   */
  const loadStatus = async () => {
    try {
      const status = await mcpServerService.getStatus();
      setServerStatus(status);
      setIsLoading(false);
    } catch (error) {
      console.error('Failed to load server status:', error);
      setIsLoading(false);
    }
  };

  /**
   * Load the MCP server configuration
   * Falls back to default values if database load fails
   */
  const loadConfiguration = async () => {
    try {
      const cfg = await mcpServerService.getConfiguration();
      console.log('Loaded configuration:', cfg);
      setConfig(cfg);
    } catch (error) {
      console.error('Failed to load configuration:', error);
      // Set a default config if loading fails
      setConfig({
        transport: 'sse',
        host: 'localhost',
        port: 8051
      });
    }
  };

  /**
   * Load the MCP transport mode from database
   */
  const loadTransportMode = async () => {
    try {
      const baseUrl = (import.meta as any).env?.VITE_API_URL || 'http://localhost:8080';
      const response = await fetch(`${baseUrl}/api/credentials/MCP_TRANSPORT`);
      if (response.ok) {
        const data = await response.json();
        const mode = data.value || 'dual';
        setTransportMode(mode as 'sse' | 'stdio' | 'dual');
      }
    } catch (error) {
      console.error('Failed to load transport mode:', error);
      // Default to dual mode
      setTransportMode('dual');
    }
  };

  /**
   * Start the MCP server
   */
  const handleStartServer = async () => {
    try {
      setIsStarting(true);
      const response = await mcpServerService.startServer();
      showToast(response.message, 'success');
      // Immediately refresh status
      await loadStatus();
    } catch (error: any) {
      showToast(error.message || 'Failed to start server', 'error');
    } finally {
      setIsStarting(false);
    }
  };

  const handleStopServer = async () => {
    try {
      setIsStopping(true);
      const response = await mcpServerService.stopServer();
      showToast(response.message, 'success');
      // Clear logs when server stops
      setLogs([]);
      // Immediately refresh status
      await loadStatus();
    } catch (error: any) {
      showToast(error.message || 'Failed to stop server', 'error');
    } finally {
      setIsStopping(false);
    }
  };

  const handleClearLogs = async () => {
    try {
      await mcpServerService.clearLogs();
      setLogs([]);
      showToast('Logs cleared', 'success');
    } catch (error) {
      showToast('Failed to clear logs', 'error');
    }
  };

  const handleCopyConfig = () => {
    if (!config) return;
    
    const configText = {
      mcpServers: {
        archon: {
          transport: config.transport,
          url: `http://${config.host}:${config.port}/${config.transport}`
        }
      }
    };
    
    navigator.clipboard.writeText(JSON.stringify(configText, null, 2));
    showToast('Configuration copied to clipboard', 'success');
  };

  const updateTransport = async (transport: 'sse' | 'stdio') => {
    try {
      const baseUrl = (import.meta as any).env?.VITE_API_URL || 'http://localhost:8080';
      await fetch(`${baseUrl}/api/credentials/TRANSPORT`, {
        method: 'PUT',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ value: transport })
      });
    } catch (error) {
      console.error('Failed to update transport:', error);
    }
  };

  const updateTransportMode = async (mode: 'sse' | 'stdio' | 'dual') => {
    try {
      const baseUrl = (import.meta as any).env?.VITE_API_URL || 'http://localhost:8080';
      const response = await fetch(`${baseUrl}/api/credentials/MCP_TRANSPORT`, {
        method: 'PUT',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ 
          value: mode,
          category: 'server_config',
          description: 'MCP server transport mode - sse, stdio, or dual'
        })
      });
      
      if (response.ok) {
        setTransportMode(mode);
        showToast(`Transport mode set to ${mode.toUpperCase()}`, 'success');
        
        // If server is running, suggest restart
        if (serverStatus.status === 'running') {
          showToast('Restart the MCP server for changes to take effect', 'info');
        }
      } else {
        throw new Error('Failed to update transport mode');
      }
    } catch (error) {
      console.error('Failed to update transport mode:', error);
      showToast('Failed to update transport mode', 'error');
    }
  };

  const getConfigDisplay = () => {
    if (!config) return '';
    
    if (selectedTransport === 'sse') {
      // SSE configuration for web-based clients
      const sseConfig = {
        mcpServers: {
          archon: {
            transport: "sse",
            url: `http://${config.host}:${config.port}/sse`
          }
        }
      };
      return JSON.stringify(sseConfig, null, 2);
    } else {
      // Stdio configuration for Cursor/Claude Desktop
      const stdioConfig = {
        mcpServers: {
          archon: {
            command: "docker",
            args: [
              "exec", 
              "-i",
              "-e", "TRANSPORT=stdio",
              "-e", "HOST=localhost", 
              "-e", "PORT=8051",
              "archon-pyserver",
              "uv", "run", "python", "src/mcp_server.py"
            ]
          }
        }
      };
      return JSON.stringify(stdioConfig, null, 2);
    }
  };

  const formatUptime = (seconds: number): string => {
    const hours = Math.floor(seconds / 3600);
    const minutes = Math.floor((seconds % 3600) / 60);
    const secs = seconds % 60;
    return `${hours}h ${minutes}m ${secs}s`;
  };

  const formatLogEntry = (log: LogEntry | string): string => {
    if (typeof log === 'string') {
      return log;
    }
    return `[${log.level}] ${log.message}`;
  };

  const getStatusIcon = () => {
    switch (serverStatus.status) {
      case 'running':
        return <CheckCircle className="w-5 h-5 text-green-500" />;
      case 'starting':
      case 'stopping':
        return <Loader className="w-5 h-5 text-blue-500 animate-spin" />;
      default:
        return <AlertCircle className="w-5 h-5 text-red-500" />;
    }
  };

  const getStatusColor = () => {
    switch (serverStatus.status) {
      case 'running':
        return 'text-green-500';
      case 'starting':
      case 'stopping':
        return 'text-blue-500';
      default:
        return 'text-red-500';
    }
  };

  if (isLoading) {
    return (
      <div className="flex items-center justify-center min-h-[400px]">
        <Loader className="animate-spin text-gray-500" size={32} />
      </div>
    );
  }

  return (
    <motion.div
      initial="hidden"
      animate={isVisible ? 'visible' : 'hidden'}
      variants={containerVariants}
    >
      <motion.h1
        className="text-3xl font-bold text-gray-800 dark:text-white mb-8"
        variants={titleVariants}
      >
        MCP Dashboard
      </motion.h1>

      {/* Tab Navigation */}
      <motion.div className="mb-6 border-b border-gray-200 dark:border-gray-800" variants={itemVariants}>
        <div className="flex space-x-8">
          <button
            onClick={() => setActiveTab('server')}
            className={`pb-3 relative ${
              activeTab === 'server'
                ? 'text-blue-600 dark:text-blue-400 font-medium'
                : 'text-gray-500 dark:text-gray-400 hover:text-gray-700 dark:hover:text-gray-300'
            }`}
          >
            Server Control
            {activeTab === 'server' && (
              <span className="absolute bottom-0 left-0 right-0 h-0.5 bg-blue-500 shadow-[0_0_10px_rgba(59,130,246,0.5)]"></span>
            )}
          </button>
          <button
            onClick={() => setActiveTab('clients')}
            className={`pb-3 relative ${
              activeTab === 'clients'
                ? 'text-cyan-600 dark:text-cyan-400 font-medium'
                : 'text-gray-500 dark:text-gray-400 hover:text-gray-700 dark:hover:text-gray-300'
            }`}
          >
            MCP Clients
            {activeTab === 'clients' && (
              <span className="absolute bottom-0 left-0 right-0 h-0.5 bg-cyan-500 shadow-[0_0_10px_rgba(34,211,238,0.5)]"></span>
            )}
          </button>
        </div>
      </motion.div>

      {/* Server Control Tab */}
      {activeTab === 'server' && (
        <>
          {/* Server Control + Server Logs */}
          <motion.div className="grid grid-cols-1 lg:grid-cols-2 gap-6" variants={itemVariants}>
            
            {/* Left Column: Archon MCP Server */}
            <div>
              <h2 className="text-xl font-semibold text-gray-800 dark:text-white mb-4 flex items-center">
                <Server className="mr-2 text-blue-500" size={20} />
                Archon MCP Server
              </h2>
              
              <Card accentColor="blue" className="space-y-6">
                {/* Status Display */}
                <div className="flex items-center justify-between">
                  <div 
                    className="flex items-center gap-3 cursor-help" 
                    title={process.env.NODE_ENV === 'development' ? 
                      `Debug Info:\nStatus: ${serverStatus.status}\nConfig: ${config ? 'loaded' : 'null'}\n${config ? `Details: ${JSON.stringify(config, null, 2)}` : ''}` : 
                      undefined
                    }
                  >
                    {getStatusIcon()}
                    <div>
                      <p className={`font-semibold ${getStatusColor()}`}>
                        Status: {serverStatus.status.charAt(0).toUpperCase() + serverStatus.status.slice(1)}
                      </p>
                      {serverStatus.uptime !== null && (
                        <p className="text-sm text-gray-600 dark:text-zinc-400">
                          Uptime: {formatUptime(serverStatus.uptime)}
                        </p>
                      )}
                    </div>
                  </div>
                  
                  {/* Control Buttons */}
                  <div className="flex gap-2 items-center">
                    {/* Transport Mode Dropdown */}
                    <select
                      value={transportMode}
                      onChange={(e) => updateTransportMode(e.target.value as 'sse' | 'stdio' | 'dual')}
                      disabled={serverStatus.status === 'running' || isStarting || isStopping}
                      className="px-4 py-2.5 text-sm font-medium border border-gray-300 dark:border-zinc-700 rounded-lg bg-white dark:bg-zinc-900 text-gray-700 dark:text-zinc-300 focus:outline-none focus:ring-2 focus:ring-blue-500 focus:border-blue-500 shadow-sm hover:shadow-md transition-all duration-200 disabled:opacity-50 disabled:cursor-not-allowed focus:shadow-blue-500/25 focus:shadow-lg"
                      style={{
                        background: 'linear-gradient(135deg, rgba(59, 130, 246, 0.1) 0%, rgba(147, 51, 234, 0.1) 100%)',
                        boxShadow: '0 0 0 1px rgba(59, 130, 246, 0.2), 0 1px 3px rgba(0, 0, 0, 0.1)'
                      }}
                    >
                      <option value="dual">Mode: DUAL</option>
                      <option value="sse">Mode: SSE</option>
                      <option value="stdio">Mode: STDIO</option>
                    </select>

                    {serverStatus.status === 'stopped' ? (
                      <Button
                        onClick={handleStartServer}
                        disabled={isStarting}
                        variant="primary"
                        accentColor="green"
                        className="shadow-emerald-500/20 shadow-sm"
                      >
                        {isStarting ? (
                          <>
                            <Loader className="w-4 h-4 mr-2 animate-spin inline" />
                            Starting...
                          </>
                        ) : (
                          <>
                            <Play className="w-4 h-4 mr-2 inline" />
                            Start Server
                          </>
                        )}
                      </Button>
                    ) : (
                      <Button
                        onClick={handleStopServer}
                        disabled={isStopping || serverStatus.status !== 'running'}
                        variant="primary"
                        accentColor="pink"
                        className="shadow-pink-500/20 shadow-sm"
                      >
                        {isStopping ? (
                          <>
                            <Loader className="w-4 h-4 mr-2 animate-spin inline" />
                            Stopping...
                          </>
                        ) : (
                          <>
                            <Square className="w-4 h-4 mr-2 inline" />
                            Stop Server
                          </>
                        )}
                      </Button>
                    )}
                  </div>
                </div>

                {/* Connection Details */}
                {serverStatus.status === 'running' && config && (
                  <div className="border-t border-gray-200 dark:border-zinc-800 pt-4">
                    <div className="flex items-center justify-between mb-3">
                      <h3 className="text-sm font-medium text-gray-700 dark:text-zinc-300">
                        Transport Configuration
                        <span className="ml-2 px-2 py-1 text-xs bg-blue-100 dark:bg-blue-900 text-blue-800 dark:text-blue-200 rounded-full">
                          {transportMode.toUpperCase()}
                        </span>
                      </h3>
                      <Button
                        variant="secondary"
                        accentColor="blue"
                        size="sm"
                        onClick={handleCopyConfig}
                      >
                        <Copy className="w-3 h-3 mr-1 inline" />
                        Copy
                      </Button>
                    </div>
                    
                    {/* Transport Selection Tabs */}
                    <div className="mb-4">
                      <div className="flex border-b border-gray-200 dark:border-zinc-700 mb-3">
                        <button
                          onClick={() => setSelectedTransport('sse')}
                          disabled={transportMode === 'stdio'}
                          className={`px-4 py-2 text-sm font-medium border-b-2 transition-colors ${
                            selectedTransport === 'sse'
                              ? 'border-blue-500 text-blue-600 dark:text-blue-400'
                              : 'border-transparent text-gray-500 dark:text-zinc-400 hover:text-gray-700 dark:hover:text-zinc-300'
                          } ${
                            transportMode === 'stdio' 
                              ? 'opacity-50 cursor-not-allowed' 
                              : 'cursor-pointer'
                          }`}
                        >
                          SSE (Web)
                        </button>
                        <button
                          onClick={() => setSelectedTransport('stdio')}
                          disabled={transportMode === 'sse'}
                          className={`px-4 py-2 text-sm font-medium border-b-2 transition-colors ${
                            selectedTransport === 'stdio'
                              ? 'border-blue-500 text-blue-600 dark:text-blue-400'
                              : 'border-transparent text-gray-500 dark:text-zinc-400 hover:text-gray-700 dark:hover:text-zinc-300'
                          } ${
                            transportMode === 'sse' 
                              ? 'opacity-50 cursor-not-allowed' 
                              : 'cursor-pointer'
                          }`}
                        >
                          Stdio (Cursor/Claude)
                        </button>
                      </div>
                    </div>

                    <div className="bg-gray-50 dark:bg-black/50 rounded-lg p-4 font-mono text-sm relative">
                      <pre className="text-gray-600 dark:text-zinc-400 whitespace-pre-wrap">
                        {getConfigDisplay()}
                      </pre>
                      <p className="text-xs text-gray-500 dark:text-zinc-500 mt-3 font-sans">
                        {selectedTransport === 'sse' 
                          ? 'Add this to your web-based MCP client configuration'
                          : 'Add this to your MCP client configuration (e.g., ~/.cursor/mcp.json)'}
                      </p>
                    </div>
                  </div>
                )}
              </Card>
            </div>

            {/* Right Column: Server Logs */}
            <div>
              <h2 className="text-xl font-semibold text-gray-800 dark:text-white mb-4 flex items-center">
                <Clock className="mr-2 text-purple-500" size={20} />
                Server Logs
              </h2>
              
              <Card accentColor="purple">
                <div className="flex items-center justify-between mb-4">
                  <p className="text-sm text-gray-600 dark:text-zinc-400">
                    {logs.length > 0 
                      ? `Showing ${logs.length} log entries`
                      : 'No logs available'
                    }
                  </p>
                  <Button
                    variant="ghost"
                    size="sm"
                    onClick={handleClearLogs}
                    disabled={logs.length === 0}
                  >
                    Clear Logs
                  </Button>
                </div>
                
                <div 
                  id="mcp-logs-container"
                  ref={logsContainerRef}
                  className="bg-gray-50 dark:bg-black border border-gray-200 dark:border-zinc-900 rounded-md p-4 h-80 overflow-y-auto font-mono text-sm"
                >
                  {logs.length === 0 ? (
                    <p className="text-gray-500 dark:text-zinc-500 text-center py-8">
                      {serverStatus.status === 'running' 
                        ? 'Waiting for log entries...'
                        : 'Start the server to see logs'
                      }
                    </p>
                  ) : (
                    logs.map((log, index) => (
                      <div
                        key={index}
                        className={`py-1.5 border-b border-gray-100 dark:border-zinc-900 last:border-0 ${
                          typeof log !== 'string' && log.level === 'ERROR' 
                            ? 'text-red-600 dark:text-red-400' 
                            : typeof log !== 'string' && log.level === 'WARNING'
                            ? 'text-yellow-600 dark:text-yellow-400'
                            : 'text-gray-600 dark:text-zinc-400'
                        }`}
                      >
                        {formatLogEntry(log)}
                      </div>
                    ))
                  )}
                  <div ref={logsEndRef} />
                </div>
              </Card>
            </div>
          </motion.div>
        </>
      )}

      {/* Clients Tab */}
      {activeTab === 'clients' && (
        <motion.div variants={itemVariants}>
          <MCPClients />
        </motion.div>
      )}
    </motion.div>
  );
};