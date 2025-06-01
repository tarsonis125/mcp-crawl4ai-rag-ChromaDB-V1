import { useState, useEffect, useRef } from 'react';
import { Play, Square, Copy, Clock, Server, AlertCircle, CheckCircle, Loader, Trash2, Wrench, Code, ExternalLink, PlayCircle, Terminal } from 'lucide-react';
import { motion } from 'framer-motion';
import { Card } from '../components/ui/Card';
import { Button } from '../components/ui/Button';
import { useStaggeredEntrance } from '../hooks/useStaggeredEntrance';
import { useToast } from '../contexts/ToastContext';
import { mcpService, ServerStatus, LogEntry, ServerConfig, MCPTool } from '../services/mcpService';

export const MCPPage = () => {
  const [serverStatus, setServerStatus] = useState<ServerStatus>({
    status: 'stopped',
    uptime: null,
    logs: []
  });
  const [config, setConfig] = useState<ServerConfig | null>(null);
  const [logs, setLogs] = useState<LogEntry[]>([]);
  const [tools, setTools] = useState<MCPTool[]>([]);
  const [isLoading, setIsLoading] = useState(true);
  const [isLoadingTools, setIsLoadingTools] = useState(false);
  const [isStarting, setIsStarting] = useState(false);
  const [isStopping, setIsStopping] = useState(false);
  const [toolsError, setToolsError] = useState<string | null>(null);
  const logsEndRef = useRef<HTMLDivElement>(null);
  const logsContainerRef = useRef<HTMLDivElement>(null);
  const statusPollInterval = useRef<NodeJS.Timeout | null>(null);
  const { showToast } = useToast();

  // MCP Testing state
  const [selectedTool, setSelectedTool] = useState<MCPTool | null>(null);
  const [testParams, setTestParams] = useState<Record<string, any>>({});
  const [testResult, setTestResult] = useState<any>(null);
  const [isTestingTool, setIsTestingTool] = useState(false);
  const [testError, setTestError] = useState<string | null>(null);

  // Use staggered entrance animation
  const { isVisible, containerVariants, itemVariants, titleVariants } = useStaggeredEntrance(
    [1, 2, 3, 4],
    0.15
  );

  // Load initial status and start polling
  useEffect(() => {
    loadStatus();
    loadConfiguration();

    // Start polling for status updates
    statusPollInterval.current = setInterval(loadStatus, 5000);

    return () => {
      if (statusPollInterval.current) {
        clearInterval(statusPollInterval.current);
      }
      mcpService.disconnectLogs();
    };
  }, []);

  // Start WebSocket connection when server is running
  useEffect(() => {
    if (serverStatus.status === 'running') {
      // Fetch historical logs first
      mcpService.getLogs({ limit: 100 }).then(historicalLogs => {
        setLogs(historicalLogs);
      }).catch(console.error);

      // Then start streaming
      mcpService.streamLogs((log) => {
        setLogs(prev => [...prev, log]);
      }, { autoReconnect: true });

      // Load tools when server is running
      loadMCPTools();
      
      // Ensure configuration is loaded when server is running
      if (!config) {
        loadConfiguration();
      }
    } else {
      mcpService.disconnectLogs();
      setTools([]);
      setToolsError(null);
    }
  }, [serverStatus.status]);

  // Auto-scroll logs to bottom
  useEffect(() => {
    if (logsContainerRef.current && logsEndRef.current) {
      logsContainerRef.current.scrollTop = logsContainerRef.current.scrollHeight;
    }
  }, [logs]);

  const loadStatus = async () => {
    try {
      const status = await mcpService.getStatus();
      setServerStatus(status);
      setIsLoading(false);
    } catch (error) {
      console.error('Failed to load server status:', error);
      setIsLoading(false);
    }
  };

  const loadConfiguration = async () => {
    try {
      const cfg = await mcpService.getConfiguration();
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

  const loadMCPTools = async () => {
    setIsLoadingTools(true);
    setToolsError(null);
    try {
      const mcpTools = await mcpService.getAvailableTools();
      setTools(mcpTools);
    } catch (error: any) {
      console.error('Failed to load MCP tools:', error);
      setToolsError(error.message || 'Failed to load tools');
      setTools([]);
    } finally {
      setIsLoadingTools(false);
    }
  };

  const handleStartServer = async () => {
    try {
      setIsStarting(true);
      const response = await mcpService.startServer();
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
      const response = await mcpService.stopServer();
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
      await mcpService.clearLogs();
      setLogs([]);
      showToast('Logs cleared', 'success');
    } catch (error) {
      showToast('Failed to clear logs', 'error');
    }
  };

  const handleRefreshTools = () => {
    if (serverStatus.status === 'running') {
      loadMCPTools();
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

  const getConfigDisplay = () => {
    if (!config) return '';
    
    const configObj = {
      mcpServers: {
        archon: {
          transport: config.transport,
          url: `http://${config.host}:${config.port}/${config.transport}`
        }
      }
    };
    
    return JSON.stringify(configObj, null, 2);
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

  const extractParametersFromSchema = (tool: MCPTool) => {
    if (!tool.inputSchema?.properties) return [];
    
    const required = tool.inputSchema.required || [];
    return Object.entries(tool.inputSchema.properties).map(([name, schema]: [string, any]) => ({
      name,
      type: schema.type || 'unknown',
      required: required.includes(name),
      description: schema.description || ''
    }));
  };

  // MCP Testing functions
  const handleToolSelect = (tool: MCPTool) => {
    setSelectedTool(tool);
    setTestParams({});
    setTestResult(null);
    setTestError(null);
  };

  const handleParamChange = (paramName: string, value: any) => {
    setTestParams(prev => ({
      ...prev,
      [paramName]: value
    }));
  };

  const handleTestTool = async () => {
    if (!selectedTool) return;

    setIsTestingTool(true);
    setTestError(null);
    setTestResult(null);

    try {
      // Use the backend API to call the tool since we can't call MCP directly
      const baseUrl = (import.meta as any).env?.VITE_API_URL || 'http://localhost:8080';
      let endpoint = '';
      let body = {};

      // Map tool names to backend endpoints
      switch (selectedTool.name) {
        case 'crawl_single_page':
          endpoint = '/api/crawl/single';
          body = { url: testParams.url };
          break;
        case 'smart_crawl_url':
          endpoint = '/api/crawl/smart';
          body = { 
            url: testParams.url,
            max_depth: testParams.max_depth || 3,
            max_concurrent: testParams.max_concurrent || 10,
            chunk_size: testParams.chunk_size || 5000
          };
          break;
        case 'perform_rag_query':
          endpoint = '/api/rag/query';
          body = {
            query: testParams.query,
            source: testParams.source,
            match_count: testParams.match_count || 5
          };
          break;
        case 'get_available_sources':
          endpoint = '/api/rag/sources';
          break;
        default:
          throw new Error(`Tool "${selectedTool.name}" is not supported for testing yet`);
      }

      const response = await fetch(`${baseUrl}${endpoint}`, {
        method: endpoint === '/api/rag/sources' ? 'GET' : 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: endpoint === '/api/rag/sources' ? undefined : JSON.stringify(body)
      });

      if (!response.ok) {
        const errorData = await response.json();
        throw new Error(errorData.error || `HTTP ${response.status}`);
      }

      const result = await response.json();
      setTestResult(result);
      showToast(`Tool "${selectedTool.name}" executed successfully`, 'success');
    } catch (error: any) {
      console.error('Tool test error:', error);
      setTestError(error.message || 'Failed to execute tool');
      showToast(`Tool test failed: ${error.message}`, 'error');
    } finally {
      setIsTestingTool(false);
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

      {/* Top Row: Server Control + Server Logs */}
      <motion.div className="grid grid-cols-1 lg:grid-cols-2 gap-6 mb-8" variants={itemVariants}>
        
        {/* Left Column: Server Control */}
        <div>
          <h2 className="text-xl font-semibold text-gray-800 dark:text-white mb-4 flex items-center">
            <Server className="mr-2 text-blue-500" size={20} />
            Server Control
          </h2>
          
          <Card accentColor="blue" className="space-y-6">
            {/* Status Display */}
            <div className="flex items-center justify-between">
              <div className="flex items-center gap-3">
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
              <div className="flex gap-2">
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
                <h3 className="text-sm font-medium text-gray-700 dark:text-zinc-300 mb-3">
                  Connection Configuration
                </h3>
                <div className="bg-gray-50 dark:bg-black/50 rounded-lg p-4 font-mono text-sm relative">
                  <pre className="text-gray-600 dark:text-zinc-400 whitespace-pre-wrap">
                    {getConfigDisplay()}
                  </pre>
                  <p className="text-xs text-gray-500 dark:text-zinc-500 mt-3 font-sans">
                    Add this to your MCP client configuration (e.g., ~/.cursor/mcp.json)
                  </p>
                </div>
                <Button
                  variant="secondary"
                  accentColor="blue"
                  onClick={handleCopyConfig}
                  className="mt-3"
                >
                  <Copy className="w-4 h-4 mr-2 inline" />
                  Copy Configuration
                </Button>
              </div>
            )}
            
            {/* Debug info - remove this after testing */}
            {process.env.NODE_ENV === 'development' && (
              <div className="mt-4 p-2 bg-yellow-100 dark:bg-yellow-900/20 rounded text-xs">
                <p>Debug - Status: {serverStatus.status}, Config: {config ? 'loaded' : 'null'}</p>
                {config && <p>Config details: {JSON.stringify(config, null, 2)}</p>}
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
                <Trash2 className="w-4 h-4 mr-1" />
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

      {/* Bottom Row: Available Tools + MCP Test Panel */}
      <motion.div className="grid grid-cols-1 xl:grid-cols-3 gap-6" variants={itemVariants}>
        
        {/* Left 2/3: Available Tools */}
        <div className="xl:col-span-2">
          <div className="flex items-center justify-between mb-4">
            <h2 className="text-xl font-semibold text-gray-800 dark:text-white flex items-center">
              <Wrench className="mr-2 text-orange-500" size={20} />
              Available Tools
            </h2>
            {serverStatus.status === 'running' && (
              <Button
                variant="ghost"
                size="sm"
                onClick={handleRefreshTools}
                disabled={isLoadingTools}
              >
                {isLoadingTools ? (
                  <Loader className="w-4 h-4 mr-1 animate-spin" />
                ) : (
                  <ExternalLink className="w-4 h-4 mr-1" />
                )}
                Refresh Tools
              </Button>
            )}
          </div>
          
          <Card accentColor="orange">
          {serverStatus.status !== 'running' ? (
            <div className="text-center py-8">
              <AlertCircle className="w-12 h-12 text-gray-400 mx-auto mb-4" />
              <p className="text-gray-500 dark:text-zinc-500">
                Start the MCP server to see available tools
              </p>
            </div>
          ) : isLoadingTools ? (
            <div className="text-center py-8">
              <Loader className="w-8 h-8 text-blue-500 mx-auto mb-4 animate-spin" />
              <p className="text-gray-500 dark:text-zinc-500">
                Loading tools from MCP server...
              </p>
            </div>
          ) : toolsError ? (
            <div className="text-center py-8">
              <AlertCircle className="w-12 h-12 text-red-400 mx-auto mb-4" />
              <p className="text-red-600 dark:text-red-400 mb-2">
                Failed to load tools
              </p>
              <p className="text-sm text-gray-500 dark:text-zinc-500">
                {toolsError}
              </p>
              <Button
                variant="secondary"
                size="sm"
                onClick={handleRefreshTools}
                className="mt-4"
              >
                Try Again
              </Button>
            </div>
          ) : tools.length === 0 ? (
            <div className="text-center py-8">
              <Code className="w-12 h-12 text-gray-400 mx-auto mb-4" />
              <p className="text-gray-500 dark:text-zinc-500">
                No tools available from MCP server
              </p>
            </div>
          ) : (
            <div className="overflow-x-auto">
              <table className="w-full">
                <thead>
                  <tr className="border-b border-gray-200 dark:border-zinc-800">
                    <th className="text-left py-3 px-4 font-semibold text-gray-700 dark:text-zinc-300">
                      Tool Name
                    </th>
                    <th className="text-left py-3 px-4 font-semibold text-gray-700 dark:text-zinc-300">
                      Description
                    </th>
                    <th className="text-left py-3 px-4 font-semibold text-gray-700 dark:text-zinc-300">
                      Parameters
                    </th>
                  </tr>
                </thead>
                <tbody>
                  {tools.map((tool, index) => {
                    const parameters = extractParametersFromSchema(tool);
                    return (
                      <tr key={index} className="border-b border-gray-100 dark:border-zinc-900 last:border-0">
                        <td className="py-3 px-4">
                          <code className="text-sm bg-gray-100 dark:bg-zinc-800 px-2 py-1 rounded text-blue-600 dark:text-blue-400">
                            {tool.name}
                          </code>
                        </td>
                        <td className="py-3 px-4 text-sm text-gray-600 dark:text-zinc-400">
                          {tool.description || 'No description available'}
                        </td>
                        <td className="py-3 px-4">
                          {parameters.length === 0 ? (
                            <span className="text-sm text-gray-500 dark:text-zinc-500 italic">
                              No parameters
                            </span>
                          ) : (
                            <div className="space-y-1">
                              {parameters.map((param, paramIndex) => (
                                <div key={paramIndex} className="text-xs">
                                  <code className="text-purple-600 dark:text-purple-400">
                                    {param.name}
                                  </code>
                                  <span className="text-gray-500 dark:text-zinc-500 ml-1">
                                    ({param.type})
                                    {param.required && <span className="text-red-500 ml-1">*</span>}
                                  </span>
                                  {param.description && (
                                    <div className="text-gray-600 dark:text-zinc-400 mt-0.5">
                                      {param.description}
                                    </div>
                                  )}
                                </div>
                              ))}
                            </div>
                          )}
                        </td>
                      </tr>
                    );
                  })}
                </tbody>
              </table>
            </div>
          )}
          </Card>
        </div>

        {/* Right 1/3: MCP Test Panel */}
        <div className="xl:col-span-1">
          <div className="flex items-center justify-between mb-4">
            <h2 className="text-xl font-semibold text-gray-800 dark:text-white flex items-center">
              <Terminal className="mr-2 text-cyan-500" size={20} />
              Test Tools
            </h2>
          </div>
          
          <Card accentColor="blue" className="h-fit">
            {tools.length === 0 ? (
              <div className="text-center py-8">
                <Terminal className="w-8 h-8 text-gray-400 mx-auto mb-4" />
                <p className="text-gray-500 dark:text-zinc-500 text-sm">
                  Load tools to start testing
                </p>
              </div>
            ) : (
              <div className="space-y-4">
                {/* Tool Selection */}
                <div>
                  <label className="block text-sm font-medium text-gray-700 dark:text-zinc-300 mb-2">
                    Select Tool
                  </label>
                  <select
                    value={selectedTool?.name || ''}
                    onChange={(e) => {
                      const tool = tools.find(t => t.name === e.target.value);
                      if (tool) handleToolSelect(tool);
                    }}
                    className="w-full px-3 py-2 border border-gray-300 dark:border-zinc-700 rounded-md bg-white dark:bg-zinc-800 text-gray-900 dark:text-zinc-100 text-sm"
                  >
                    <option value="">Choose a tool...</option>
                    {tools.map((tool) => (
                      <option key={tool.name} value={tool.name}>
                        {tool.name}
                      </option>
                    ))}
                  </select>
                </div>

                {/* Parameters */}
                {selectedTool && (
                  <div className="space-y-3">
                    <h4 className="text-sm font-medium text-gray-700 dark:text-zinc-300">
                      Parameters
                    </h4>
                    {extractParametersFromSchema(selectedTool).map((param) => (
                      <div key={param.name}>
                        <label className="block text-xs font-medium text-gray-600 dark:text-zinc-400 mb-1">
                          {param.name}
                          {param.required && <span className="text-red-500 ml-1">*</span>}
                        </label>
                        <input
                          type={param.type === 'integer' ? 'number' : 'text'}
                          value={testParams[param.name] || ''}
                          onChange={(e) => handleParamChange(param.name, 
                            param.type === 'integer' ? parseInt(e.target.value) || 0 : e.target.value
                          )}
                          placeholder={param.description}
                          className="w-full px-2 py-1 border border-gray-300 dark:border-zinc-700 rounded text-xs bg-white dark:bg-zinc-800 text-gray-900 dark:text-zinc-100"
                        />
                      </div>
                    ))}
                  </div>
                )}

                {/* Execute Button */}
                {selectedTool && (
                  <Button
                    onClick={handleTestTool}
                    disabled={isTestingTool}
                    variant="primary"
                    accentColor="blue"
                    className="w-full"
                  >
                    {isTestingTool ? (
                      <>
                        <Loader className="w-4 h-4 mr-2 animate-spin" />
                        Testing...
                      </>
                    ) : (
                      <>
                        <PlayCircle className="w-4 h-4 mr-2" />
                        Test Tool
                      </>
                    )}
                  </Button>
                )}

                {/* Results */}
                {(testResult || testError) && (
                  <div className="mt-4">
                    <h4 className="text-sm font-medium text-gray-700 dark:text-zinc-300 mb-2">
                      Result
                    </h4>
                    <div className="bg-gray-50 dark:bg-black/50 rounded-md p-3 max-h-48 overflow-y-auto">
                      {testError ? (
                        <div className="text-red-600 dark:text-red-400 text-xs">
                          Error: {testError}
                        </div>
                      ) : (
                        <pre className="text-xs text-gray-600 dark:text-zinc-400 whitespace-pre-wrap">
                          {JSON.stringify(testResult, null, 2)}
                        </pre>
                      )}
                    </div>
                  </div>
                )}
              </div>
            )}
          </Card>
        </div>
      </motion.div>
    </motion.div>
  );
};