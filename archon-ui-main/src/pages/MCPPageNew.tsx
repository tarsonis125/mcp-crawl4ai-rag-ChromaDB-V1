import React, { useState } from 'react';
import { Play, Square, RefreshCw, Server, Clock, Copy, Loader } from 'lucide-react';
import { motion } from 'framer-motion';
import { Card } from '../components/ui/Card';
import { Button } from '../components/ui/Button';
import { useStaggeredEntrance } from '../hooks/useStaggeredEntrance';
import { MCPClients } from '../components/mcp/MCPClients';
export const MCPPage = () => {
  // Demo states for UI
  const [serverStatus] = useState('stopped');
  const [logs] = useState(['[INFO] MCP Server initialization...', '[INFO] Loading configuration from /etc/mcp/config.json', '[INFO] Server ready to start']);
  // Animation hooks
  const {
    isVisible,
    containerVariants,
    itemVariants,
    titleVariants
  } = useStaggeredEntrance([1, 2, 3], 0.15);
  // Tab state for switching between Server Control and Clients
  const [activeTab, setActiveTab] = useState<'server' | 'clients'>('server');
  return <motion.div initial="hidden" animate={isVisible ? 'visible' : 'hidden'} variants={containerVariants}>
      <motion.h1 className="text-3xl font-bold text-gray-800 dark:text-white mb-8" variants={titleVariants}>
        MCP Dashboard
      </motion.h1>
      {/* Tab Navigation */}
      <motion.div className="mb-6 border-b border-gray-200 dark:border-gray-800" variants={itemVariants}>
        <div className="flex space-x-8">
          <button onClick={() => setActiveTab('server')} className={`pb-3 relative ${activeTab === 'server' ? 'text-blue-600 dark:text-blue-400 font-medium' : 'text-gray-500 dark:text-gray-400 hover:text-gray-700 dark:hover:text-gray-300'}`}>
            Server Control
            {activeTab === 'server' && <span className="absolute bottom-0 left-0 right-0 h-0.5 bg-blue-500 shadow-[0_0_10px_rgba(59,130,246,0.5)]"></span>}
          </button>
          <button onClick={() => setActiveTab('clients')} className={`pb-3 relative ${activeTab === 'clients' ? 'text-cyan-600 dark:text-cyan-400 font-medium' : 'text-gray-500 dark:text-gray-400 hover:text-gray-700 dark:hover:text-gray-300'}`}>
            MCP Clients
            {activeTab === 'clients' && <span className="absolute bottom-0 left-0 right-0 h-0.5 bg-cyan-500 shadow-[0_0_10px_rgba(34,211,238,0.5)]"></span>}
          </button>
        </div>
      </motion.div>
      {/* Server Control Tab */}
      {activeTab === 'server' && <>
          {/* Server Control + Server Logs */}
          <motion.div className="grid grid-cols-1 lg:grid-cols-2 gap-6" variants={itemVariants}>
            {/* Left Column: Archon MCP Server */}
            <div>
              <h2 className="text-xl font-semibold text-gray-800 dark:text-white mb-4 flex items-center">
                <Server className="mr-2 text-blue-500" size={20} />
                Archon MCP Server
              </h2>
              <Card accentColor="blue" className="space-y-6">
                <div className="flex items-center justify-between">
                  <div className="flex items-center gap-3">
                    <div className={`h-3 w-3 rounded-full ${serverStatus === 'running' ? 'bg-emerald-500' : 'bg-pink-500'}`}></div>
                    <div>
                      <p className={`font-semibold ${serverStatus === 'running' ? 'text-emerald-500' : 'text-pink-500'}`}>
                        Status:{' '}
                        {serverStatus.charAt(0).toUpperCase() + serverStatus.slice(1)}
                      </p>
                    </div>
                  </div>
                  <div className="flex gap-2">
                    <Button variant="primary" accentColor="green" className="shadow-emerald-500/20 shadow-sm">
                      <Play className="w-4 h-4 mr-2 inline" />
                      Start Server
                    </Button>
                  </div>
                </div>
                <div className="border-t border-gray-200 dark:border-zinc-800 pt-4">
                  <div className="flex items-center justify-between mb-3">
                    <h3 className="text-sm font-medium text-gray-700 dark:text-zinc-300">
                      Transport Configuration
                    </h3>
                    <Button variant="secondary" accentColor="blue" size="sm">
                      <Copy className="w-3 h-3 mr-1 inline" />
                      Copy
                    </Button>
                  </div>
                  <div className="bg-gray-50 dark:bg-black/50 rounded-lg p-4 font-mono text-sm">
                    <pre className="text-gray-600 dark:text-zinc-400 whitespace-pre-wrap">
                      {`{
  "transport": "sse",
  "endpoint": "http://localhost:3000",
  "apiKey": "your-api-key"
}`}
                    </pre>
                  </div>
                </div>
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
                    Showing {logs.length} log entries
                  </p>
                  <Button variant="ghost" size="sm">
                    Clear Logs
                  </Button>
                </div>
                <div className="bg-gray-50 dark:bg-black border border-gray-200 dark:border-zinc-900 rounded-md p-4 h-80 overflow-y-auto font-mono text-sm">
                  {logs.map((log, index) => <div key={index} className="py-1.5 border-b border-gray-100 dark:border-zinc-900 last:border-0 text-gray-600 dark:text-zinc-400">
                      {log}
                    </div>)}
                </div>
              </Card>
            </div>
          </motion.div>
        </>}
      {/* Clients Tab */}
      {activeTab === 'clients' && <motion.div variants={itemVariants}>
          <MCPClients />
        </motion.div>}
    </motion.div>;
};