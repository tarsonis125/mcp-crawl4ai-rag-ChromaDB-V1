import React, { useState } from 'react';
import { Play, Square, RefreshCw, Server, Database, Clock } from 'lucide-react';
import { motion } from 'framer-motion';
import { Card } from '../components/ui/Card';
import { Input } from '../components/ui/Input';
import { Button } from '../components/ui/Button';
import { Badge } from '../components/ui/Badge';
import { useStaggeredEntrance } from '../hooks/useStaggeredEntrance';
export const MCPPage = () => {
  const [serverStatus, setServerStatus] = useState<'stopped' | 'running' | 'starting'>('stopped');
  const [serverLogs, setServerLogs] = useState<string[]>(['[INFO] MCP Server initialization...', '[INFO] Loading configuration from /etc/mcp/config.json', '[INFO] Server ready to start']);
  const [connectionString, setConnectionString] = useState('http://localhost:3000');
  const [apiPort, setApiPort] = useState('3000');
  const [dbPath, setDbPath] = useState('./data/mcp.db');
  // Use staggered entrance animation
  const {
    isVisible,
    containerVariants,
    itemVariants,
    titleVariants
  } = useStaggeredEntrance([1, 2, 3],
  // Just need something with length
  0.15);
  const startServer = () => {
    setServerStatus('starting');
    setServerLogs(prev => [...prev, '[INFO] Starting MCP Server...']);
    // Simulate server start
    setTimeout(() => {
      setServerStatus('running');
      setServerLogs(prev => [...prev, '[INFO] Initializing database connection', '[INFO] Starting API server on port 3000', '[INFO] MCP Server running']);
    }, 2000);
  };
  const stopServer = () => {
    setServerStatus('stopped');
    setServerLogs(prev => [...prev, '[INFO] Stopping MCP Server...', '[INFO] Closing database connections', '[INFO] Server stopped']);
  };
  return <motion.div initial="hidden" animate={isVisible ? 'visible' : 'hidden'} variants={containerVariants}>
      <motion.h1 className="text-3xl font-bold text-gray-800 dark:text-white mb-8" variants={titleVariants}>
        MCP Server
      </motion.h1>
      {/* Server Controls */}
      <motion.div className="mb-8" variants={itemVariants}>
        <h2 className="text-xl font-semibold text-gray-800 dark:text-white mb-4 flex items-center">
          <Server className="mr-2 text-blue-500" size={20} />
          Server Controls
        </h2>
        <Card accentColor="blue" className="space-y-6">
          <div className="flex items-center justify-between">
            <div className="flex items-center">
              <div className={`h-3 w-3 rounded-full mr-2 ${serverStatus === 'running' ? 'bg-emerald-500' : serverStatus === 'starting' ? 'bg-blue-500' : 'bg-pink-500'}`}></div>
              <span className="text-gray-700 dark:text-white">
                Status:{' '}
                {serverStatus.charAt(0).toUpperCase() + serverStatus.slice(1)}
              </span>
            </div>
            <div className="flex gap-2">
              <Button onClick={startServer} disabled={serverStatus !== 'stopped'} variant={serverStatus === 'stopped' ? 'primary' : 'outline'} accentColor="green" size="sm" className={serverStatus === 'stopped' ? 'shadow-emerald-500/20 shadow-sm' : ''}>
                <Play className="w-4 h-4 mr-1 inline" />
                <span>Start</span>
              </Button>
              <Button onClick={stopServer} disabled={serverStatus === 'stopped'} variant={serverStatus !== 'stopped' ? 'primary' : 'outline'} accentColor="pink" size="sm" className={serverStatus !== 'stopped' ? 'shadow-pink-500/20 shadow-sm' : ''}>
                <Square className="w-4 h-4 mr-1 inline" />
                <span>Stop</span>
              </Button>
              <Button variant="outline" accentColor="blue" size="sm">
                <RefreshCw className="w-4 h-4 mr-1 inline" />
                <span>Restart</span>
              </Button>
            </div>
          </div>
          {/* Server Configuration */}
          <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
            <Input label="Connection String" type="text" value={connectionString} onChange={e => setConnectionString(e.target.value)} accentColor="blue" />
            <Input label="API Port" type="text" value={apiPort} onChange={e => setApiPort(e.target.value)} accentColor="blue" />
            <div className="md:col-span-2">
              <label className="block text-gray-600 dark:text-zinc-400 text-sm mb-1.5">
                Database Path
              </label>
              <div className="flex gap-2">
                <Input type="text" value={dbPath} onChange={e => setDbPath(e.target.value)} accentColor="blue" className="flex-1" />
                <Button variant="outline" accentColor="blue">
                  Browse
                </Button>
              </div>
            </div>
          </div>
          {/* Server Logs */}
          <div>
            <div className="flex items-center justify-between mb-2">
              <label className="text-gray-600 dark:text-zinc-400 text-sm flex items-center">
                <Clock className="w-4 h-4 mr-1 text-blue-500" />
                Server Logs
              </label>
              <Button variant="ghost" size="sm" className="text-xs">
                Clear Logs
              </Button>
            </div>
            <div className="bg-gray-50 dark:bg-black border border-gray-200 dark:border-zinc-900 rounded-md p-2 h-64 overflow-y-auto font-mono text-sm">
              {serverLogs.map((log, index) => <div key={index} className="text-gray-600 dark:text-zinc-400 py-1 border-b border-gray-100 dark:border-zinc-900 last:border-0">
                  {log}
                </div>)}
            </div>
          </div>
        </Card>
      </motion.div>
      {/* Database Status */}
      <motion.div className="mb-8" variants={itemVariants}>
        <h2 className="text-xl font-semibold text-gray-800 dark:text-white mb-4 flex items-center">
          <Database className="mr-2 text-purple-500" size={20} />
          Database Status
        </h2>
        <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
          <motion.div variants={itemVariants}>
            <Card accentColor="purple">
              <h3 className="text-gray-600 dark:text-zinc-400 text-sm mb-1">
                Documents
              </h3>
              <p className="text-2xl font-semibold text-gray-800 dark:text-white">
                256
              </p>
            </Card>
          </motion.div>
          <motion.div variants={itemVariants}>
            <Card accentColor="green">
              <h3 className="text-gray-600 dark:text-zinc-400 text-sm mb-1">
                Storage Used
              </h3>
              <p className="text-2xl font-semibold text-gray-800 dark:text-white">
                1.2 GB
              </p>
            </Card>
          </motion.div>
          <motion.div variants={itemVariants}>
            <Card accentColor="blue">
              <h3 className="text-gray-600 dark:text-zinc-400 text-sm mb-1">
                Last Sync
              </h3>
              <p className="text-2xl font-semibold text-gray-800 dark:text-white">
                5 min ago
              </p>
            </Card>
          </motion.div>
        </div>
      </motion.div>
    </motion.div>;
};