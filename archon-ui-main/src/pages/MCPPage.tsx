import React, { useState, useEffect, useRef } from 'react';
import { Play, Square, Copy, Clock, Server, AlertCircle, CheckCircle, Loader, Trash2 } from 'lucide-react';
import { motion } from 'framer-motion';
import { Card } from '../components/ui/Card';
import { Input } from '../components/ui/Input';
import { Button } from '../components/ui/Button';
import { Badge } from '../components/ui/Badge';
import { useStaggeredEntrance } from '../hooks/useStaggeredEntrance';
import { useToast } from '../contexts/ToastContext';
import { mcpService, ServerStatus, LogEntry, ServerConfig } from '../services/mcpService';

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
  const logsEndRef = useRef<HTMLDivElement>(null);
  const statusPollInterval = useRef<NodeJS.Timeout | null>(null);
  const { showToast } = useToast();

  // Use staggered entrance animation
  const { isVisible, containerVariants, itemVariants, titleVariants } = useStaggeredEntrance(
    [1, 2, 3],
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
    } else {
      mcpService.disconnectLogs();
    }
  }, [serverStatus.status]);

  // Auto-scroll logs to bottom
  useEffect(() => {
    logsEndRef.current?.scrollIntoView({ behavior: 'smooth' });
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
      setConfig(cfg);
    } catch (error) {
      console.error('Failed to load configuration:', error);
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

      {/* Server Status and Control */}
      <motion.div className="mb-8" variants={itemVariants}>
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
                      <Loader className="w-4 h-4 mr-2 animate-spin" />
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
                      <Loader className="w-4 h-4 mr-2 animate-spin" />
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
                Connection Details
              </h3>
              <div className="bg-gray-50 dark:bg-black/50 rounded-lg p-4 font-mono text-sm">
                <p className="text-gray-600 dark:text-zinc-400">
                  Transport: {config.transport}
                </p>
                <p className="text-gray-600 dark:text-zinc-400">
                  URL: http://{config.host}:{config.port}/{config.transport}
                </p>
              </div>
              <Button
                variant="secondary"
                accentColor="blue"
                onClick={handleCopyConfig}
                className="mt-3"
              >
                <Copy className="w-4 h-4 mr-2 inline" />
                Copy Config
              </Button>
            </div>
          )}
        </Card>
      </motion.div>

      {/* Server Logs */}
      <motion.div variants={itemVariants}>
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
          
          <div className="bg-gray-50 dark:bg-black border border-gray-200 dark:border-zinc-900 rounded-md p-4 h-96 overflow-y-auto font-mono text-sm">
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
      </motion.div>
    </motion.div>
  );
};